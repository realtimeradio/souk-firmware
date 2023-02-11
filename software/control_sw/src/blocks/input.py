import numpy as np

from .block import Block
from souk_mkid_readout.error_levels import *

class Input(Block):
    dtype = '>h'
    ADC_SS_ARM_OFFSET = 0
    ADC_SS_TRIG_OFFSET = 1
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

    def get_adc_snapshot(self):
        """
        Get an ADC snapshot.

        :return: numpy array of complex valued ADC samples
        :rtype: numpy.ndarray
        """

        i_ss = self.host.snapshots[self.prefix + 'adc_ss_i']
        q_ss = self.host.snapshots[self.prefix + 'adc_ss_q']
        i_ss.arm()
        q_ss.arm()
        self._trigger_snapshot()
        di, ti = i_ss.read_raw(arm=False)
        dq, tq = q_ss.read_raw(arm=False)
        i = np.frombuffer(di['data'], dtype=self.dtype)
        q = np.frombuffer(dq['data'], dtype=self.dtype)
        return i + 1j*q

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

    def enable_loopback(self):
        """
        Set pipeline to internally loop-back DAC stream into ADC.
        """
        self.write_int('loopback_enable', 1)

    def disable_loopback(self):
        """
        Set pipeline to feed pipeline from ADC inputs
        """
        self.write_int('loopback_enable', 0)

    def loopback_enabled(self):
        """
        Get the current loopback state.

        :return: True if internal loopback is enabled. False otherwise.
        :rtype: bool
        """
        return bool(self.read_int('loopback_enable'))

    def get_status(self):
        """
        Get status and error flag dictionaries.

        Status keys:

            - loopback (book) : True is system is in internal loopback mode.
              If True this is flagged with "WARNING".

        :return: (status_dict, flags_dict) tuple. `status_dict` is a dictionary of
            status key-value pairs. flags_dict is
            a dictionary with all, or a sub-set, of the keys in `status_dict`. The values
            held in this dictionary are as defined in `error_levels.py` and indicate
            that values in the status dictionary are outside normal ranges.

        """

        stats = {}
        flags = {}
        stats['loopback'] = self.loopback_enabled()
        if stats['loopback']:
            flags['loopback'] = FENG_WARNING
        return stats, flags

    def initialize(self, read_only=False):
        """
        :param read_only: If False, disable loopback mode.
            If True, do nothing.
        :type read_only: bool
        """
        if read_only:
            return
        self.write_int('adc_ss_ctrl', 0)
        self.disable_loopback()
