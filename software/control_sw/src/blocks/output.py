import numpy as np

from .block import Block
from souk_mkid_readout.error_levels import *

class Output(Block):
    USE_CORDIC=0
    USE_LUT=1
    USE_PSB=2
    MODE_MAP = {USE_CORDIC:'CORDIC', USE_LUT:'LUT', USE_PSB:'PSB'}
    def __init__(self, host, name, logger=None):
        """
        :param host: CasperFpga interface for host.
        :type host: casperfpga.CasperFpga

        :param name: Name of block in Simulink hierarchy.
        :type name: str

        :param logger: Logger instance to which log messages should be emitted.
        :type logger: logging.Logger

        """
        super(Output, self).__init__(host, name, logger)

    def use_cordic(self):
        """
        Set output pipeline to use CORDIC generators
        """
        self.write_int('sel', self.USE_CORDIC)

    def use_lut(self):
        """
        Set output pipeline to use LUT generators
        """
        self.write_int('sel', self.USE_LUT)

    def use_psb(self):
        """
        Set output pipeline to use Polyphase Synthesis generators
        """
        self.write_int('sel', self.USE_PSB)

    def get_mode(self):
        """
        Get the current output mode.

        :return: string describing output mode, eg. "CORDIC"
        :rtype: str
        """
        v = self.read_uint('sel')
        try:
            s = self.MODE_MAP[v]
        except KeyError:
            self.logger.error('Output mode not recognized')
            s = 'Unknown'
        return s

    def get_status(self):
        """
        Get status and error flag dictionaries.

        Status keys:

            - mode (str) : 'CORDIC' or 'LUT' or 'PSB'

        :return: (status_dict, flags_dict) tuple. `status_dict` is a dictionary of
            status key-value pairs. flags_dict is
            a dictionary with all, or a sub-set, of the keys in `status_dict`. The values
            held in this dictionary are as defined in `error_levels.py` and indicate
            that values in the status dictionary are outside normal ranges.

        """

        stats = {}
        flags = {}
        stats['mode'] = self.get_mode()
        return stats, flags

    def initialize(self, read_only=False):
        """
        :param read_only:
            If True, do nothing. If False, initialize to LUT mode.
        :type read_only: bool
        """
        if read_only:
            return
        self.use_lut()
