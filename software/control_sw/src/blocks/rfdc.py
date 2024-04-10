import socket
import time
import datetime

from .block import Block
from souk_mkid_readout.error_levels import *

class Rfdc(Block):
    """
    Instantiate a control interface for an RFDC firmware block.

    :param host: CasperFpga interface for host.
    :type host: casperfpga.CasperFpga

    :param name: Name of block in Simulink hierarchy.
    :type name: str

    :param logger: Logger instance to which log messages should be emitted.
    :type logger: logging.Logger

    :param lmkfile: LMK configuration file to load to board's PLL chip
    :type lmkfile: str

    :param lmxfile: LMX configuration file to load to board's PLL chip
    :type lmxfile: str

    """
    def __init__(self, host, name, logger=None, lmkfile=None, lmxfile=None):
        super(Rfdc, self).__init__(host, name, logger)
        self.core = self.host.adcs[name]
        if lmkfile is not None:
            self._check_clockfile_exists(lmkfile)
        if lmxfile is not None:
            self._check_clockfile_exists(lmxfile)
        self.lmkfile = lmkfile
        self.lmxfile = lmxfile

    def _check_clockfile_exists(self, f):
        try:
            available = self.core.show_clk_files()
        except AttributeError:
            # Happens if the transport doesn't have a listbof method
            # Return as if everything is fine
            return True
        if not f in available:
            self.logger.error(f"Clockfile {f} not in available files ({available})")
            return False
        return True

    def _get_core_status(self):
        """
        Get the underlying RFDC firmware module's status flags.
        """
        status = {}
        flags = {}
        s = self.core.status()
        for k0, v0 in s.items():
            for k1, v1 in v0.items():
                if k1 == 'Enabled':
                    status[f"{k0}_enabled"] = bool(v1)
                if k1 == 'State':
                    status[f"{k0}_state"] = v1
                    if v1 != 15:
                        flags[f"{k0}_state"] = FENG_ERROR
                if k1 == 'PLL':
                    status[f"{k0}_pll"] = v1
                    if v1 != 1:
                        flags[f"{k0}_pll"] = FENG_ERROR
        return status, flags

    def get_status(self):
        """
        Get status and error flag dictionaries.

        Status keys:

            - lmkfile (str) : The name of the LMK configuration file being used.

            - lmxfile (str) : The name of the LMX configuration file being used.

        :return: (status_dict, flags_dict) tuple. `status_dict` is a dictionary of
            status key-value pairs. flags_dict is
            a dictionary with all, or a sub-set, of the keys in `status_dict`. The values
            held in this dictionary are as defined in `error_levels.py` and indicate
            that values in the status dictionary are outside normal ranges.
        """
        stats, flags = self._get_core_status()
        stats['lmkfile'] = self.lmkfile
        stats['lmxfile'] = self.lmxfile
        if stats['lmkfile'] is None:
            flags['lmkfile'] = FENG_WARNING
        else:
            if not self._check_clockfile_exists(stats['lmkfile']):
                flags['lmkfile'] = FENG_ERROR
        if stats['lmxfile'] is None:
            flags['lmxfile'] = FENG_WARNING
        else:
            if not self._check_clockfile_exists(stats['lmxfile']):
                flags['lmxfile'] = FENG_ERROR
        return stats, flags

    def initialize(self, read_only=False):
        """
        :param read_only: If False, initialize the RFDC core and PLL chips.
            If True, do nothing.
        :type read_only: bool
        """
        if read_only:
            return
        self.core.init(self.lmkfile, self.lmxfile)

    def get_lo(self, adc_sample_rate_hz, tile, block):
        """
        Get current LO frequency.

        :param adc_sample_rate_hz: ADC sample rate in Hz
        :type adc_sample_rate_hz: float

        :param tile: Zero-indexed tile ID of this ADC.
        :type tile: int

        :param block: Zero-indexed block ID of this ADC.
        :type block: int

        :return: LO frequency in Hz
        :rtype: float
        """
        mode, coarse_freq, fine_freq_mhz = self.core.get_mixer_status(dev='adc', tile=tile, block=block)
        DECIMATION = 2 # TODO: read from driver
        if coarse_freq == 'fs/4':
            coarse_freq = DECIMATION * adc_sample_rate_hz / 4.
        elif coarse_freq == '-fs/4':
            coarse_freq = -1 * DECIMATION * adc_sample_rate_hz / 4.
        elif coarse_freq == 'fs/2':
            coarse_freq = DECIMATION * adc_sample_rate_hz / 2.
        else:
            coarse_freq = 0

        return coarse_freq + fine_freq_mhz*1e6

        
