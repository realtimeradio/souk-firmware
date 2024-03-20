import time
import struct
import numpy as np

from .block import Block
from souk_mkid_readout.error_levels import *


class Common(Block):
    """
    Instantiate a control interface for the "common" firmware block,
    which is common to all DSP pipelines.

    :param host: CasperFpga interface for host.
    :type host: casperfpga.CasperFpga

    :param name: Name of block in Simulink hierarchy.
    :type name: str

    :param logger: Logger instance to which log messages should be emitted.
    :type logger: logging.Logger

    :param ninput: Number of inputs this block can handle.
    :type ninput: int

    """
    def __init__(self, host, name,
                 logger=None,
                 ninput=4,
                ):
        super(Common, self).__init__(host, name, logger)
        self.ninput = ninput

    def get_input(self):
        """
        Get the currently selected input index.

        :return: Input ID
        :rtype: int
        """
        return self.read_uint('sel')

    def set_input(self, n):
        """
        Set the currently selected input index to ``n``.

        :param n: Input index to select
        :type n: int
        """
        if not n < self.ninput:
            self.logger.error(f"Common block only services {self.ninput} inputs, so can't select {n}")
            raise ValueError
        self.write_int('sel', n)

    def get_status(self):
        """
        Get status and error flag dictionaries.

        Status keys:

            - input_select (int) : Currently selected input ID

        :return: (status_dict, flags_dict) tuple. `status_dict` is a dictionary of
            status key-value pairs. flags_dict is
            a dictionary with all, or a sub-set, of the keys in `status_dict`. The values
            held in this dictionary are as defined in `error_levels.py` and indicate
            that values in the status dictionary are outside normal ranges.
        """
        stats = {}
        flags = {}
        stats['input_select'] = self.get_input()
        return stats, flags

    def initialize(self, read_only=False):
        """
        Initialize the block.

        :param read_only: If False, set the input select mux to input 0. 
            if True, do nothing.
        :type read_only: bool
        """
        if not read_only:
            self.set_input(0)
