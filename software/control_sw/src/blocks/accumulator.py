import time
import struct
import numpy as np

from .block import Block
from souk_mkid_readout.error_levels import *

class Accumulator(Block):
    """
    Instantiate a control interface for an Auto-Correlation block. This
    provides auto-correlation spectra of post-FFT data.

    In order to save FPGA resourece, the auto-correlation block may use a single
    correlation core to compute the auto-correlation of a subset of the total
    number of ADC channels at any given time. This is the case when the
    block is instantiated with ``n_cores > 1`` and ``use_mux=True``.
    In this case, auto-correlation spectra are captured ``n_signals / n_cores``
    channels at a time. 

    :param host: CasperFpga interface for host.
    :type host: casperfpga.CasperFpga

    :param name: Name of block in Simulink hierarchy.
    :type name: str

    :param logger: Logger instance to which log messages should be emitted.
    :type logger: logging.Logger

    :param acc_len: Accumulation length initialization value, in spectra.
    :type acc_len: int

    :param n_chans: Number of frequency channels.
    :type n_chans: int

    :param n_parallel_chans: Number of chans processed by the firmware
        module in parallel.
    :type n_parallel_chans: int

    :param is_complex: If True, block accumulates complex-valued data.
    :type is_complex: Bool

    :param dtype: Data type string (as recognised by numpy's `frombuffer` method)
        for accumulated data. If data are complex, this is the data type of
        one of a single real/imag component.
    :type dtype: str

    """
    def __init__(self, host, name,
                 acc_len=2**15,
                 logger=None,
                 n_chans=4096,
                 n_parallel_chans=8,
                 is_complex=True,
                 dtype='>i4'
                ):
        super(Accumulator, self).__init__(host, name, logger)
        self.n_chans = n_chans
        self._n_parallel_chans = n_parallel_chans
        self._default_acc_len = acc_len
        assert n_chans % n_parallel_chans == 0
        self._n_serial_chans = n_chans // n_parallel_chans
        self._dtype = dtype
        self._is_complex = is_complex

    def get_acc_cnt(self):
        """
        Get the current accumulation count.

        :return: Current accumulation count
        :rtype: int
        """
        return self.read_uint('acc_cnt')
   
    def _wait_for_acc(self):
        """
        Block until a new accumulation completes, then return
        the count index.

        :return: Current accumulation count
        :rtype: int
        """
        cnt0 = self.get_acc_cnt()
        cnt1 = self.get_acc_cnt()
        # Counter overflow protection
        if cnt1 < cnt0:
            cnt1 += 2**32
        while cnt1 < ((cnt0+1) % (2**32)):
            time.sleep(0.1)
            cnt1 = self.get_acc_cnt()
        return cnt1

    def _read_bram(self):
        """ 
        Read RAM containing accumulated spectra.

        :return: Array of complex valued data, in int32 format. Array
            dimensions are [FREQUENCY CHANNEL].
        :rtype: numpy.array
        """
        dout = np.zeros(self.n_chans, dtype=complex)
        start_acc_cnt = self.get_acc_cnt()
        wordsize = np.dtype(self._dtype).itemsize
        if self._is_complex:
            wordsize *= 2
        for i in range(self._n_parallel_chans):
            ramname = f'dout{i}'
            d = np.frombuffer(self.read(ramname, self._n_serial_chans*wordsize), dtype=self._dtype)
            for j in range(self._n_serial_chans):
                if self._is_complex:
                    dout.real[self._n_parallel_chans * j + i] = d[2*j]
                    dout.imag[self._n_parallel_chans * j + i] = d[2*j + 1]
                else:
                    dout.real[self._n_parallel_chans * j + i] = d[j]
        stop_acc_cnt = self.get_acc_cnt()
        if start_acc_cnt != stop_acc_cnt:
            self._warning('Accumulation counter changed while reading data!')
        return dout

    def get_new_spectra(self):
        """
        Wait for a new accumulation to be ready then read it.

        :return: Array of `self.n_chans` complex-values.
        :rtype: numpy.ndarray

        """
        self._wait_for_acc()
        return self._read_bram()


    def plot_spectra(self, power=True, db=True, show=True, fftshift=True, sample_rate_hz=None):
        """
        Plot the spectra of all signals in a single signal_block,
        with accumulation length divided out
        
        :param power: If True, plot power, else plot complex
        :type power: bool

        :param db: If True, plot 10log10(power). Else, plot linear.
        :type db: bool

        :param show: If True, call matplotlib's `show` after plotting
        :type show: bool

        :param fftshift: If True, fftshift data before plotting.
        :type fftshift: bool

        :param sample_rate_hz: Effective FFT input sampling rate, in Hz.
            If provided, generate an appropriate frequency axis
        :type sample_rate_hz: float

        :return: matplotlib.Figure

        """
        from matplotlib import pyplot as plt
        spec = self.get_new_spectra()
        if sample_rate_hz is None:
            x = np.arange(self.n_chans)
            xlabel = 'Frequency Channel'
        else:
            x = np.fft.fftfreq(self.n_chans, 1/sample_rate_hz) / 1e6
            xlabel = 'Frequency (MHz)'
        if fftshift:
            spec = np.fft.fftshift(spec)
            x = np.fft.fftshift(x)
        if power:
            if self._is_complex:
                spec = np.abs(spec)**2
            f, ax = plt.subplots(1,1)
            ax.set_xlabel(xlabel)
            if db:
                ax.set_ylabel('Power [dB]')
                spec = 10*np.log10(np.abs(spec))
            else:
                ax.set_ylabel('Power [linear]')
            ax.plot(x, spec)
        else:
            f, ax = plt.subplots(3,1)
            plt.subplot(3,1,1)
            plt.plot(spec.real, label='real')
            plt.plot(spec.imag, label='imag')
            plt.legend()
            plt.xlabel(xlabel)
            plt.subplot(3,1,2)
            plt.plot(x, np.abs(spec))
            plt.ylabel('Amplitude')
            plt.xlabel(xlabel)
            plt.subplot(3,1,3)
            plt.plot(x, np.angle(spec))
            plt.ylabel('Phase [rads]')
            plt.xlabel(xlabel)
        if show:
            plt.show()
        return f

    def get_acc_len(self):
        """
        Get the currently loaded accumulation length in units of spectra.

        :return: Current accumulation length
        :rtype: int
        """
        return self.read_int('acc_len') * self._n_parallel_chans / self.n_chans

    def set_acc_len(self, acc_len):
        """
        Set the number of spectra to accumulate.

        :param acc_len: Number of spectra to accumulate
        :type acc_len: int
        """
        acc_len = acc_len * self.n_chans // self._n_parallel_chans
        self.write_int('acc_len', acc_len)

    def get_status(self):
        """
        Get status and error flag dictionaries.

        Status keys:

            - acc_len (int) : Currently loaded accumulation length in number of spectra.

        :return: (status_dict, flags_dict) tuple. `status_dict` is a dictionary of
            status key-value pairs. flags_dict is
            a dictionary with all, or a sub-set, of the keys in `status_dict`. The values
            held in this dictionary are as defined in `error_levels.py` and indicate
            that values in the status dictionary are outside normal ranges.
        """
        stats = {
            'acc_len': self.get_acc_len(),
        }
        flags = {}
        return stats, flags

    def initialize(self, read_only=False):
        """
        Initialize the block, setting (or reading) the accumulation length.

        :param read_only: If False, set the accumulation length to the value provided
            when this block was instantiated. If True, use whatever accumulation length
            is currently loaded.
        :type read_only: bool
        """
        if read_only:
            self.get_acc_len()
        else:
            self.set_acc_len(self._default_acc_len)
