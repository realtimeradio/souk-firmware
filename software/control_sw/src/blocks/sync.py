import time
from numpy import log2

from .block import Block
from souk_mkid_readout.error_levels import *

class Sync(Block):
    """
    The Sync block controls internal timing signals.

    It has two timing components, the first is an "Internal Telescope Time (TT)" counter.
    This counter is synchronized to an external time reference (typically PPS) and maintains
    a count of FPGA clock ticks since the UNIX epoch.

    The second component is the output synchronization logic, which resets a DSP processing
    pipeline.

    A typical synchronization flow is:

    1. `initialize()` -- Perform basic firmware initialization.
    2. `update_internal_time()` -- Set the TT counter to the correct value on the next PPS edge.
    3. `set_timed_sync(mrst=True)` -- Issue a reset and start trigger to downstream logic at an appropriate time.
    4. [Optional] Periodically call `arm_sync()` and observe TT vs PPS drift with `get_drift()`.
    
    If no external synchronization sources are present a typical flow is:

    1. `initialize()` -- Perform basic firmware initialization.
    2. `sw_sync(mrst=True)` -- issue an immediate reset and start trigger to downstream logic.

    In this flow, timestamps from the system are not meaningful.


    :param host: CasperFpga interface for host.
    :type host: casperfpga.CasperFpga

    :param name: Name of block in Simulink hierarchy.
    :type name: str

    :param clk_hz: The FPGA clock rate at which the DSP fabric runs, in Hz.
    :type clk_hz: int

    :param sync_delay: The initial delay to load for the delayed sync output in FPGA clock cycles
    :type sync_delay: int

    :param logger: Logger instance to which log messages should be emitted.
    :type logger: logging.Logger
    """
    OFFSET_MRST = 0
    OFFSET_ACTIVE_HIGH = 1
    OFFSET_RST_TT_INT = 2
    OFFSET_MAN_LOAD_INT = 3
    OFFSET_TT_INT_LOAD_ARM = 4
    OFFSET_MAN_PPS = 5
    OFFSET_RST_TT = 6
    OFFSET_RST_ERR = 7
    OFFSET_ARM_SYNC_OUT = 8
    OFFSET_MAN_SYNC = 9
    OFFSET_ARM_NOISE = 10
    OFFSET_TT_LOAD_ARM = 11
    OFFSET_ENABLE_LOOPBACK = 12
    OFFSET_ENABLE_ERR_FLAG = 13

    OFFSET_TIMED_SYNC_SW_SYNC = 1
    OFFSET_TIMED_SYNC_EN = 0

    def __init__(self, host, name, clk_hz=None, sync_delay=1, logger=None):
        super(Sync, self).__init__(host, name, logger)
        self.clk_hz = clk_hz

        self.offset_ns = 0.0

        self.sync_wait_timeout_limit_s = 1.2
        self.sync_wait_sleep_period_s = 0.0005
        self._default_sync_delay = sync_delay
    
    def uptime(self):
        """
        :return: Time in FPGA clock ticks since the FPGA was last programmed.

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

    def get_error_count(self):
        """
        :return: Number of sync errors.
        :rtype: int
        """
        return self.read_uint('error')

    def reset_error_count(self):
        """
        Reset internal error counter to 0.
        """
        self.change_reg_bits('ctrl', 0, self.OFFSET_RST_ERR)
        self.change_reg_bits('ctrl', 1, self.OFFSET_RST_ERR)
        self.change_reg_bits('ctrl', 0, self.OFFSET_RST_ERR)

    def set_sync_active_high(self):
        """
        Set the sync pulse to active on a positive edge.
        """
        self.change_reg_bits('ctrl', 1, self.OFFSET_ACTIVE_HIGH)

    def set_sync_active_low(self):
        """
        Set the sync pulse to active on a negative edge.
        """
        self.change_reg_bits('ctrl', 0, self.OFFSET_ACTIVE_HIGH)

    def assert_mrst(self):
        """
        Assert reset.
        """
        self.change_reg_bits('ctrl', 1, self.OFFSET_MRST)

    def deassert_mrst(self):
        """
        Deassert reset.
        """
        self.change_reg_bits('ctrl', 0, self.OFFSET_MRST)

    def get_time_to_sync(self):
        """
        Return the number of FPGA clock ticks until the
        timed sync event.
        
        :return: FPGA clock ticks until sync. Saturates
                 at +/- 2**31
        """
        return self.read_int('time_to_sync')

    def enable_timed_sync(self):
        """
        Enable timed sync with TT equals the loaded target time.
        """
        self.change_reg_bits('timed_sync_ctrl', 1, self.OFFSET_TIMED_SYNC_EN)

    def disable_timed_sync(self):
        """
        Disable timed sync with TT equals the loaded target time.
        """
        self.change_reg_bits('timed_sync_ctrl', 0, self.OFFSET_TIMED_SYNC_EN)

    def set_timed_sync(self, tt=None, wait=False, mrst=True):
        """
        Set the timed sync for telescope time `TT`.

        :param tt: Telescope time, in FPGA clock ticks since UNIX epoch,
                   at which sync should be issued.
        :param mrst: If True, issue reset prior to sync.
        :param wait: If True, wait for the sync to pass, else return
                     straight away.
        """
        self.assert_mrst()
        self.deassert_mrst()
        self.disable_timed_sync()
        self.write_int('timed_sync_msb', (tt >> 32) & 0xffffffff)
        self.write_int('timed_sync_enable', 1)
        self.enable_timed_sync()
        time_to_sync = self.get_time_to_sync()
        self.log.info(f'Time until sync is {time_to_sync} clocks')
        if time_to_sync < 0:
            self.error('Target sync time is in the past!')
            raise RuntimeError
        if wait:
            self.log.info('Waiting for sync to pass')
            while(self.get_time_to_sync() > 0):
                time.sleep(0.25)

    def enable_error_flag(self):
        """
        Enable error flag.
        """
        self.change_reg_bits('ctrl', 1, self.OFFSET_ENABLE_ERR_FLAG)

    def disable_error_flag(self):
        """
        Disable error flag.
        """
        self.change_reg_bits('ctrl', 0, self.OFFSET_ENABLE_ERR_FLAG)
    
    def wait_for_sync(self):
        """
        Block until a sync has been received.
        """
        tstart = time.time()
        ttimeout = tstart + self.sync_wait_timeout_limit_s
        c = self.count_ext()
        while(self.count_ext() == c):
            if time.time() > ttimeout:
                self.logger.warning("Timed out waiting for sync pulse")
                break
            time.sleep(self.sync_wait_sleep_period_s)

    def set_delay(self, delay):
        """
        Set the delay of the delayed sync output

        :param delay: Delay in FPGA clock cycles
        :type delay: int
        """
        self.write_int('sync_delay', delay)

    def get_delay(self):
        """
        Get the delay of the delayed sync output, in FPGA clock cycles

        :return: Delay in FPGA clock cycles
        :rtype: int
        """
        return self.read_uint('sync_delay')

    def get_pipeline_latency(self):
        """
        Get the difference in arrival time of a sync pulse at the start of the RX chain
        and at the end of the TX chain, in units of FPGA clock cycles.
        Depending on the `mix` block signal sharing settings, this is either the total
        latency (when the TX pipeline sync is shared with the RX pipeline sync) or
        is the residual skew when the RX pipeline sync is a delayed copy of the TX sync.

        :return: Sync time difference, in FPGA clock cycles
        :rtype: int
        """
        delay = self.get_delay()
        latency = self.read_uint('pipeline_latency')
        return latency - delay

    def get_drift(self):
        """
        Get the drift observed between the time determined by a counter reset on the
        last `arm` call, and the internal telescope time, updated with `update_internal_time`
        based on external synchronization pulses.

        If the drift measurement changes during read, throw a RuntimeError.

        :return: drift, in FPGA clock cycles
        :rtype: int
        """
        msb = self.read_int('drift_msb')
        lsb = self.read_uint('drift_lsb')
        if self.read_int('drift_msb') != msb:
            self.logger.error('Drift count MSBs changed during LSB read')
            raise RuntimeError
        return (msb * 2**32) + lsb

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
    #            self.logger.warning("Timed out waiting for PPS")
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

    def sw_sync(self, wait=True, mrst=True):
        """
        Issue a sync pulse from software. This will only do anything
        if appropriate arming commands have been made in advance.

        :param wait: If True, wait 50ms for a sync to propagate before returning.
        :type wait: bool

        :param mrst: If True, issue a reset pulse prior to sync.
        :type mrst: bool
        """
        if mrst:
            self.deassert_mrst()
        self.change_reg_bits('timed_sync_ctrl', 0, self.OFFSET_TIMED_SYNC_SW_SYNC)
        if mrst:
            self.assert_mrst()
            self.deassert_mrst()
        self.change_reg_bits('timed_sync_ctrl', 1, self.OFFSET_TIMED_SYNC_SW_SYNC)
        self.change_reg_bits('timed_sync_ctrl', 0, self.OFFSET_TIMED_SYNC_SW_SYNC)
        if wait:
            time.sleep(0.05) # Ensure the sync has propagated

    def sw_pps(self, wait=True):
        """
        Issue a PPS pulse from software. This can be used to
        set the telescope time when no PPS signal is connected.
        This will only do anything if sw_arm has been called in advance.
        """
        self.change_reg_bits('ctrl', 0, self.OFFSET_MAN_SYNC)
        self.change_reg_bits('ctrl', 1, self.OFFSET_MAN_SYNC)
        self.change_reg_bits('ctrl', 0, self.OFFSET_MAN_SYNC)
        if wait:
            time.sleep(0.05) # Ensure the sync has propagated

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
            self.change_reg_bits('ctrl', 0, self.OFFSET_MAN_SYNC)
            self.change_reg_bits('ctrl', 1, self.OFFSET_MAN_SYNC)
            self.change_reg_bits('ctrl', 0, self.OFFSET_MAN_SYNC)

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
            self.logger.error("Failed to read TT without being interrupted by a sync. Is the sync rate very high?")
            raise RuntimeError
        return tt, sync_number

    def get_tt_of_sync(self):
        """
        Get the internal TT of the last system sync event.

        :return: tt. The internal TT of the last sync.
        :rtype: int
        """
        tt = (self.read_uint('tt_sync_msb') << 32) + self.read_uint('tt_sync_lsb')
        return tt

    def update_internal_time(self, clk_hz=None, sync_period=None, offset_ns=0.0, sync_clock_factor=1):
        """
        Arm sync trigger receivers,
        having loaded an appropriate telescope time.

        :param clk_hz: The FPGA DSP clock rate, in Hz. Used to set the
            telescope time counter. If None is provided, self.clk_hz will be used.
        :type clk_hz: int

        :param sync_period: Sync pulse period, in FPGA clock ticks. If None, read
            period from FPGA counters.

        :param offset_ns: Nanoseconds offset to add to the time loaded into the
            internal telescope time counter.
        :type offset_ns: float

        :return: next_sync_clocks: The value of the TT counter at the arrival
            of the next sync pulse. Or, `None`, if the TT counter was loaded
            late.
        :rtype int:

        """

        clk_hz = clk_hz or self.clk_hz
        if clk_hz is None:
            self.logger.error('No FPGA clock rate was provided!')
            raise

        # Figure out sync rate
        tt0, sync0 = self.get_tt_of_ext_sync()
        tt1, sync1 = self.get_tt_of_ext_sync()
        if sync0 == sync1:
            message = f'No sync pulse was detected over {self.sync_wait_timeout_limit_s} seconds.'
            self.logger.error(message)
            raise RuntimeError(message)

        sync_period_detect = (tt1 - tt0) / (sync1 - sync0)
        self.logger.info("Detected sync period %.1f (2^%.1f) clocks" % (sync_period_detect, log2(sync_period_detect)))
        if sync_period is None:
            sync_period = sync_period_detect
        else:
            self.logger.info("Using provided sync period of %d clocks" % sync_period)
            delta = abs(sync_period - sync_period_detect) / sync_period
            self.logger.info("Measured sync period differs from provided by %.3f%%" % (delta * 100))
        sync_period = int(sync_period)
        sync_period_s = sync_period / clk_hz
        sync_period_ms = 1000*sync_period_s
        sync_period_us = 1000000*sync_period_s
        self.logger.info("Detected sync period is %.3f milliseconds" % (sync_period_ms))
        # Check the offset of a sync from NTP time
        self.wait_for_sync()
        ntp_us = 1000000*time.time()
        ntp_offset_us = int(ntp_us) % 1000000 # offset from NTP 1s boundary in microsec
        ntp_offset_f = (ntp_offset_us / sync_period_us) % 1 # fraction of a period offset
        self.logger.info("NTP offset usecs: ntp_offset_us: %d" % ntp_offset_us)
        # Wrap fractional offsets
        if ntp_offset_f > 0.5:
            ntp_offset_f -= 1
        self.logger.info("Last sync pulse arrived at time %.5f" % (ntp_us / 1e6))
        self.logger.info("Sync pulses offset from NTP by %d us" % (ntp_offset_f * sync_period_us))
        if abs(ntp_offset_f) > 0.1:
            self.logger.warning("Sync pulses offset from NTP by %.2f of a period" % ntp_offset_f)
        
        # We assume that the master TT is tracking clocks since unix epoch.
        # Syncs should come every `sync_period` ADC clocks
        self.wait_for_sync()
        now = time.time()
        now_clocks = int(now * clk_hz)
        next_sync_clocks = int(round((now_clocks / sync_period))) + 1 
        next_sync_clocks *= sync_period
        next_sync = next_sync_clocks / clk_hz

        # Wait for 20% of a sync period
        time.sleep(sync_period_s * 0.2) # Earlier warning is issued if NTP offset > 10% of a period

        delay = next_sync - time.time()
        if delay < (sync_period_s / 4): # Must load at least 1/4 period before sync
            self.logger.error("Took too long to configure telescope time register")
        offset_samples = offset_ns * (clk_hz*1e-9)
        offset_samples_aligned = round(offset_samples/sync_clock_factor) * sync_clock_factor # maintain factor
        self.offset_ns = offset_samples_aligned / (clk_hz*1e-9)

        self.logger.info(
            "Offset of {} ns ({} samples) applied (requested {} ns ({} samples), rounded the nearest multiple of {} samples)".format(
            self.offset_ns, offset_samples_aligned,
            offset_ns, offset_samples,
            sync_clock_factor
        ))

        next_sync_clocks = int(next_sync_clocks + offset_samples_aligned)

        self.load_internal_time(next_sync_clocks+1, software_load=False) # +1 because counter loads clock after sync
        loaded_time = time.time()
        spare = next_sync - loaded_time + ((ntp_offset_f * sync_period_us)/ 1e6)
        #self.logger.info("Next sync time: %.3f" % next_sync)
        #self.logger.info("Loaded time: %.3f" % loaded_time)
        #self.logger.info("NTP offset: %.5f" % (ntp_offset_us/1e6))
        self.logger.info("Loaded new telescope time (%d) for %s (%.4f)" % (next_sync_clocks, time.ctime(next_sync), next_sync))
        self.logger.info("Load completed at %.4f" % loaded_time)
        # Wait for a sync to pass so the TT is laoded before anything else happens
        self.wait_for_sync()
        if spare < 0:
            self.logger.error("Internal TT loaded after the expected sync arrival!")
            return None
        if spare < sync_period_s / 4: # Must have loaded at least 1/4 period before sync
            self.logger.warning("Internal TT loaded with only %.2f milliseconds to spare" % (1000*spare))
        else:
            self.logger.info("Internal TT loaded with %.2f milliseconds to spare" % (1000*spare))
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

            - sync_delay (int) : The number of FPGA clock cycles between the RX and TX sync pulses.

            - drift (int) : The number of FPGA clock cycles of drift measured between the last SYNC and PPS

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
        stats['sync_delay'] = self.get_delay()
        stats['ext_count'] = self.count_ext()
        stats['error_count'] = self.get_error_count()
        stats['drift'] = self.get_drift()
        if stats['error_count'] != 0:
            flags['error_count'] = FENG_WARNING
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
            self.set_sync_active_high()
            self.enable_error_flag()
            self.reset_error_count()
            self.set_delay(self._default_sync_delay)
