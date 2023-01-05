import time

from .block import Block

class TimedPulse(Block):
    """
    The TimedPulse block controls the output of pulses which
    are locked to telescope time (TT).

    :param host: CasperFpga interface for host.
    :type host: casperfpga.CasperFpga

    :param name: Name of block in Simulink hierarchy.
    :type name: str

    :param clk_hz: The FPGA clock rate at which the DSP fabric runs, in Hz.
    :type clk_hz: int

    :param logger: Logger instance to which log messages should be emitted.
    :type logger: logging.Logger
    """
    OFFSET_TRIG_EN = 1
    OFFSET_TRIG_FORCE = 0

    def __init__(self, host, name, logger=None):
        super(TimedPulse, self).__init__(host, name, logger)

    def enable_tt_pulse(self):
        """
        Enable output sync pulse when target TT is reached
        """
        self.change_reg_bits('ctrl', 1, self.OFFSET_TRIG_EN)

    def disable_tt_pulse(self):
        """
        Disable output sync pulse when target TT is reached
        """
        self.change_reg_bits('ctrl', 0, self.OFFSET_TRIG_EN)

    def force_pulse(self):
        """
        Force an output pulse immediately, with no deterministic
        relationship to TT.
        """
        self.change_reg_bits('ctrl', 1, self.OFFSET_TRIG_FORCE)
        self.change_reg_bits('ctrl', 0, self.OFFSET_TRIG_FORCE)

    def set_target_tt(self, tt, enable_trig=True):
        """
        Load a new target TT

        :param tt: Telescope time to load
        :type tt: int

        :param enable_trig: If True, enable the triggering of a sync pulse
            at this time. Else, set the load_time registers but don't
            enable the triggering system.
        :type enable_trig: bool

        """
        assert tt < 2**64
        assert tt >= 0
        self.write_int('target_load_time_msb', tt >> 32)
        self.write_int('target_load_time_lsb', tt & 0xffffffff)
        if enable_trig:
            self.enable_tt_pulse()

    def get_target_tt(self):
        """
        Get currently set target load time.
        
        :return: target_tt
        :rtype: int
        """
        lsb = self.read_uint('target_load_time_lsb')
        msb = self.read_uint('target_load_time_msb')
        v = (msb << 32) + lsb
        return v

    def get_time_to_load(self):
        """
        Get number of FPGA clocks until load trigger.
        The returned value will be negative if the trigger time
        is in the past.
        
        :return: time_to_load
        :rtype: int
        """
        lsb = self.read_uint('time_to_load_lsb')
        msb = self.read_uint('time_to_load_msb')
        v = (msb << 32) + lsb
        if v > (2**63 - 1):
            v -= 2**64
        return v

    def get_fpga_time(self, fpga_clock_rate_hz=None):
        """
        Get the current FPGA time in FPGA clocks. If
        fpga_clock_rate_hz is provided, return time as a
        date-time string.

        :param fpga_clock_rate_hz: The FPGA clock rate in Hz
        :type fpga_clock_rate_hz: float

        :return: telescope_time
        :rtype: int | str
        """

        fpga_clk_difference = self.get_target_tt() - self.get_time_to_load()
        return fpga_clk_difference if fpga_clock_rate_hz is None else time.ctime(fpga_clk_difference/fpga_clock_rate_hz)

    def get_force_state(self):
        """
        Get the state of the "force_pulse" control flag.

        :return: force_state
        :rtype: bool
        """
        return bool(self.get_reg_bits('ctrl', self.OFFSET_TRIG_FORCE))

    def get_enable_state(self):
        """
        Get the state of the "trigger enable" control flag.

        :return: enable_state
        :rtype: bool
        """
        return bool(self.get_reg_bits('ctrl', self.OFFSET_TRIG_EN))


    def get_status(self):
        """
        Get status and error flag dictionaries.

        Status keys:

            - target_load_time (int) : Currently set target load time, in FPGA clocks.

            - time_to_load (int) : Currently reported time until load, in FPGA clocks.

            - fpga_time (str) : The FPGA telescope time as a date-time string.

            - is_enabled (bool) : The enable state of the triggered sync logic

            - is_forced (bool) : The state of the force load flag

        :return: (status_dict, flags_dict) tuple. `status_dict` is a dictionary of
            status key-value pairs. flags_dict is
            a dictionary with all, or a sub-set, of the keys in `status_dict`. The values
            held in this dictionary are as defined in `error_levels.py` and indicate
            that values in the status dictionary are outside normal ranges.
        """
        stats = {}
        flags = {}
        stats['target_load_time'] = self.get_target_tt()
        stats['time_to_load'] = self.get_time_to_load()
        stats['fpga_time'] = self.get_fpga_time(fpga_clock_rate_hz=256e6)
        stats['is_enabled'] = self.get_enable_state()
        stats['is_forced'] = self.get_force_state()
        if stats['is_forced']:
            flags['is_forced'] = FENG_NOTIFY
        return stats, flags

    def initialize(self, read_only=False):
        """
        Initialize block.

        :param read_only: If False, initialize control flags to disable state.
            If True, do nothing.
        :type read_only: bool

        """
        if read_only:
            pass
        else:
            self.write_int('ctrl', 0)
