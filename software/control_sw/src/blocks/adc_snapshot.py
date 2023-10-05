import numpy as np

from .block import Block
from souk_mkid_readout.error_levels import *

class AdcSnapshot(Block):
    dtype = '>h'
    ADC_SS_TRIG_OFFSET = 0
    NBYTE = 16 * 2**9 # Number of bytes in each of I and Q buffers
    def __init__(self, host, name, logger=None):
        """
        :param host: CasperFpga interface for host.
        :type host: casperfpga.CasperFpga

        :param name: Name of block in Simulink hierarchy.
        :type name: str

        :param logger: Logger instance to which log messages should be emitted.
        :type logger: logging.Logger

        """
        super(Input, self).__init__(host, name, logger)

    def _trigger_snapshot(self):
        """
        Send snapshot trigger.
        """
        self.change_reg_bits('adc_ss_ctrl', 0, self.ADC_SS_TRIG_OFFSET)
        self.change_reg_bits('adc_ss_ctrl', 1, self.ADC_SS_TRIG_OFFSET)
        self.change_reg_bits('adc_ss_ctrl', 0, self.ADC_SS_TRIG_OFFSET)

    def _read_samples(self):
        """
        Read samples from the ADC data buffers.

        :return: complex-valued array of ADC samples
        :rtype: numpy.ndarray
        """
        di = self.read('i', self.NBYTE)
        dq = self.read('q', self.NBYTE)
        i = np.frombuffer(di, dtype=self.dtype)
        q = np.frombuffer(dq, dtype=self.dtype)
        return i + 1j*q


    def get_adc_snapshot(self):
        """
        Get an ADC snapshot.

        :return: numpy array of complex valued ADC samples
        :rtype: numpy.ndarray
        """

        self._trigger_snapshot()
        return self._read_samples()

    def plot_adc_snapshot(self, nsamples=None):
        """
        Plot an ADC snapshot.

        :param nsamples: If provided, only plot this many samples
        :type nsamples: int
        """
        from matplotlib import pyplot as plt
        x = self.get_adc_snapshot()
        if nsamples is not None:
            x = x[0:nsamples]
        plt.plot(x.real, label='I')
        plt.plot(x.imag, label='Q')
        plt.legend()
        plt.ylabel('ADC counts')
        plt.xlabel('Sample Number')
        plt.show()

    def plot_adc_spectrum(self, db=False):
        """
        Plot a power spectrum of the ADC input stream using a simple FFT.

        :param db: If True, plot in dBs, else linear.
        :type db: bool
        """
        from matplotlib import pyplot as plt
        x = self.get_adc_snapshot()
        X = np.abs(np.fft.fft(x))**2
        if db:
            X = 10*np.log10(X)
        plt.plot(np.fft.fftshift(X))
        plt.xlabel('FFT bin (DC-centered)')
        if db:
            plt.ylabel('Power (dB; Arbitrary Reference)')
        else:
            plt.ylabel('Power (Linear, Arbitrary Reference)')
        plt.show()
