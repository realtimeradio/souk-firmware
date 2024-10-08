import struct
import numpy as np
from .block import Block
from ..helpers import cplx2uint

class Mixer(Block):
    """
    Instantiate a control interface for a Mixer block.

    :param host: CasperFpga interface for host.
    :type host: casperfpga.CasperFpga

    :param name: Name of block in Simulink hierarchy.
    :type name: str

    :param logger: Logger instance to which log messages should be emitted.
    :type logger: logging.Logger

    :param n_chans: Number of channels this block processes
    :type n_chans: int

    :param n_upstream_chans: Number of channels in the upstream PFB prior to downselection
    :type n_upstream_chans: int

    :param upstream_oversample_factor: Oversampling factor of upstream system. This, with the
       number of upstream channels, should allow this block to figure out how wide channels are.
    :type upstream_oversample_factor: int

    :param n_parallel_chans: Number of channels this block processes in parallel
    :type n_parallel_chans: int

    :param phase_bp: Number of phase fractional bits
    :type phase_bp: int

    :param n_ri_step_bits: Number of bits in each of the real/image per-sample rotation
        values.
    :type n_ri_step_bits: int

    """
    # Control bit offsets
    _IND_SYNC_OFFSET = 4
    _IND_STEP_OFFSET = 3
    _IND_OFFSET_OFFSET = 2
    _IND_SCALE_OFFSET = 1
    _IND_RI_STEP_OFFSET = 0
    _LO_OUTPUT_BP = 22 # Binary point position of phasors
    # Offsets of fields in control register
    _SCALE_WORD_OFFSET = 3 # Must be 3
    _PHASE_OFFSET_WORD_OFFSET = 2
    _RI_STEP_WORD_OFFSET = 1
    _PHASE_INC_WORD_OFFSET = 0
    _CONTROL_N_WORDS = 4 # parallel words
    _CONTROL_STRUCT_FORMAT = 'iIiI'
    def __init__(self, host, name,
            n_chans=4096,
            n_upstream_chans=8192,
            upstream_oversample_factor=2,
            n_parallel_chans=4,
            phase_bp=31,
            phase_offset_bp=31,
            n_scale_bits=8,
            n_ri_step_bits=16,
            n_phase_slots=2**12,
            logger=None):
        super(Mixer, self).__init__(host, name, logger)
        self.n_chans = n_chans
        assert n_chans % n_parallel_chans == 0
        self._n_upstream_chans = n_upstream_chans
        self._upstream_oversample_factor = upstream_oversample_factor
        self._n_parallel_chans = n_parallel_chans
        self._n_serial_chans = n_chans // n_parallel_chans
        self._phase_bp = phase_bp
        self._phase_offset_bp = phase_offset_bp
        self._n_scale_bits = n_scale_bits
        self._n_ri_step_bits = n_ri_step_bits
        self.n_phase_slots = n_phase_slots

    def enable_power_mode(self):
        """
        Instead of applying a phase rotation to the data streams,
        calculate their power.
        """
        self.write_int('power_en', 1)

    def disable_power_mode(self):
        """
        Use phase rotation, rather than power.
        """
        self.write_int('power_en', 0)

    def is_power_mode(self):
        """
        Get the current block mode.

        :return: True if the block is calculating power, False if it is
            applying phase rotation.
        :rtype: bool
        """
        return bool(self.read_int('power_en'))

    def set_chan_freq(self, chan, freq_offset_hz=None, phase_offset=0, sample_rate_hz=2500000000, next_buf=False):
        """
        Set the frequency of output channel `chan`.

        :param chan: The channel index to which this phase-rate should be applied
        :type chan: int

        :param freq_offset_hz: The frequency offset, in Hz, from the channel center.
            If None, disable this oscillator.
        :type freq_offset_hz: float

        :param phase_offset: The phase offset at which this oscillator should start
            in units of radians.
        :type phase: float

        :param sample_rate_hz: DAC sample rate, in Hz
        :type sample_rate_hz: float

        :param next_buf: If False, write directly to the buffer currently being
            read by the firmware. If True, write to the next buffer, leaving
            the new parameters inactive until the buffer is switched
            (eg. by `switch_current_buffer`). If 0 or 1, write to that buffer.
        :type next_buf: bool or int

        """
        if freq_offset_hz is None:
            phase_step = None
        else:
            fft_period_s = self._n_upstream_chans / self._upstream_oversample_factor / sample_rate_hz
            fft_rbw_hz = 1./fft_period_s # FFT channel width, Hz
            phase_step = freq_offset_hz / fft_rbw_hz * 2 * np.pi
        self.set_phase_step(chan, phase=phase_step, phase_offset=phase_offset, next_buf=next_buf)

    def _format_amp_scale(self, v):
        """
        Given a desired scale factor, format as an appropriate
        integer which is interpretable by the mixer firmware.

        :param v: Scale factor (or numpy array of factors)
        :type v: float or array of floats

        :return: Integer scale[s]
        :rtype: int or array of ints
        """
        is_array = isinstance(v, np.ndarray)
        if not is_array:
            v = np.array([v], dtype=float)
        v *= 2**self._n_scale_bits
        v = np.array(np.round(v), dtype=int)
        # saturate
        scale_max = 2**self._n_scale_bits - 1
        v[v > scale_max] = scale_max
        if is_array:
            return v
        else:
            return v[0]

    def set_amplitude_scale(self, chan, scale=1.0, los=['rx', 'tx'], next_buf=False):
        """
        Apply an amplitude scaling <=1 to an output channel.

        :param chan: The channel index to which this phase-rate should be applied
        :type chan: int

        :param scaling: optional scaling (<=1) to apply to the output tone amplitude.
        :type scaling: float

        :param los: List of LOs to write to. Can be ['rx'], ['tx'] or ['rx', 'tx']
        :type los: list

        :param next_buf: If False, write directly to the buffer currently being
            read by the firmware. If True, write to the next buffer, leaving
            the new parameters inactive until the buffer is switched
            (eg. by `switch_current_buffer`). If 0 or 1, write to that buffer.
        :type next_buf: bool or int

        """
        if next_buf in [0, 1]:
            buf = next_buf
        else:
            buf = self.get_current_buffer()
            if next_buf:
                buf = (buf + 1) % 2
        p = chan % self._n_parallel_chans  # Parallel stream number
        s = chan // self._n_parallel_chans # Serial channel position
        assert scale >= 0
        scale = self._format_amp_scale(scale)
        word_base = self._CONTROL_N_WORDS * (buf * self.n_serial_chans + s)
        for lo in los:
            if lo not in ['rx', 'tx']:
                raise ValueError(f"Only LOs 'rx' and 'tx' are understood. Not {lo}.")
            regname = f'{lo}_lo{p}_control'
            self.write_int(regname, scale, word_offset=word_base + self._SCALE_WORD_OFFSET)

    def _format_phase_step(self, phase, phase_offset):
        """
        Given a desired phase step and offset, format each as appropriate
        integers which are interpretable by the mixer firmware

        :param phase: phase[s] to step per clock cycle, in radians
        :type phase: float, or array of floats

        :param phase_offset: phase offset[s], in radians
        :type phase_offset: float, or array of floats

        :return: (phase_int, phase_offset_int) -- the integers to be written
            to firmware. Each is either an integer (if ``phase`` and ``phase_offset``
            are integers. Else an array of integers.
        :rtype: int, int (or array(dtype=int), array(dtype=int))
        """
        is_array = isinstance(phase, np.ndarray)
        assert isinstance(phase_offset, np.ndarray) == is_array
        if not is_array:
            phase = np.array([phase])
            phase_offset = np.array([phase_offset])
        n_tone = len(phase)
        assert len(phase_offset) == n_tone
        phase_int = np.zeros(len(phase), dtype='i4')
        phase_offset_int = np.zeros(len(phase_offset), dtype='i4')
        for i in range(n_tone):
            phase_scaled = phase[i] / np.pi # units of pi rads
            phase_scaled = ((phase_scaled + 1) % 2) - 1 # -pi to pi
            phase_scaled = int(phase_scaled * 2**self._phase_bp)
            phase_int[i] = phase_scaled
            phase_offset_scaled = phase_offset[i] / np.pi # units of pi rads
            phase_offset_scaled = ((phase_offset_scaled + 1) % 2) - 1 # -pi to pi
            phase_offset_scaled = int(phase_offset_scaled * 2**self._phase_offset_bp)
            phase_offset_int[i] = phase_offset_scaled
        if is_array:
            return phase_int, phase_offset_int
        else:
            return phase_int[0], phase_offset_int[0]

    def set_phase_step(self, chan, phase=None, phase_offset=0.0, los=['rx', 'tx'], next_buf=False):
        """
        Set the phase increment to apply on each successive sample for
        channel `chan`.

        :param chan: The channel index to which this phase-rate should be applied
        :type chan: int

        :param phase: The phase increment to be added each successive sample
            in units of radians. If None, disable this oscillator.
        :type phase: float

        :param phase_offset: The phase offset at which this oscillator should start
            in units of radians.
        :type phase: float

        :param los: List of LOs to write to. Can be ['rx'], ['tx'] or ['rx', 'tx']
        :type los: list

        :param next_buf: If False, write directly to the buffer currently being
            read by the firmware. If True, write to the next buffer, leaving
            the new parameters inactive until the buffer is switched
            (eg. by `switch_current_buffer`). If 0 or 1, write to that buffer.
        :type next_buf: bool

        """
        if next_buf in [0, 1]:
            buf = next_buf
        else:
            buf = self.get_current_buffer()
            if next_buf:
                buf = (buf + 1) % 2
        p = chan % self._n_parallel_chans  # Parallel stream number
        s = chan // self._n_parallel_chans # Serial channel position
        if phase is None:
            phase = 0
            phase_scaled = 0
            phase_offset_scaled = 0
        else:
            phase_scaled, phase_offset_scaled = self._format_phase_step(phase, phase_offset)
        ri_step_scaled = cplx2uint(np.cos(phase) + 1j*np.sin(phase), self._n_ri_step_bits)
        word_base = self._CONTROL_N_WORDS * (buf * self.n_serial_chans + s)
        v = [0, 0, 0]
        for lo in los:
            if lo not in ['rx', 'tx']:
                raise ValueError(f"Only LOs 'rx' and 'tx' are understood. Not {lo}.")
            regname = f'{lo}_lo{p}_control'
            v[self._PHASE_INC_WORD_OFFSET] = phase_scaled
            v[self._PHASE_OFFSET_WORD_OFFSET] = phase_offset_scaled
            v[self._RI_STEP_WORD_OFFSET] = ri_step_scaled
            self.write(regname, struct.pack('>' + self._CONTROL_STRUCT_FORMAT[0:3], *v), word_offset=word_base)

    def get_current_buffer(self):
        """
        Get the current ping-pong buffer index (either 0 or 1) used for reading.

        :return: Buffer index
        :rtype: int
        """
        return self.read_uint('read_buf')

    def set_current_buffer(self, buf_id):
        """
        Set the current ping-pong buffer index (either 0 or 1) used for reading.

        :return: Buffer index
        :rtype: int
        """
        assert buf_id in [0, 1], 'buf_id should be either 0 or 1'
        self.write_int('read_buf', buf_id)

    def switch_current_buffer(self):
        """
        Flip the current buffer by reading `get_current_buffer`, swapping 0 <-> 1
        and writing to `set_current_buffer`
        """
        cur_buf = self.get_current_buffer()
        next_buf = (cur_buf + 1) % 2
        self.set_current_buffer(next_buf)
 
    def get_phase_offset(self, chan, lo='rx'):
        """
        Get the currently loaded phase increment being applied to channel `chan`.

        :param lo: Which LO to read. 'rx' or 'tx'
        :type lo: str

        :return: (phase_step, phase_offset, scale)
            A tuple containing the phase increment (in radians) being applied
            to channel `chan` on each successive sample, the start phase in radians,
            and the scale factor being applied to this channel.
        :rtype: float
        """
        cur_buf = self.get_current_buffer()
        p = chan % self._n_parallel_chans  # Parallel stream number
        s = chan // self._n_parallel_chans # Serial channel position
        if lo not in ['rx', 'tx']:
            raise ValueError(f"Only LOs 'rx' and 'tx' are understood. Not {lo}.")
        regname = f'{lo}_lo{p}_control'
        word_base = self._CONTROL_N_WORDS * (cur_buf * self._n_serial_chans + s)
        # Increment-per-clock
        inc_val = self.read_int(regname, word_offset=word_base + self._PHASE_INC_WORD_OFFSET) / 2**self._phase_bp * np.pi
        # Now phase offset
        phase_offset = self.read_int(offset_regname, word_offset=word_base + self._PHASE_OFFSET_WORD_OFFSET) / 2**self._phase_offset_bp * np.pi
        # Finally scale
        scale = self.read_uint(scale_regname, word_offset=word_base + self._SCALE_WORD_OFFSET) / 2**self._n_scale_bits
        return inc_val, phase_offset, scale

    def set_freqs(self, freqs_hz, phase_offsets, scaling=1.0, sample_rate_hz=2500000000, los=['rx', 'tx'], next_buf=False):
        """
        Configure the amplitudes, phases, and frequencies of multiple tones.

        :param freqs_hz: The frequencies, in Hz, to emit.
        :type freqs_hz: numpy.ndarray

        :param phase_offsets: The phase offsets at which oscillators should start,
            in units of radians.
        :type phase_offsets: np.ndarray

        :param scaling: optional scaling (<=1) to apply to the output tone
            amplitudes. If a single number, apply this scale to all tones.
        :type scaling: np.ndarray

        :param sample_rate_hz: DAC sample rate, in Hz
        :type sample_rate_hz: float

        :param los: List of LOs to write to. Can be ['rx'], ['tx'] or ['rx', 'tx']
        :type los: list

        :param next_buf: If False, write directly to the buffer currently being
            read by the firmware. If True, write to the next buffer, leaving
            the new parameters inactive until the buffer is switched
            (eg. by `switch_current_buffer`). If 0 or 1, write to that buffer.
        :type next_buf: bool or int

        """
        if next_buf in [0, 1]:
            buf = next_buf
        else:
            buf = self.get_current_buffer()
            if next_buf:
                buf = (buf + 1) % 2
        freqs_hz = np.array(freqs_hz, dtype=float)
        n_tone = len(freqs_hz)
        phase_offsets = np.array(phase_offsets, dtype=float)
        assert len(phase_offsets) == n_tone
        try:
            assert len(scaling) == n_tone
            scaling = np.array(scaling)
        except TypeError:
            scaling = scaling * np.ones(n_tone, dtype=float)
        
        fft_period_s = self._n_upstream_chans / self._upstream_oversample_factor / sample_rate_hz
        fft_rbw_hz = 1./fft_period_s # FFT channel width, Hz
        phase_steps = freqs_hz / fft_rbw_hz * 2 * np.pi
        ri_steps = np.cos(phase_steps) + 1j*np.sin(phase_steps)
        phase_steps, phase_offsets = self._format_phase_step(phase_steps, phase_offsets)
        scaling = self._format_amp_scale(scaling)
        ri_steps = [cplx2uint(ri_step, self._n_ri_step_bits) for ri_step in ri_steps]
        # format appropriately
        phase_steps_u = np.array(phase_steps, dtype='>i4').view('>u4')
        phase_offsets_u = np.array(phase_offsets, dtype='>i4').view('>u4')
        scaling_u = np.array(scaling, dtype='>u4')
        ri_steps_u = np.array(ri_steps, dtype='>u4')
        # create a new array to put all control variable into in parallel
        v = np.zeros(int(np.ceil(n_tone / self._n_parallel_chans)) * self._CONTROL_N_WORDS, dtype='>u4')
        for i in range(min(self._n_parallel_chans, n_tone)):
            v[self._SCALE_WORD_OFFSET :: self._CONTROL_N_WORDS] = scaling_u[i::self._n_parallel_chans]
            v[self._PHASE_INC_WORD_OFFSET :: self._CONTROL_N_WORDS] = phase_steps_u[i::self._n_parallel_chans]
            v[self._PHASE_OFFSET_WORD_OFFSET :: self._CONTROL_N_WORDS] = phase_offsets_u[i::self._n_parallel_chans]
            v[self._RI_STEP_WORD_OFFSET :: self._CONTROL_N_WORDS] = ri_steps_u[i::self._n_parallel_chans]
            for lo in los:
                if lo not in ['rx', 'tx']:
                    raise ValueError(f"Only LOs 'rx' and 'tx' are understood. Not {lo}.")
                reg = f'{lo}_lo{i}_control'
                self.write(reg, v.tobytes())

    def set_phase_switch_pattern(self, pattern, spectra_per_step, los=['rx', 'tx'], n_blank=0):
        """
        Set the phase switching pattern.

        For a pattern (eg) [1, 0] The first `spectra_per_step` spectra will have LOs phase inverted,
        the next `spectra_per_step` spectra will not be inverted, and then the pattern will reset.

        The maximum number of slots in the pattern is `self.n_phase_slots`.

        :param pattern: List or array of ones and zeros. One indicates that phase should be inverted
            in this slot. 0 indicates phase should not be inverted.
        :type pattern: list

        :param spectra_per_step: The number of spectra to which each element of pattern should be applied.
        :type spectra_per_step: int

        :param los: List of LOs to modify. Can be ['rx'], ['tx'] or ['rx', 'tx']
        :type los: list

        :param n_blank: Number of spectra to blank before and after a phase switch transition
        :type n_blank: int
        """
        n_slots_used = len(pattern)
        assert n_slots_used <= self.n_phase_slots, f'Number of elements of `pattern` must be no more than {self.n_phase_slots}'
        spectra_per_cycle = n_slots_used * spectra_per_step
        pattern_full = np.zeros(self.n_phase_slots, dtype='>B')
        pattern_full[0:n_slots_used] = pattern[:]
        assert np.all([x in [0,1] for x in pattern]), 'All pattern elements must be 1 or 0'

        for lo in los:
            if lo not in ['rx', 'tx']:
                raise ValueError(f"Only LOs 'rx' and 'tx' are understood. Not {lo}.")
            self.write(f'{lo}_lo0_phase_inv_en', pattern_full.tobytes())
            self.write_int(f'{lo}_lo0_last_spec_index_per_step', spectra_per_step-1)
            self.write_int(f'{lo}_lo0_last_spec_index_cycle', spectra_per_cycle-1)
            self.write_int(f'{lo}_lo0_last_spec_before_blank', self._n_serial_chans - 1 - n_blank)
            self.write_int(f'{lo}_lo0_n_spectra_blank', n_blank)

    def get_phase_switch_pattern(self, lo='rx'):
        """
        Get the currently loaded phase switch pattern.

        :param lo: Which LO to read. 'rx' or 'tx'
        :type lo: str

        :return: (phase pattern, spectra_per_step)
            A tuple containing the phase pattern as an array of 1s and 0s,
            and the number of spectra to which each phase is applied.
        :rtype: (numpy.ndarray, int)
        """
        if lo not in ['rx', 'tx']:
            raise ValueError(f"Only LOs 'rx' and 'tx' are understood. Not {lo}.")
        spectra_per_step = self.read_uint(f'{lo}_lo0_last_spec_index_per_step') + 1
        spectra_per_cycle = self.read_uint(f'{lo}_lo0_last_spec_index_cycle') + 1
        assert spectra_per_cycle % spectra_per_step == 0, 'This should not happen!'
        n_steps = spectra_per_cycle // spectra_per_step
        pattern = np.frombuffer(self.read(f'{lo}_lo0_phase_inv_en', self.n_phase_slots), dtype='>B')
        return pattern[0:n_steps], spectra_per_step

    def _get_lo_snapshot(self, n=None):
        """
        DEBUG FIRMWARE ONLY

        Get the phase outputs of the TX LO

        :param n: If provided, only return this channel's data
        :type n: int

        :return: Array of LO value vs time
        :rtype: numpy.ndarray
        """
        try:
            ss = self.host.snapshots[self.prefix + 'snapshot']
        except AttributeError:
            self.error("Can't find snapshot. Is this debug feature in the firmware?")
            raise RuntimeError
        raw, t = ss.read_raw()
        dc = np.frombuffer(raw['data'], dtype='>i4') / self._LO_OUTPUT_BP
        d = dc[0::2] + 1j*dc[1::2]
        if n is None:
            return d
        nval = len(d) // self.n_chans
        ntime = ss.width_bits // 64
        out = []
        for i in range(nval // ntime):
            for j in range(ntime):
                out += [d[i * self.n_chans * ntime + j]]
        return np.array(out)


    def initialize(self, read_only=False):
        """
        Initialize the block.

        :param read_only: If True, this method is a no-op. If False,
            set this block to phase rotate mode, but initialize 
            with each channel having zero phase increment.
        :type read_only: bool
        """
        if read_only:
            pass
        else:
            self.disable_power_mode()
            self.set_freqs(np.zeros(self.n_chans), np.zeros(self.n_chans), np.zeros(self.n_chans))
            self.set_phase_switch_pattern([0], 1024) # Don't do any phase switching
