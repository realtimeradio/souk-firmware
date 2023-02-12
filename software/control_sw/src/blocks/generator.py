import numpy as np

from .block import Block
from souk_mkid_readout.error_levels import *

class Generator(Block):
    def __init__(self, host, name, logger=None):
        """
        :param host: CasperFpga interface for host.
        :type host: casperfpga.CasperFpga

        :param name: Name of block in Simulink hierarchy.
        :type name: str

        :param logger: Logger instance to which log messages should be emitted.
        :type logger: logging.Logger

        """
        super(Generator, self).__init__(host, name, logger)
        self.n_generators  = None
        self._n_parallel   = None
        self.n_samples     = None
        self._get_block_params()
    
    def _get_block_params(self):
        """
        Get the compile time block configuration
        """
        x = self.read_uint('block_info')
        self.n_generators = (x >> 24) & 0xff
        self._n_parallel  = (x >> 16) & 0xff
        self.n_samples    = (x >> 8)  & 0xff

    def set_lut_output(self, n, x):
        """
        Set LUT output `n` to sample array `x`.

        :param n: Which generator to target.
        :type n: int

        :param x: Array (or list) of complex sample values
        :type x: list or numpy.array
        """
        if n >= self.n_generators:
            self._error(f'Requested generator {n}, but only {self.n_generators} are provided')
            return
        x = np.array(x)
        if len(x) != self.n_samples:
            self._error(f'{len(x)} sample were provided but expected {self.n_samples}')
            return
        imag = np.array(x.imag, dtype='>i4')
        real = np.array(x.real, dtype='>i4')
        self.write(f'{n}_i', real.tobytes())
        self.write(f'{n}_q', imag.tobytes())

    def set_cordic_output(self, n, p):
        """
        Set CORDIC output `n` to increment by phase `p` every sample.

        :param n: Which generator to target.
        :type n: int

        :param p: phase increment, in units of radians
        :type p: float
        """
        if n >= self.n_generators:
            self._error(f'Requested generator {n}, but only {self.n_generators} are provided')
            return
        if self.n_samples != 0:
            self._error('This is a LUT generator, and provides no CORDIC capabilities')
            return
        # phase should be in units of pi radians, and in range +/-1
        phase_scaled = p / np.pi
        phase_scaled = ((phase_scaled + 1) % 2) - 1
        phase_scaled = int(phase_scaled * 2**63)
        self.write_int(f'{n}_phase_inc_inc_msb', (phase_scaled >> 32) & 0xffffffff)
        self.write_int(f'{n}_phase_inc_inc_lsb', phase_scaled & 0xffffffff)

    def reset_phase(self):
        """
        Reset the phase of the output(s).
        """
        self.write_int('phase_inc_rst', 0)
        self.write_int('phase_inc_rst', 1)
        self.write_int('phase_inc_rst', 0)
        
    def initialize(self, read_only=False):
        """
        :param read_only:
            If True, do nothing. If False, reset phase and generator contents
        :type read_only: bool
        """
        if read_only:
            return
        for g in range(self.n_generators):
            if self.n_samples > 0:
                self.set_lut_output(g, np.zeros(self.n_samples, dtype=complex))
            else:
                self.set_cordic_output(g, 0)
        self.reset_phase()
