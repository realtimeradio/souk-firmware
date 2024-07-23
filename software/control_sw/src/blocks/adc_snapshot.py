import numpy as np

from .block import Block
from souk_mkid_readout.error_levels import *

class AdcSnapshot(Block):
    dtype = '>h'
    ADC_SS_TRIG_OFFSET = 1
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
        super(AdcSnapshot, self).__init__(host, name, logger)

    def _trigger_snapshot(self):
        """
        Send snapshot trigger.
        """
        self.change_reg_bits('ctrl', 0, self.ADC_SS_TRIG_OFFSET)
        self.change_reg_bits('ctrl', 1, self.ADC_SS_TRIG_OFFSET)
        self.change_reg_bits('ctrl', 0, self.ADC_SS_TRIG_OFFSET)

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
        Same as `get_snapshot` for backwards compatibility
        """
        self.logger.info('get_adc_snapshot is deprecated. Please use get_snapshot')
        return self.get_snapshot()

    def get_snapshot(self):
        """
        Get a data snapshot.

        :return: numpy array of complex valued ADC samples
        :rtype: numpy.ndarray
        """

        self._trigger_snapshot()
        return self._read_samples()

    def plot_adc_snapshot(self, nsamples=None):
        """
        Same as `plot_snapshot` for backwards compatibility
        """
        self.logger.info('plot_adc_snapshot is deprecated. Please use plot_snapshot')
        return self.plot_snapshot(nsamples=nsamples)

    def plot_snapshot(self, nsamples=None):
        """
        Plot a data snapshot.

        :param nsamples: If provided, only plot this many samples
        :type nsamples: int
        """
        from matplotlib import pyplot as plt
        x2d = np.atleast_2d(self.get_snapshot())
        for i in range(x.shape[0]):
            if nsamples is not None:
                x = x2d[i][0:nsamples]
            plt.plot(x.real, label=f'I{i}')
            plt.plot(x.imag, label=f'Q{i}')
        plt.legend()
        plt.ylabel('ADC counts')
        plt.xlabel('Sample Number')
        plt.show()

    def plot_adc_spectrum(self, db=False):
        """
        Same as `plot_spectrum` for backwards compatibility
        """
        self.logger.info('plot_adc_spectrum is deprecated. Please use plot_spectrum')
        return plot_spectrum(db=db)

    def plot_adc_spectrum(self, db=False):
        """
        Plot a power spectrum of a data snapshot using a simple FFT.

        :param db: If True, plot in dBs, else linear.
        :type db: bool
        """
        from matplotlib import pyplot as plt
        x2d = np.atleast_2d(self.get_snapshot())
        for i in range(x.shape[0]):
            X = np.abs(np.fft.fft(x))**2
            if db:
                X = 10*np.log10(X)
            plt.plot(np.fft.fftshift(X), label=f'{i}')
        plt.xlabel('FFT bin (DC-centered)')
        if db:
            plt.ylabel('Power (dB; Arbitrary Reference)')
        else:
            plt.ylabel('Power (Linear, Arbitrary Reference)')
        plt.legend()
        plt.show()
