import struct
import numpy as np
from .block import Block

class Mixer(Block):
    """
    Instantiate a control interface for a Channel Reorder block.

    :param host: CasperFpga interface for host.
    :type host: casperfpga.CasperFpga

    :param name: Name of block in Simulink hierarchy.
    :type name: str

    :param logger: Logger instance to which log messages should be emitted.
    :type logger: logging.Logger

    :param n_chans: Number of channels this block processes
    :type n_chans: int

    :param n_parallel_chans: Number of channels this block processes in parallel
    :type n_parallel_chans: int

    :param phase_bp: Number of phase fractional bits
    :type phase_bp: int

    """
    def __init__(self, host, name,
            n_chans=4096,
            n_parallel_chans=4,
            phase_bp=31,
            phase_offset_bp=31,
            n_scale_bits=8,
            logger=None):
        super(Mixer, self).__init__(host, name, logger)
        self.n_chans = n_chans
        assert n_chans % n_parallel_chans == 0
        self._n_parallel_chans = n_parallel_chans
        self._n_serial_chans = n_chans // n_parallel_chans
        self._phase_bp = phase_bp
        self._phase_offset_bp = phase_offset_bp
        self._n_scale_bits = n_scale_bits

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

    def set_chan_freq(self, chan, freq_offset_hz=None, phase_offset=0, sample_rate_hz=2500000000):
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

        """
        if freq_offset_hz is None:
            phase_step = None
        else:
            fft_period_s = self.n_chans / sample_rate_hz
            fft_rbw_hz = 1./fft_period_s # FFT channel width, Hz
            phase_step = freq_offset_hz / fft_rbw_hz * 2 * np.pi
        self.set_phase_step(chan, phase=phase_step, phase_offset=phase_offset)

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

    def set_amplitude_scale(self, chan, scale=1.0):
        """
        Apply an amplitude scaling <=1 to an output channel.

        :param chan: The channel index to which this phase-rate should be applied
        :type chan: int

        :param scaling: optional scaling (<=1) to apply to the output tone amplitude.
        :type scaling: float
        """
        p = chan % self._n_parallel_chans  # Parallel stream number
        s = chan // self._n_parallel_chans # Serial channel position
        regname = f'lo{p}_scale'
        assert scale >= 0
        scale = self._format_amp_scale(scale)
        self.write_int(regname, scale, word_offset=s)

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
        phase_int = np.zeros(len(phase), dtype='u4')
        phase_offset_int = np.zeros(len(phase_offset), dtype='i4')
        for i in range(n_tone):
            phase_scaled = phase[i] / np.pi # units of pi rads
            phase_scaled = ((phase_scaled + 1) % 2) - 1 # -pi to pi
            phase_scaled = int(phase_scaled * 2**self._phase_bp)
            # set the MSB high
            if phase_scaled >= 0:
                phase_int[i] = (1<<31) + phase_scaled
            else:
                phase_int[i] = (1<<31) + (phase_scaled + (1<<31))
            phase_offset_scaled = phase_offset[i] / np.pi # units of pi rads
            phase_offset_scaled = ((phase_offset_scaled + 1) % 2) - 1 # -pi to pi
            phase_offset_scaled = int(phase_offset_scaled * 2**self._phase_offset_bp)
            phase_offset_int[i] = phase_offset_scaled
        if is_array:
            return phase_int, phase_offset_int
        else:
            return phase_int[0], phase_offset_int[0]

    def set_phase_step(self, chan, phase=None, phase_offset=0.0):
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

        """
        p = chan % self._n_parallel_chans  # Parallel stream number
        s = chan // self._n_parallel_chans # Serial channel position
        inc_regname = f'lo{p}_phase_inc'
        offset_regname = f'lo{p}_phase_offset'
        if phase is None:
            phase_scaled = 0
            phase_offset_scaled = 0
        else:
            phase_scaled, phase_offset_scaled = self._format_phase_step(phase, phase_offset)
        self.write_int(inc_regname, phase_scaled, word_offset=s)
        self.write_int(offset_regname, phase_offset_scaled, word_offset=s)
 
    def get_phase_offset(self, chan):
        """
        Get the currently loaded phase increment being applied to channel `chan`.

        :return: (phase_step, phase_offset, enabled)
            A tuple containing the phase increment (in radians) being applied
            to channel `chan` on each successive sample, the start phase in radians,
            and a boolean indicating the channel is enabled.
        :rtype: float
        """
        p = chan % self._n_parallel_chans  # Parallel stream number
        s = chan // self._n_parallel_chans # Serial channel position
        inc_regname = f'lo{p}_phase_inc'
        offset_regname = f'lo{p}_phase_offset'
        # Read increment reg and mask off enable bit
        inc_val = self.read_uint(inc_regname, word_offset=s)
        enabled = bool(inc_val >> 31)
        phase_step = inc_val & (2**31 - 1)
        if phase_step > 2**30:
            phase_step -= 2**31
        phase_step = (phase_step / (2**self._phase_bp)) * np.pi
        # Now phase offset
        phase_offset = self.read_int(offset_regname, word_offset=s)
        phase_offset = (phase_offset / (2**self._phase_offset_bp)) * np.pi
        return phase_step, phase_offset, enabled

    def set_freqs(self, freqs_hz, phase_offsets, scaling=1.0, sample_rate_hz=2500000000):
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

        """
        freqs_hz = np.array(freqs_hz, dtype=float)
        n_tone = len(freqs_hz)
        phase_offsets = np.array(phase_offsets, dtype=float)
        assert len(phase_offsets) == n_tone
        try:
            assert len(scaling) == n_tone
            scaling = np.array(scaling)
        except TypeError:
            scaling = scaling * np.ones(n_tone, dtype=float)
        
        fft_period_s = self.n_chans / sample_rate_hz
        fft_rbw_hz = 1./fft_period_s # FFT channel width, Hz
        phase_steps = freqs_hz / fft_rbw_hz * 2 * np.pi
        phase_steps, phase_offsets = self._format_phase_step(phase_steps, phase_offsets)
        scaling = self._format_amp_scale(scaling)
        # format appropriately
        print(phase_steps)
        phase_steps = np.array(phase_steps, dtype='>u4')
        print(phase_steps)
        phase_offsets = np.array(phase_offsets, dtype='>u4')
        scaling = np.array(scaling, dtype='>u4')
        for i in range(self._n_parallel_chans):
            regprefix = f'lo{i}'
            self.write(regprefix + '_scale', scaling[i::self._n_parallel_chans].tobytes())
            self.write(regprefix + '_phase_inc', phase_steps[i::self._n_parallel_chans].tobytes())
            self.write(regprefix + '_phase_offset', phase_offsets[i::self._n_parallel_chans].tobytes())

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
