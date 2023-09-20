import numpy as np

from .block import Block
from souk_mkid_readout.error_levels import *

class Pfb(Block):
    def __init__(self, host, name, logger=None, fftshift=0xffffffff):
        """
        :param host: CasperFpga interface for host.
        :type host: casperfpga.CasperFpga

        :param name: Name of block in Simulink hierarchy.
        :type name: str

        :param logger: Logger instance to which log messages should be emitted.
        :type logger: logging.Logger

        :param fftshift: Default FFT shift to apply
        :type fftshift: int
        """
        super(Pfb, self).__init__(host, name, logger)
        self.fftshift = fftshift

    def set_fftshift(self, shift):
        """
        Set the FFT shift schedule.

        :param shift: Shift schedule to be applied.
        :type shift: int
        """
        self.write_int('shift', shift)

    def get_fftshift(self):
        """
        Get the currently applied FFT shift schedule. The returned value
        takes into account any hardcoding of the shift settings by firmware.

        :return: Shift schedule
        :rtype: int
        """
        return self.read_uint('shift')

    def get_overflow_count(self):
        """
        Get the total number of FFT overflow events, since the last
        statistics reset.

        :return: Number of overflows
        :rtype: int
        """
        return self.read_uint('of_count')

    def reset_overflow_count(self):
        """
        Reset overflow counter.
        """
        self.write_int('ctrl', 1)
        self.write_int('ctrl', 0)

    def get_status(self):
        """
        Get status and error flag dictionaries.

        Status keys:

            - overflow_count (int) : Number of FFT overflow events since last
              statistics reset. Any non-zero value is flagged with "WARNING".

            - fftshift (str) : Currently loaded FFT shift schedule, formatted
              as a binary string, prefixed with "0b".

        :return: (status_dict, flags_dict) tuple. `status_dict` is a dictionary of
            status key-value pairs. flags_dict is
            a dictionary with all, or a sub-set, of the keys in `status_dict`. The values
            held in this dictionary are as defined in `error_levels.py` and indicate
            that values in the status dictionary are outside normal ranges.

        """

        stats = {}
        flags = {}
        stats['overflow_count'] = self.get_overflow_count()
        if stats['overflow_count'] != 0:
            flags['overflow_count'] = FENG_WARNING
        fftshift = self.get_fftshift()
        stats['fftshift'] = '0b%s' % np.binary_repr(fftshift, width=16)
        return stats, flags

    def initialize(self, read_only=False):
        """
        :param read_only: If False, set the FFT shift to the default value, and
            reset the overflow count. If True, do nothing.
        :type read_only: bool
        """
        if read_only:
            return
        self.set_fftshift(self.fftshift)
        self.reset_overflow_count()
