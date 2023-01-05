import time
from numpy import log2

from .block import Block

class Sync(Block):
    """
    The Sync block controls internal timing signals.

    :param host: CasperFpga interface for host.
    :type host: casperfpga.CasperFpga

    :param name: Name of block in Simulink hierarchy.
    :type name: str

    :param clk_hz: The FPGA clock rate at which the DSP fabric runs, in Hz.
    :type clk_hz: int

    :param logger: Logger instance to which log messages should be emitted.
    :type logger: logging.Logger
    """
    OFFSET_ACTIVE_HIGH = 0
    OFFSET_RST_TT_INT = 1
    OFFSET_MAN_LOAD_INT = 2
    OFFSET_TT_INT_LOAD_ARM = 3
    OFFSET_MAN_PPS = 4
    OFFSET_RST_TT = 5
    OFFSET_RST_ERR = 6
    OFFSET_ARM_SYNC_OUT = 7
    OFFSET_MAN_SYNC = 8
    OFFSET_ARM_NOISE = 9
    OFFSET_TT_LOAD_ARM = 10

    def __init__(self, host, name, clk_hz=None, logger=None):
        super(Sync, self).__init__(host, name, logger)
        self.clk_hz = clk_hz

        self.offset_ns = 0.0

        self.sync_wait_timeout_limit_s = 0.5
        self.sync_wait_sleep_period_s = 0.0005
    
    def uptime(self):
        """
        :return: Time in FPGA clock ticks since the FPGA was last programmed.
            Resolution is 2**32 (21 seconds at 200 MHz)

        :rtype: int
        """
        return self.read_uint('uptime_msb') << 32

    def period(self):
        """
        :return: The number of FPGA clock ticks between the last two external sync pulses.
        :rtype int:
        """
        return self.read_uint('ext_sync_period')+1

    def count_ext(self):
        """
        :return: Number of external sync pulses received.
        :rtype int:
        """
        return self.read_uint('ext_sync_count')

    #def count_pps(self):
    #    """
    #    :return: Number of external PPS pulses received.
    #    :rtype int:
    #    """
    #    return self.read_uint('ext_pps_count')

    #def count_int(self):
    #    """
    #    :return: Number of internal sync pulses received.
    #    :rtype int:
    #    """
    #    return self.read_uint('int_sync_count')

    def get_latency(self):
        """
        :return: Number of FPGA clock ticks between sync transmission and reception
        :rtype int:
        """
        return self.read_uint('latency') & 0xff

    def get_error_count(self):
        """
        :return: Number of sync errors.
        :rtype int:
        """
        return self.read_uint('latency') >> 8

    def reset_error_count(self):
        """
        Reset internal error counter to 0.
        """
        self.change_reg_bits('ctrl', 0, self.OFFSET_RST_ERR)
        self.change_reg_bits('ctrl', 1, self.OFFSET_RST_ERR)
        self.change_reg_bits('ctrl', 0, self.OFFSET_RST_ERR)
    
    def wait_for_sync(self):
        """
        Block until a sync has been received.
        """
        tstart = time.time()
        ttimeout = tstart + self.sync_wait_timeout_limit_s
        c = self.count_ext()
        while(self.count_ext() == c):
            if time.time() > ttimeout:
                self._warning("Timed out waiting for sync pulse")
                break
            time.sleep(self.sync_wait_sleep_period_s)

    #def wait_for_pps(self, timeout=2.0):
    #    """
    #    Block until a PPS has been received.

    #    :param timeout: Timeout, in seconds, to wait.
    #    :type timeout: float

    #    :return: least-significant 32-bits of telescope time of
    #      last PPS pulse. Or, -1, on timeout.
    #    :rtype int:
    #    """
    #    t0 = time.time()
    #    c0 = self.read_uint('tt_lsb')
    #    c1 = self.read_uint('tt_lsb')
    #    while(c1 == c0):
    #        c1 = self.read_uint('tt_lsb')
    #        if time.time() > (t0 + timeout):
    #            self._warning("Timed out waiting for PPS")
    #            return -1
    #        time.sleep(0.05)
    #    return c1

    def arm_sync(self, wait=True):
        """
        Arm sync pulse generator, which passes sync pulses to the
        design DSP.

        :param wait: If True, wait for a sync to pass before returning.
        :type wait: bool
        """
        self.change_reg_bits('ctrl', 0, self.OFFSET_ARM_SYNC_OUT)
        self.change_reg_bits('ctrl', 1, self.OFFSET_ARM_SYNC_OUT)
        self.change_reg_bits('ctrl', 0, self.OFFSET_ARM_SYNC_OUT)
        if wait:
            self.wait_for_sync()
            time.sleep(0.2) # The latest firmware doesn't sync immediately on the pulse

    def arm_noise(self):
        """
        Arm noise generator resets.
        """
        self.change_reg_bits('ctrl', 0, self.OFFSET_ARM_NOISE)
        self.change_reg_bits('ctrl', 1, self.OFFSET_ARM_NOISE)
        self.change_reg_bits('ctrl', 0, self.OFFSET_ARM_NOISE)

    def sw_sync(self):
        """
        Issue a sync pulse from software. This will only do anything
        if appropriate arming commands have been made in advance.
        """
        self.change_reg_bits('ctrl', 0, self.OFFSET_MAN_SYNC)
        self.change_reg_bits('ctrl', 1, self.OFFSET_MAN_SYNC)
        self.change_reg_bits('ctrl', 0, self.OFFSET_MAN_SYNC)
        time.sleep(0.2) # Ensure the sync has propagated

    #def set_output_sync_rate(self, mask):
    #    """
    #    Set the output sync generation rate. A sync is issued
    #    when the lower 32-bits of the telescope time counter,
    #    masked with ``~mask`` == 0. I.e., a mask of 0 will
    #    cause a sync every 2^32 clock cycles. A mask of 0xffff0000
    #    will create an output pulse every 2^16 clock cycles.
    #    Output sync pulses are extended by 256 clocks, so the output pulse rate
    #    should be lower than this.

    #    :param mask: Mask with which to bitwise AND the telescope time
    #        counter before comparing to 0.
    #    :type mask: int
    #    """
    #    self.write_int('tt_mask', mask)

    #def update_telescope_time(self, fs_hz=None):
    #    """
    #    Arm PPS trigger receivers,
    #    having loaded an appropriate telescope time.

    #    :param fs_hz: The FPGA DSP clock rate, in Hz. Used to set the
    #        telescope time counter. If None is provided, self.clk_hz will be used.
    #    :type fs_hz: int

    #    """
    #    fs_hz = fs_hz or self.clk_hz
    #    if fs_hz is None:
    #        self.logger.error('No FPGA clock rate was provided!')
    #        raise
    #    x = self.wait_for_pps()
    #    has_pps = (x >= 0)
    #    if not has_pps:
    #        # Timed out, probably because this isn't the TT SNAP2 with PPS
    #        self._info("Skipping telescope time update, because this board doesn't have a PPS")
    #        return
    #    now = time.time()
    #    next_pps = int(now) + 1
    #    self._info("Loading new telescope time at %s" % time.ctime(next_pps))
    #    target_tt = int(next_pps * fs_hz)
    #    delay = next_pps - time.time()
    #    if delay < 0.2:
    #        self._error("Took too long to generate software sync")
    #    self.load_telescope_time(target_tt, software_load=False)
    #    loaded_time = time.time()
    #    spare = next_pps - loaded_time
    #    if spare < 0.2:
    #        self._warning("TT loaded with only %.2f seconds to spare" % spare)
    #    if spare < 0:
    #        self._error("TT loaded after the expected PPS arrival!")
    #    # Now wait for a PPS so that the TT will have been loaded before anything else happend
    #    if has_pps:
    #        self.wait_for_pps()

    #def reset_telescope_time(self):
    #    """
    #    Reset the telescope time counter to 0 immediately.
    #    """
    #    self.change_reg_bits('ctrl', 0, self.OFFSET_RST_TT)
    #    self.change_reg_bits('ctrl', 1, self.OFFSET_RST_TT)
    #    self.change_reg_bits('ctrl', 0, self.OFFSET_RST_TT)

    #def load_telescope_time(self, tt, software_load=False):
    #    """
    #    Load a new starting value into the telescope time counter on the
    #    next PPS.

    #    :param tt: Telescope time to load
    #    :type tt: int

    #    :param software_load: If True, immediately load via a software trigger. Else
    #        load on the next PPS arrival.
    #    :type software_load: bool
    #    """
    #    assert tt < 2**64 - 1
    #    self.write_int('tt_load_msb', tt >> 32)
    #    self.write_int('tt_load_lsb', tt & 0xffffffff)
    #    self.change_reg_bits('ctrl', 0, self.OFFSET_TT_LOAD_ARM)
    #    self.change_reg_bits('ctrl', 1, self.OFFSET_TT_LOAD_ARM)
    #    self.change_reg_bits('ctrl', 0, self.OFFSET_TT_LOAD_ARM)
    #    if software_load:
    #        self.change_reg_bits('ctrl', 0, self.OFFSET_MAN_PPS)
    #        self.change_reg_bits('ctrl', 1, self.OFFSET_MAN_PPS)
    #        self.change_reg_bits('ctrl', 0, self.OFFSET_MAN_PPS)

    def load_internal_time(self, tt, software_load=False):
        """
        Load a new starting value into the _internal_ telescope time counter on the
        next sync.

        :param tt: Telescope time to load
        :type tt: int

        :param software_load: If True, immediately load via a software trigger. Else
            load on the next external sync pulse arrival.
        :type software_load: bool
        """
        assert tt < 2**64 - 1
        self.write_int('int_tt_load_msb', tt >> 32)
        self.write_int('int_tt_load_lsb', tt & 0xffffffff)
        self.change_reg_bits('ctrl', 0, self.OFFSET_TT_INT_LOAD_ARM)
        self.change_reg_bits('ctrl', 1, self.OFFSET_TT_INT_LOAD_ARM)
        self.change_reg_bits('ctrl', 0, self.OFFSET_TT_INT_LOAD_ARM)
        if software_load:
            self.change_reg_bits('ctrl', 0, self.OFFSET_MAN_LOAD_INT)
            self.change_reg_bits('ctrl', 1, self.OFFSET_MAN_LOAD_INT)
            self.change_reg_bits('ctrl', 0, self.OFFSET_MAN_LOAD_INT)

    def get_tt_of_ext_sync(self):
        """
        Get the internal TT at which the last sync pulse arrived.

        :return: (tt, sync_number). ``tt`` is the internal TT of the last sync.
            ``sync_number`` is the sync pulse count corresponding to this TT.
        :rtype int:
        """
        # wait for a pulse so we are less likely to read over a boundary
        self.wait_for_sync()
        sync_number = self.count_ext()
        tt = (self.read_uint('ext_sync_tt_msb') << 32) + self.read_uint('ext_sync_tt_lsb')
        sync_number_reread = self.count_ext()
        if sync_number_reread != sync_number:
            self._error("Failed to read TT without being interrupted by a sync. Is the sync rate very high?")
            raise RuntimeError
        return tt, sync_number

    def get_tt_of_sync(self):
        """
        Get the internal TT of the last system sync event.

        :return: tt. The internal TT of the last sync.
        :rtype int:
        """
        tt = (self.read_uint('tt_sync_msb') << 32) + self.read_uint('tt_sync_lsb')
        return tt

    def update_internal_time(self, fs_hz=None, offset_ns=0.0, sync_clock_factor=1):
        """
        Arm sync trigger receivers,
        having loaded an appropriate telescope time.

        :param fs_hz: The FPGA DSP clock rate, in Hz. Used to set the
            telescope time counter. If None is provided, self.clk_hz will be used.
        :type fs_hz: int

        :param offset_ns: Nanoseconds offset to add to the time loaded into the
            internal telescope time counter.
        :type offset_ns: float

        :return: next_sync_clocks: The value of the TT counter at the arrival
            of the next sync pulse. Or, `None`, if the TT counter was loaded
            late.
        :rtype int:

        """

        fs_hz = fs_hz or self.clk_hz
        if fs_hz is None:
            self.logger.error('No FPGA clock rate was provided!')
            raise

        # Figure out sync rate
        tt0, sync0 = self.get_tt_of_ext_sync()
        tt1, sync1 = self.get_tt_of_ext_sync()
        if sync0 == sync1:
            message = f'No sync pulse was detected over {self.sync_wait_timeout_limit_s} seconds.'
            self.logger.error(message)
            raise RuntimeError(message)

        sync_period = (tt1 - tt0) / (sync1 - sync0)
        self._info("Detected sync period %.1f (2^%.1f) clocks" % (sync_period, log2(sync_period)))
        sync_period = int(sync_period)
        sync_period_s = sync_period / fs_hz
        sync_period_ms = 1000*sync_period_s
        sync_period_us = 1000000*sync_period_s
        self._info("Detected sync period is %.3f milliseconds" % (sync_period_ms))
        # Check the offset of a sync from NTP time
        self.wait_for_sync()
        ntp_us = 1000000*time.time()
        ntp_offset_us = int(ntp_us) % 1000000 # offset from NTP 1s boundary in microsec
        ntp_offset_f = (ntp_offset_us / sync_period_us) % 1 # fraction of a period offset
        self._info("NTP offset usecs: ntp_offset_us: %d" % ntp_offset_us)
        # Wrap fractional offsets
        if ntp_offset_f > 0.5:
            ntp_offset_f -= 1
        self._info("Last sync pulse arrived at time %.5f" % (ntp_us / 1e6))
        self._info("Sync pulses offset from NTP by %d us" % (ntp_offset_f * sync_period_us))
        if abs(ntp_offset_f) > 0.1:
            self._warning("Sync pulses offset from NTP by %.2f of a period" % ntp_offset_f)
        
        # We assume that the master TT is tracking clocks since unix epoch.
        # Syncs should come every `sync_period` ADC clocks
        self.wait_for_sync()
        now = time.time()
        now_clocks = int(now * fs_hz)
        next_sync_clocks = int(round((now_clocks / sync_period))) + 1 
        next_sync_clocks *= sync_period
        next_sync = next_sync_clocks / fs_hz

        # Wait for 20% of a sync period
        time.sleep(sync_period_s * 0.2) # Earlier warning is issued if NTP offset > 10% of a period

        delay = next_sync - time.time()
        if delay < (sync_period_s / 4): # Must load at least 1/4 period before sync
            self._error("Took too long to configure telescope time register")
        offset_samples = offset_ns * (fs_hz*1e-9)
        offset_samples_aligned = round(offset_samples/sync_clock_factor) * sync_clock_factor # maintain factor
        self.offset_ns = offset_samples_aligned / (fs_hz*1e-9)

        self._info(
            "Offset of {} ns ({} samples) applied (requested {} ns ({} samples), rounded the nearest multiple of {} samples)".format(
            self.offset_ns, offset_samples_aligned,
            offset_ns, offset_samples,
            sync_clock_factor
        ))

        next_sync_clocks = int(next_sync_clocks + offset_samples_aligned)

        self.load_internal_time(next_sync_clocks+1, software_load=False) # +1 because counter loads clock after sync
        loaded_time = time.time()
        spare = next_sync - loaded_time + ((ntp_offset_f * sync_period_us)/ 1e6)
        #self._info("Next sync time: %.3f" % next_sync)
        #self._info("Loaded time: %.3f" % loaded_time)
        #self._info("NTP offset: %.5f" % (ntp_offset_us/1e6))
        self._info("Loaded new telescope time (%d) for %s (%.4f)" % (next_sync_clocks, time.ctime(next_sync), next_sync))
        self._info("Load completed at %.4f" % loaded_time)
        # Wait for a sync to pass so the TT is laoded before anything else happens
        self.wait_for_sync()
        if spare < 0:
            self._error("Internal TT loaded after the expected sync arrival!")
            return None
        if spare < sync_period_s / 4: # Must have loaded at least 1/4 period before sync
            self._warning("Internal TT loaded with only %.2f milliseconds to spare" % (1000*spare))
        else:
            self._info("Internal TT loaded with %.2f milliseconds to spare" % (1000*spare))
        return next_sync_clocks

    def get_status(self):
        """
        Get status and error flag dictionaries.

        Status keys:

            - uptime_fpga_clks (int) : Number of FPGA clock ticks (= ADC clock ticks)
              since the FPGA was last programmed.

            - period_fpga_clks (int) : Number of FPGA clock ticks (= ADC clock ticks)
              between the last two internal sync pulses.

            - ext_count (int) : The number of external sync pulses since the FPGA
              was last programmed.

            - int_count (int) : The number of internal sync pulses since the FPGA
              was last programmed.

        :return: (status_dict, flags_dict) tuple. `status_dict` is a dictionary of
            status key-value pairs. flags_dict is
            a dictionary with all, or a sub-set, of the keys in `status_dict`. The values
            held in this dictionary are as defined in `error_levels.py` and indicate
            that values in the status dictionary are outside normal ranges.
        """
        stats = {}
        flags = {}
        stats['uptime_fpga_clks'] = self.uptime()
        stats['period_fpga_clks'] = self.period()
        stats['ext_count'] = self.count_ext()
        #stats['int_count'] = self.count_int()
        return stats, flags

    def initialize(self, read_only=False):
        """
        Initialize block.

        :param read_only: If False, initialize system control register to 0
            and reset error counters. If True, do nothing.
        :type read_only: bool

        """
        if read_only:
            pass
        else:
            self.write_int('ctrl', 0)
            # Set output pulse rate to 1 per 2**29 clocks (every ~2.7 seconds)
            #self.set_output_sync_rate(0xe0000000)
            self.reset_error_count()
