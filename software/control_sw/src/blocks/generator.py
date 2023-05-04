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
        try:
            x = self.read_uint('block_info')
        except:
            return
        self.n_generators = (x >> 24) & 0xff
        self._n_parallel  = (x >> 16) & 0xff
        self.n_samples    = 2**((x >> 8)  & 0xff)

    def set_lut_output(self, n, x):
        """
        Set LUT output `n` to sample array `x`.

        :param n: Which generator to target.
        :type n: int

        :param x: Array (or list) of complex sample values
        :type x: list or numpy.array
        """
        if self.n_generators is None:
            self._get_block_params()
        if n >= self.n_generators:
            self._error(f'Requested generator {n}, but only {self.n_generators} are provided')
            return
        x = np.array(x)
        if len(x) != self.n_samples:
            self._error(f'{len(x)} sample were provided but expected {self.n_samples}')
            return
        imag = np.array(x.imag * 2**14, dtype='>i2')
        real = np.array(x.real * 2**14, dtype='>i2')
        self.write(f'{n}_i', real.tobytes())
        self.write(f'{n}_q', imag.tobytes())

    def get_lut_output(self, n):
        """
        Get waveform stored in LUT output `n`.

        :param n: Which generator to target.
        :type n: int

        :return: waveform
        :rtype: numpy.ndarray
        """
        realraw = self.read(f'{n}_i', self.n_samples*2)
        imagraw = self.read(f'{n}_q', self.n_samples*2)
        real = np.frombuffer(realraw, dtype='>i2')
        imag = np.frombuffer(imagraw, dtype='>i2')
        return real + 1j*imag

    def set_output_freq(self, n, freq_mhz, sample_rate_mhz=2457.6,
                        amplitude=1., round_freq=True, window=False):
        """
        Set an output to a CW tone at a specific frequency.

        :param n: Which generator to target
        :type n: int

        :param freq_mhz: Output frequency, in MHz
        :type freq_mhz: float

        :param sample_rate_mhz: DAC sample rate, in MHz
        :type sample_rate_mhz: float

        :param amplitude: Set the output of amplitude of the CW signal. Only
            applicable for LUT-based generators
        :type amplitude: float

        :param round_freq: If True, round ``freq_mhz`` to the nearest frequency which
            can be represented with a ``self.n_samples`` circular buffer.
            This option affects only LUT generators.
        :type round_freq: bool

        :param window: If True, apply a Hann (a.k.a. Hanning) window to data samples.
            This option affects only LUT generators.
        :type window: bool
        """
        if self.n_samples > 1:
            t = np.arange(self.n_samples) / sample_rate_mhz
            if round_freq:
                freq_step_mhz = sample_rate_mhz / self.n_samples
                freq_mhz = round(freq_mhz / freq_step_mhz) * freq_step_mhz
                self._info(f"Rounded frequency to {freq_mhz} to make continuous circular waveform")
            x = np.exp(1j*2*np.pi*freq_mhz*t) * amplitude
            if window:
                self._info("Appling Hann window")
                x *= np.hanning(self.n_samples)
            self.set_lut_output(n, x)
        else:
            if amplitude != 1.0:
                self._warning("Amplitude setting not used for CORDIC generators")
            phase_step = 2*np.pi * freq_mhz / sample_rate_mhz
            self.set_cordic_output(n, phase_step)

    def set_cordic_output(self, n, p):
        """
        Set CORDIC output `n` to increment by phase `p` every sample.

        :param n: Which generator to target.
        :type n: int

        :param p: phase increment, in units of radians
        :type p: float
        """
        if self.n_generators is None:
            self._get_block_params()
        if n >= self.n_generators:
            self._error(f'Requested generator {n}, but only {self.n_generators} are provided')
            return
        if self.n_samples > 1:
            self._error('This is a LUT generator, and provides no CORDIC capabilities')
            return
        # phase should be in units of pi radians, and in range +/-1
        phase_scaled = p / np.pi
        phase_scaled = ((phase_scaled + 1) % 2) - 1
        phase_scaled = int(phase_scaled * 2**63)
        self.write_int(f'{n}_phase_inc_msb', (phase_scaled >> 32) & 0xffffffff)
        self.write_int(f'{n}_phase_inc_lsb', phase_scaled & 0xffffffff)
        self.reset_phase()

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
        self._get_block_params()
        if read_only:
            return
        for g in range(self.n_generators):
            if self.n_samples > 1:
                self.set_lut_output(g, np.zeros(self.n_samples, dtype=complex))
            else:
                self.set_cordic_output(g, 0)
        self.reset_phase()
