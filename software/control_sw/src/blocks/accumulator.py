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
                 logger=None,
                 acc_len=2**15,
                 n_chans=4096,
                 n_parallel_chans=8,
                 is_complex=True,
                 dtype='>i4',
                 has_dest_ip=False,
                ):
        super(Accumulator, self).__init__(host, name, logger)
        self.n_chans = n_chans
        self._n_parallel_chans = n_parallel_chans
        self._default_acc_len = acc_len
        assert n_chans % n_parallel_chans == 0
        self._n_serial_chans = n_chans // n_parallel_chans
        self._dtype = dtype
        self._is_complex = is_complex
        self._has_dest_ip = has_dest_ip

    def get_acc_cnt(self):
        """
        Get the current accumulation count.

        :return: Current accumulation count
        :rtype: int
        """
        return self.read_uint('acc_cnt')
   
    def _wait_for_acc(self, poll_period_s=0.1):
        """
        Block until a new accumulation completes, then return
        the count index.

        :param poll_period_s: The polling rate of the new accumulation counter, in seconds.
        :type poll_period_s: float

        :return: Current accumulation count
        :rtype: int
        """
        cnt0 = self.get_acc_cnt()
        cnt1 = self.get_acc_cnt()
        # Counter overflow protection
        if cnt1 < cnt0:
            cnt1 += 2**32
        while cnt1 < ((cnt0+1) % (2**32)):
            time.sleep(poll_period_s)
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
            if self._is_complex:
                dout[i::self._n_parallel_chans].real = d[0::2]
                dout[i::self._n_parallel_chans].imag = d[1::2]
            else:
                dout[i::self._n_parallel_chans].imag = d[:]
        stop_acc_cnt = self.get_acc_cnt()
        if start_acc_cnt != stop_acc_cnt:
            self.logger.warning('Accumulation counter changed while reading data!')
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
        return self.read_int('acc_len') // self._n_serial_chans

    def set_acc_len(self, acc_len):
        """
        Set the number of spectra to accumulate.

        :param acc_len: Number of spectra to accumulate
        :type acc_len: int
        """
        acc_len = acc_len * self._n_serial_chans
        self.write_int('acc_len', acc_len)

    def read_tt(self):
        msb = self.read_uint('acc_tt_msb')
        lsb = self.read_uint('acc_tt_lsb')
        return (msb << 32) + lsb

    def set_dest_ip(self, ip):
        if not self._has_dest_ip:
            raise NotImplementedError
        ip_octs = list(map(int, ip.split('.')))
        ip_int = 0
        for i in range(4):
            ip_int += (ip_octs[i] << (24 - 8*i))
        self.write_int('dest_ip', ip_int)

    def get_dest_ip(self):
        if not self._has_dest_ip:
            raise NotImplementedError
        ip_int = self.read_uint('dest_ip')
        ip_octs = [0 for _ in range(4)]
        for i in range(4):
            ip_octs[i] = (ip_int >> (24 - 8*i)) & 0xff
        ip = '.'.join(map(str, ip_octs))
        return ip

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
        stats = {}
        flags = {}
        stats['acc_len'] = self.get_acc_len()
        if self._has_dest_ip:
            stats['dest_ip'] = self.get_dest_ip()
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
            if self._has_dest_ip:
                self.set_dest_ip('0.0.0.0')


class WindowedAccumulator(Accumulator):
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
                 logger=None,
                 acc_len=2**15,
                 n_chans=4096,
                 n_parallel_chans=8,
                 is_complex=True,
                 dtype='>i4',
                 has_dest_ip=False,
                 include_window=False,
                 window_bp=14,
                 window_dtype='>i2',
                 window_n_points=2**11,
                 max_reuse_bits=9
                ):
        super(WindowedAccumulator, self).__init__(host, name, logger,
                acc_len=acc_len, n_chans=n_chans,
                n_parallel_chans=n_parallel_chans, is_complex=is_complex,
                dtype=dtype, has_dest_ip=has_dest_ip)
        self._window_bp = window_bp
        self._window_dtype = window_dtype
        self._window_n_points = window_n_points
        self._max_reuse_bits = max_reuse_bits

    def write_window(self, window):
        assert len(window) <= self._window_n_points
        coeffs = np.array(window)
        coeffs *= 2**self._window_bp
        coeffs = np.array(coeffs, dtype=self._window_dtype)
        self.write('window', coeffs.tobytes())

    def get_window(self, n=None):
        nbytes = self._window_n_points * np.dtype(self._window_dtype).itemsize
        fullwind = np.frombuffer(self.read('window', nbytes), dtype=self._window_dtype)
        if n is None:
            n = int(np.ceil(self.get_acc_len() / 2**self.get_window_step()))
        out = fullwind[0:n] / 2**self._window_bp
        return out

    def set_window_step(self, n):
        assert n <= self._max_reuse_bits
        self.write_int('window_shift', n)

    def get_window_step(self):
        return self.read_uint('window_shift')

    def set_window(self, windfunc=np.ones):
        # Start with known state, to aid in future debugging
        coeffs = (np.zeros(self._window_n_points))
        acc_len = self.get_acc_len()
        # Need to reuse coeffs if acc_len is longer than number of window points
        f = acc_len / self._window_n_points
        reuse_factor_bits = max(0, int(np.ceil(np.log2(f))))
        reuse_factor = 2**reuse_factor_bits
        self.set_window_step(reuse_factor_bits)
        n_coeffs = int(np.ceil(acc_len / reuse_factor))
        self.logger.info(f'Acclen {acc_len}; using {n_coeffs} points, with reuse factor {reuse_factor}')
        coeffs[0:n_coeffs] = windfunc(n_coeffs)
        self.write_window(coeffs)

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
        stats, flags = super(WindowedAccumulator, self).get_status()
        stats['window_step'] = 2**self.get_window_step()
        stats['window'] = self.get_window()
        return stats, flags

    def initialize(self, read_only=False):
        """
        Initialize the block, setting (or reading) the accumulation length.

        :param read_only: If False, set the accumulation length to the value provided
            when this block was instantiated, and set the window function to all ones.
            If True, do nothing.
        :type read_only: bool
        """
        super(WindowedAccumulator, self).initialize(read_only=read_only)
        if not read_only:
            self.set_window_step(0)
            self.write_window(np.ones(self._window_n_points))
