from tkinter import E
from .block import Block
from .timed_pulse import TimedPulse
import numpy as np
from cosmic_f.error_levels import *

class PhaseRotate(Block):
    """
    Instantiate a control interface for a phase rotate block.

    :param host: CasperFpga interface for host.
    :type host: casperfpga.CasperFpga

    :param name: Name of block in Simulink hierarchy.
    :type name: str

    :param logger: Logger instance to which log messages should be emitted.
    :type logger: logging.Logger

    :param n_streams: Number of independent streams which may be shifted
    :type n_streams: int

    :param n_chans: Number of frequency channels per signal.
    :type n_chans: int

    :param samplehz: The ADC sample rate in MHz
    :type samplehz: float

    """
    _DELAY_BW = 64
    _DELAY_BP = 32
    _DELAY_RATE_BW = 32
    _DELAY_RATE_BP = 31
    _PHASE_BW = 32
    _PHASE_BP = 31
    _PHASE_RATE_BW=32
    _PHASE_RATE_BP=31
    _CAL_PHASE_BW = 16
    _CAL_PHASE_BP = 15
    _FIRMWARE_PHASE_BP = 31
    _FIRMWARE_SLOPE_BP = 31

    MAX_DELAY = (2**(_DELAY_BW -1) -1) / (2**_DELAY_BP)
    MAX_DELAY_RATE = (2**(_DELAY_RATE_BW-1) -1) / (2**_DELAY_RATE_BP)
    MAX_PHASE = (2**(_PHASE_BW-1) -1) / (2**_PHASE_BP)
    MAX_PHASE_RATE = (2**(_PHASE_RATE_BW-1) -1) / (2**_PHASE_RATE_BP)
    MIN_DELAY = -(2**(_DELAY_BW-1) ) / (2**_DELAY_BP)
    MIN_DELAY_RATE = -(2**(_DELAY_RATE_BW-1)) / (2**_DELAY_RATE_BP) 
    MIN_PHASE = -(2**(_PHASE_BW-1)) / (2**_PHASE_BP)
    MIN_PHASE_RATE = -(2**(_PHASE_RATE_BW-1)) / (2**_PHASE_RATE_BP) 
    FINE_DELAY_LOAD_PERIOD = 4 # It takes 4 spectra to compute and load delays
    RATE_SCALE_FACTOR = 2**5   # The firmware divides rates down by this amount

    def __init__(self, host, name, n_streams=4, samplehz=2048000000, n_chans=1024, logger=None):
        super(PhaseRotate, self).__init__(host, name, logger)
        self.timer = TimedPulse(host, name+"_timing", logger)
        self.n_streams = n_streams
        self.samplehz = samplehz
        self.n_chans = n_chans

    def set_delay(self, stream, delay):
        """
        Set the delay in units of ADC samples for the specified stream.

        :param stream: ADC stream index to which the delay should be applied.
        :type stream: int

        :param delay: delay to load (ADC samples)
        :type delay: float
        """
        if delay > self.MAX_DELAY: 
            message = f"""User requested a delay of {delay}, 
            maximum allowed is {self.MAX_DELAY}"""
            self._error(message)
            raise RuntimeError(message)
        if delay < self.MIN_DELAY:
            message = f"""User requested a delay msb of {delay}, 
            minimum allowed is {self.MIN_DELAY}"""
            self._error(message)
            raise RuntimeError(message)
        if stream > self.n_streams:
            self._error(f"""Tried to set fractional delay for stream {stream} > n_streams ({self.n_streams})""")
        
        delay_lsb_reg = f"""params{stream}_delay_lsb"""
        delay_msb_reg = f"""params{stream}_delay_msb"""

        #scale the floating point value appropriately
        scaled_delay = delay * 2**self._DELAY_BP
        
        #Registers are unsigned. As such we need to prepare the values to be unsigned.
        if scaled_delay < 0:
            unsigned_scaled_delay = int(scaled_delay + 2**self._DELAY_BW)
        else:
            unsigned_scaled_delay = int(scaled_delay)

        #prepare for two unsigned 32bit swreg's
        uint32_delay_lsb = unsigned_scaled_delay & 0xffffffff
        uint32_delay_msb = (unsigned_scaled_delay>>32) & 0xffffffff
        self._debug(f"""Setting fractional lsb delay of stream {stream} to {uint32_delay_lsb}""")
        self.write_int(delay_lsb_reg, uint32_delay_lsb)
        self._debug(f"""Setting fractional msb delay of stream {stream} to {uint32_delay_msb}""")
        self.write_int(delay_msb_reg, uint32_delay_msb)
    
    def get_delay(self, stream):
        """
        Retrieve the programmed fractional delay in ADC samples for a given stream.

        :param stream: ADC stream index from which the fractional delay should be retrieved.
        :type stream: int

        :return: uint(delay), scale
        """
        if stream > self.n_streams:
            self._error(f"""Tried to fetch fractional delay for stream {stream} > n_streams ({self.n_streams})""")
        
        delay_lsb_reg = f"""params{stream}_delay_lsb"""
        delay_msb_reg = f"""params{stream}_delay_msb"""
        uint32_delay_lsb = self.read_uint(delay_lsb_reg)
        uint32_delay_msb = self.read_uint(delay_msb_reg)

        composite_val = (uint32_delay_msb << 32) + uint32_delay_lsb

        #If greater than the most positive option for signed representation, it was negative:
        if composite_val > (2**(self._DELAY_BW -1) -1):
            composite_val -= 2**self._DELAY_BW

        return composite_val, 2**self._DELAY_BP
    
    def set_delay_rate(self, stream, delay_rate):
        """
        Set the delay rate in ADC samples per spectra for a given stream.

        :param stream: ADC stream index to which the phase should be applied.
        :type stream: int

        :param delay_rate: delay_rate to load (ADC samples per spectra)
        :type delay_rate: float
        """
        if delay_rate > self.MAX_DELAY_RATE:
            message = f"""User requested a delay rate of {delay_rate}, 
            maximum allowed is {self.MAX_DELAY_RATE}"""
            self._error(message)
            raise RuntimeError(message)
        if delay_rate < self.MIN_DELAY_RATE:
            message = f"""User requested a delay rate of {delay_rate}, 
            minimum allowed is {self.MIN_DELAY_RATE}"""
            self._error(message)
            raise RuntimeError(message)
        if np.abs(delay_rate) >= (1./(self.RATE_SCALE_FACTOR * self.FINE_DELAY_LOAD_PERIOD)):
            message = f"""User requested a delay rate of {delay_rate}, 
            that exceeds allowable magnitude given RATE_SCALE_FACTOR
            and FINE_DELAY_LOAD_PERIOD.\n
            delay_rate < {(1./(self.RATE_SCALE_FACTOR * self.FINE_DELAY_LOAD_PERIOD))}"""
            raise RuntimeError(message)
        if stream > self.n_streams:
            self._error(f"""Tried to set delay rate for stream {stream} > n_streams ({self.n_streams})""")
        
        delay_rate_reg = f"""params{stream}_delay_rate"""
        
        #scale the floating point value appropriately
        scaled_delay_rate = delay_rate * 2**self._DELAY_RATE_BP * self.RATE_SCALE_FACTOR * self.FINE_DELAY_LOAD_PERIOD

        #Registers are unsigned. As such we need to prepare the values to be unsigned.
        if scaled_delay_rate < 0:
            int_delay_rate = int(scaled_delay_rate + 2**self._DELAY_RATE_BW)
        else:
            int_delay_rate = int(scaled_delay_rate)
        self._debug(f"""Setting delay rate of stream {stream} to {int_delay_rate}""")
        self.write_int(delay_rate_reg, int_delay_rate)

    def get_delay_rate(self, stream):
        """
        Retrieve the programmed delay rate in ADC samples per spectra for a given stream.

        :param stream: ADC stream index from which the delay rate should be retrieved.
        :type stream: int

        :return: uint(delay_rate), scale
        """
        if stream > self.n_streams:
            self._error(f"""Tried to fetch delay rate for stream {stream} > n_streams ({self.n_streams})""")
        
        delay_rate_reg = f"""params{stream}_delay_rate"""
        val = self.read_uint(delay_rate_reg)

        #If greater than the most positive option for signed representation, it was negative:
        if val > (2**(self._DELAY_RATE_BW-1) -1):
            val -= 2**self._DELAY_RATE_BW

        return val, (2**self._DELAY_RATE_BP * self.RATE_SCALE_FACTOR * self.FINE_DELAY_LOAD_PERIOD)

    def set_phase(self, stream, phase):
        """
        Set the phase in radians normalised to +/- 1 for a given stream.

        :param stream: ADC stream index to which the phase should be applied.
        :type stream: int

        :param phase: phase to load (radians)
        :type phase: float
        """
        if phase >= self.MAX_PHASE:
            message = f"""User requested a delay rate of {phase}, 
            maximum allowed is {self.MAX_PHASE}"""
            self._error(message)
            raise RuntimeError(message)
        if phase < self.MIN_PHASE:
            message = f"""User requested a delay rate of {phase}, 
            minimum allowed is {self.MIN_PHASE}"""
            self._error(message)
            raise RuntimeError(message)
        if stream > self.n_streams:
            self._error(f"""Tried to set phase for stream {stream} > n_streams ({self.n_streams})""")
        phase_reg = f"""params{stream}_phase"""

        #scale the floating point value appropriately
        scaled_phase = phase * 2**self._PHASE_BP

        #Registers are unsigned. As such we need to prepare the values to be unsigned.
        if scaled_phase < 0:
            int_phase = int(scaled_phase + 2**self._PHASE_BW)
        else:
            int_phase = int(scaled_phase)
        self._debug(f"""Setting delay rate of stream {stream} to {int_phase}""")
        self.write_int(phase_reg, int_phase)

    def get_phase(self, stream):
        """
        Retrieve the programmed phase in radians normalised to +/- 1 for a given stream in radians.

        :param stream: ADC stream index from which the delay phase should be retrieved.
        :type stream: int

        :return: uint(phase)
        """
        if stream > self.n_streams:
            self._error(f"""Tried to fetch phase for stream {stream} > n_streams ({self.n_streams})""")
        
        phase_reg = f"""params{stream}_phase"""
        val = self.read_uint(phase_reg)

        #If greater than the most positive option for signed representation, it was negative:
        if val > (2**(self._PHASE_BW-1) -1):
            val -= 2**self._PHASE_BW

        return val, 2**self._PHASE_BP

    def set_phase_rate(self, stream, phase_rate):
        """
        Set the phase rate in radians per spectra for a given stream.

        :param stream: ADC stream index to which the phase_rate should be applied.
        :type stream: int

        :param phase_rate: phase_rate to load (radians per spectra)
        :type phase_rate: float
        """
        if phase_rate >= self.MAX_PHASE_RATE:
            message = f"""User requested a delay rate of {phase_rate}, 
            maximum allowed is {self.MAX_PHASE_RATE}"""
            self._error(message)
            raise RuntimeError(message)
        if phase_rate < self.MIN_PHASE_RATE:
            message = f"""User requested a delay rate of {phase_rate}, 
            minimum allowed is {self.MIN_PHASE_RATE}"""
            self._error(message)
            raise RuntimeError(message)
        if np.abs(phase_rate) >= (1./(self.RATE_SCALE_FACTOR * self.FINE_DELAY_LOAD_PERIOD)):
            message = f"""User requested a delay rate of {phase_rate}, 
            that exceeds allowable magnitude given RATE_SCALE_FACTOR
            and FINE_DELAY_LOAD_PERIOD.\n
            phase_rate < {(1./(self.RATE_SCALE_FACTOR * self.FINE_DELAY_LOAD_PERIOD))}"""
            raise RuntimeError(message)
        if stream > self.n_streams:
            self._error(f"""Tried to set phase rate for stream {stream} > n_streams ({self.n_streams})""")

        phase_reg_rate = f"""params{stream}_phase_rate"""
        #scale the floating point value appropriately
        scaled_phase_rate = phase_rate * 2**self._PHASE_RATE_BP * self.RATE_SCALE_FACTOR * self.FINE_DELAY_LOAD_PERIOD

        #Registers are unsigned. As such we need to prepare the values to be unsigned.
        if scaled_phase_rate < 0:
            int_phase_rate = int(scaled_phase_rate + 2**self._PHASE_RATE_BW)
        else:
            int_phase_rate = int(scaled_phase_rate)
        self._debug(f"""Setting delay rate of stream {stream} to {int_phase_rate}""")
        self.write_int(phase_reg_rate, int_phase_rate)
    
    def get_phase_rate(self, stream):
        """
        Retrieve the programmed phase rate in radians per spectra for a given stream.

        :param stream: ADC stream index from which the delay phase rate should be retrieved.
        :type stream: int

        :return: uint(phase_rate)
        """
        if stream > self.n_streams:
            self._error(f"""Tried to fetch phase rate for stream {stream} > n_streams ({self.n_streams})""")
        
        phase_reg_rate = f"""params{stream}_phase_rate"""
        val = self.read_uint(phase_reg_rate)

        #If greater than the most positive option for signed representation, it was negative:
        if val > (2**(self._PHASE_RATE_BW-1) -1):
            val -= 2**self._PHASE_RATE_BW

        return val, (2**self._PHASE_RATE_BP * self.RATE_SCALE_FACTOR * self.FINE_DELAY_LOAD_PERIOD)

    def set_phase_cal(self, stream, phases):
        """
        Set the phase calibration coefficients for a single input.

        :param stream: ADC stream index for which the calibration phases should be applied.
        :type stream: int

        :param phases: numpy array or list of phases to apply, in units of radians.
            phase[i] is the phase which should be applied to frequency channel i.
        :type phases: list or numpy.ndarray
        """

        phases = np.array(phases)
        assert len(phases) == self.n_chans, 'Phase calibration list must be %d elements long' % self.n_chans
        phases /= np.pi # Phases are in units of pi
        phases *= 2**self._CAL_PHASE_BP
        assert self._CAL_PHASE_BW % 8 == 0
        nbytes = self._CAL_PHASE_BW // 8
        dtype = '>i%d' % nbytes # big-endian signed int
        phases = np.array(phases, dtype=dtype)
        self.write('fd%d_fd_fs_mux_cal' % stream, phases.tobytes())

    def get_phase_cal(self, stream):
        """
        Get the phase calibration coefficients for a single input.

        :param stream: ADC stream index for which the calibration phases should be applied.
        :type stream: int

        :return phases: list of phases being applied, in units of radians.
            phase[i] is the phase which is applied to frequency channel i.
        :rtype: list
        """

        assert self._CAL_PHASE_BW % 8 == 0
        nbytes = self._CAL_PHASE_BW // 8
        dtype = '>i%d' % nbytes # big-endian signed int
        raw = self.read('fd%d_fd_fs_mux_cal' % stream, nbytes*self.n_chans)
        phases = np.fromstring(raw, dtype=dtype)
        return phases / 2**self._CAL_PHASE_BP * np.pi

    def get_firmware_slope(self, stream):
        """
        Retrieve the firmware reported slope in samples for a given stream.

        :param stream: ADC stream index for which the slope should be retrieved.
        :type stream: int

        :return: tuple of integer readout from stream-specific slope register with scaling
        """
        if stream > self.n_streams:
            self._error(f"""Tried to fetch slope for stream {stream} > n_streams ({self.n_streams})""")
        slope_reg = f"fd{stream}_slope"
        return self.read_int(slope_reg), 2**self._FIRMWARE_SLOPE_BP

    def get_firmware_phase(self, stream):
        """
        Retrieve the firmware reported phase in radians for a given stream.

        :param stream: ADC stream index for which the phase should be retrieved.
        :type stream: int

        :return: tuple of integer readout from stream-specific phase register with scaling
        """
        if stream > self.n_streams:
            self._error(f"""Tried to fetch phase for stream {stream} > n_streams ({self.n_streams})""")
        phase_reg = f"fd{stream}_phase"
        return self.read_int(phase_reg), 2**self._FIRMWARE_PHASE_BP
        
    def set_target_load_time(self, value, enable_trig=True):
        """
        Set the TT to `value` in units of FPGA clocks

        :param value: Telescope time to load in FPGA clocks
        :type value: int

        :param enable_trig: If True, enable the triggering of a sync pulse
            at this time. Else, set the load_time registers but don't
            enable the triggering system.
        :type enable_trig: bool

        """
        self.timer.set_target_tt(value, enable_trig=enable_trig)

    def force_load(self):
        """
        Force immediate load of all delays.
        """
        self.timer.force_pulse()
    
    def enable_load(self):
        """
        Enable the loading of values when target TT is reached
        """
        self.timer.enable_tt_pulse()

    def disable_load(self):
        """
        Disable the loading of values when target TT is reached
        """
        self.timer.disable_tt_pulse()

    def get_target_load_time(self):
        """
        Get currently set target load time in units of FPGA clocks.
        
        :return: target_tt
        :rtype: int
        """
        return self.timer.get_target_tt()
    
    def get_time_to_load(self):
        """
        Get number of FPGA clocks until load trigger.
        The returned value will be negative if the trigger time
        is in the past.
        
        :return: time_to_load (FPGA clocks)
        :rtype: int
        """
        return self.timer.get_time_to_load()

    def get_status(self):
        """
        Get status and error flag dictionaries.

        Status keys:

            - delay<``n``>: Currently loaded delay for ADC input index ``n``
              in units of ADC samples.
            - delayrate<``n``>: Currently loaded delay rate for ADC input index ``n``
              in units of ADC samples.
            - phase<``n``>: Currently loaded phase for ADC input index ``n``
              in units of ADC samples.
            - phaserate<``n``>: Currently loaded phase rate for ADC input index ``n``
              in units of ADC samples.
            - firmware_slope: The Firmware reported slope.
            - firmware_phase: The Firmware reported phase.
            - max_delay: The maximum delay supported by the firmware.
            - min_delay: The minimum delay supported by the firmware.
            - max_delay_rate: The maximum delay rate supported by the firmware.
            - min_delay_rate: The minimum delay rate supported by the firmware.
            - max_phase: The maximum phase supported by the firmware.
            - min_phase: The minimum phase supported by the firmware.
            - max_phase_rate: The maximum phase rate supported by the firmware.
            - min_phase_rate: The minimum phase rate supported by the firmware.
            - time_to_load: The contents of the timer.time_to_load register.

        :return: (status_dict, flags_dict) tuple. `status_dict` is a dictionary of
            status key-value pairs. flags_dict is
            a dictionary with all, or a sub-set, of the keys in `status_dict`. The values
            held in this dictionary are as defined in `error_levels.py` and indicate
            that values in the status dictionary are outside normal ranges.
        """
        stats, flags = self.timer.get_status()

        for stream in range(self.n_streams):
            stats[f"delay{stream}"] = self.get_delay(stream)
            stats[f"delayrate{stream}"] = self.get_delay_rate(stream)
            stats[f"phase{stream}"] = self.get_phase(stream)
            stats[f"phaserate{stream}"] = self.get_phase_rate(stream)
            stats["firmware_slope"] = self.get_firmware_slope(stream)
            stats["firmware_phase"] = self.get_firmware_phase(stream)
            
        stats["max_delay"] = self.MAX_DELAY
        stats["min_delay"] = self.MIN_DELAY
        stats["max_delay_rate"] = self.MAX_DELAY_RATE
        stats["min_delay_rate"] = self.MIN_DELAY_RATE
        stats["max_phase"] = self.MAX_PHASE
        stats["min_phase"] = self.MIN_PHASE
        stats["max_phase_rate"] = self.MAX_PHASE_RATE
        stats["min_phase_rate"] = self.MIN_PHASE_RATE
        stats["time_to_load"] = self.get_time_to_load()
        return stats,flags 
    
    def initialize(self, read_only=False):
        """
        Initialize the phase, phase rate, delay and delay rate for all streams.

        :param read_only: If True, do nothing. If False, initialize all
            phase steps and offsets to the minimum allowed value.
        :type read_only: bool

        """
        self.timer.initialize(read_only=read_only)
        if not read_only:
            for i in range(self.n_streams):
                self.set_phase_rate(i, 0.0)
                self.set_phase(i, 0.0)
                self.set_delay(i, 0.0)
                self.set_delay_rate(i, 0.0)
                self.set_phase_cal(i,np.zeros(self.n_chans))
            self.force_load()
