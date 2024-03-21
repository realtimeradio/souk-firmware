import numpy as np

from .block import Block
from souk_mkid_readout.error_levels import *

class Delay(Block):
    DELAY_BITS = 4
    def __init__(self, host, name, logger=None):
        """
        :param host: CasperFpga interface for host.
        :type host: casperfpga.CasperFpga

        :param name: Name of block in Simulink hierarchy.
        :type name: str

        :param logger: Logger instance to which log messages should be emitted.
        :type logger: logging.Logger

        """
        super(Delay, self).__init__(host, name, logger)
        self.max_delay = 2**self.DELAY_BITS - 1

    def set_delay(self, n_fpga_clocks):
        """
        Set the delay applied to the output stream, in units of FPGA clocks.
        Each FPGA clock is 8 DAC clocks. I.e., a system with output bandwidth
        of 2500 MHz has an FPGA clock of 312.5 MHz.

        :param n_fpga_clocks: Number of FPGA clock cycles delay to apply.
        :type n_fpga_clocks: int

        """
        assert n_fpga_clocks <= self.max_delay, f'Only delays <= {self.max_delay} supported' 
        self.write_int('n_clocks', n_fpga_clocks)

    def get_delay(self):
        """
        Get the delay applied to the output stream, in units of FPGA clocks.
        Each FPGA clock is 8 DAC clocks. I.e., a system with output bandwidth
        of 2500 MHz has an FPGA clock of 312.5 MHz.

        :return: Number of FPGA clock cycles of delay
        :rtype: int
        """
        x = self.read_uint('n_clocks')
        assert x <= self.max_delay, f'Suspicious delay > {self.max_delay} read from firmware'
        return x

    def get_status(self):
        """
        Get status and error flag dictionaries.

        Status keys:

            - delay (int) : Number of FPGA clocks of delay applied to output stream

        :return: (status_dict, flags_dict) tuple. `status_dict` is a dictionary of
            status key-value pairs. flags_dict is
            a dictionary with all, or a sub-set, of the keys in `status_dict`. The values
            held in this dictionary are as defined in `error_levels.py` and indicate
            that values in the status dictionary are outside normal ranges.

        """

        stats = {}
        flags = {}
        stats['delay'] = self.get_delay()
        return stats, flags

    def initialize(self, read_only=False):
        """
        :param read_only: If False, set delay to 0.
            If True, do nothing.
        :type read_only: bool
        """
        if read_only:
            return
        self.set_delay(0)
