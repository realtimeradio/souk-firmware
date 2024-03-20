import numpy as np

from .block import Block
from souk_mkid_readout.error_levels import *

class PsbScale(Block):
    _n_bp = 8
    _n_bit = 16
    def __init__(self, host, name, logger=None):
        """
        :param host: CasperFpga interface for host.
        :type host: casperfpga.CasperFpga

        :param name: Name of block in Simulink hierarchy.
        :type name: str

        :param logger: Logger instance to which log messages should be emitted.
        :type logger: logging.Logger

        """
        super(PsbScale, self).__init__(host, name, logger)

    def set_scale(self, scale):
        """
        Set the scale factor.

        :param scale: Scale factor to be written.
        :type scale: float
        """

        scale = int(scale * 2**self._n_bp)
        if scale > 2**self._n_bit - 1:
            scale = 2**self._n_bit - 1
            self.logger.warning(f'Saturating scale factor to {scale}')
        elif scale < 0:
            self.logger.error('Scale factor cannot be negative!')
            raise ValueError
        self.write_int('scale', scale)

    def get_scale(self):
        """
        Get the scale factor.

        :return: Scale factor
        :rtype: float
        """

        scale = self.read_uint('scale')
        return scale / (2.0**self._n_bp)

    def get_overflow_count(self):
        """
        Get the number of overflow events since the last scale factor change.

        :return: Number of overflows
        :rtype: int
        """
        return self.read_uint('scale_of_count')

    def get_status(self):
        """
        Get status and error flag dictionaries.

        Status keys:

            - scale (float) : Current scale factor
            - overflow (bool) : True if overflows detected, false otherwise.

        :return: (status_dict, flags_dict) tuple. `status_dict` is a dictionary of
            status key-value pairs. flags_dict is
            a dictionary with all, or a sub-set, of the keys in `status_dict`. The values
            held in this dictionary are as defined in `error_levels.py` and indicate
            that values in the status dictionary are outside normal ranges.

        """

        stats = {}
        flags = {}
        stats['scale'] = self.get_scale()
        stats['overflow'] = self.get_overflow_count() > 0
        if stats['overflow']:
            flags['overflow'] = FENG_WARNING
        return stats, flags

    def initialize(self, read_only=False):
        """
        :param read_only: If False, set scale to 1.0
            If True, do nothing.
        :type read_only: bool
        """
        if read_only:
            return
        self.set_scale(1.0)
