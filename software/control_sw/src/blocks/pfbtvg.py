import numpy as np
import struct
from .block import Block
from souk_mkid_readout.error_levels import *

class PfbTvg(Block):
    """
    Instantiate a control interface for a post-PFB test vector
    generator block.

    :param host: CasperFpga interface for host.
    :type host: casperfpga.CasperFpga

    :param name: Name of block in Simulink hierarchy.
    :type name: str

    :param logger: Logger instance to which log messages should be emitted.
    :type logger: logging.Logger

    :param n_inputs: Number of independent inputs which may be emulated
    :type n_inputs: int

    :param n_serial_inputs: Number of independent inputs sharing a data bus
    :type n_serial_inputs: int

    :param n_rams: Number of independent bram blocks per input. If 0, block
       has no RAMs, and just contains counter-based test vectors.
    :type n_rams: int

    :param n_samples_per_word: Number of complex samples per word in RAM
    :type n_samples_per_word: int

    :param n_chans: Number of frequency channels.
    :type n_chans: int

    :param sample_format: Struct type code (eg. 'h' for 16-bit signed) for
        each of the real/imag parts of the TVG data samples.
    :type sample_format: str

    """
    def __init__(self, host, name, n_inputs=2, n_chans=2**12,
            n_serial_inputs=1, n_rams=2, n_samples_per_word=4,
            sample_format='h', logger=None):
        super(PfbTvg, self).__init__(host, name, logger)
        self.n_inputs = n_inputs
        self._n_serial_inputs = n_serial_inputs
        self._n_rams = n_rams
        self._n_samples_per_word = n_samples_per_word
        self.n_chans = n_chans
        self._format = sample_format
        self._input_size = struct.calcsize(self._format)*self.n_chans*2

    def tvg_enable(self):
        """
        Enable the test vector generator.
        """
        self.write_int('ctrl', 1)

    def tvg_disable(self):
        """
        Disable the test vector generator
        """
        self.write_int('ctrl', 0)

    def tvg_is_enabled(self):
        """
        Query the current test vector generator state.

        :return: True if the test vector generator is enabled, else False.
        :rtype: bool

        """
        return bool(self.read_int('ctrl'))
    
    def write_input_tvg(self, input, test_vector):
        """
        Write a test vector pattern to a single signal input.
        
        :param input: Index of input to which test vectors should be loaded.
        :type input: int

        :param test_vector: `self.n_chans`-element test vector. Values should
            be representable in 16-bit integer format, and may be complex.
        :type test_vector: list or numpy.ndarray

        """
        if self._n_rams == 0:
            raise NotImplementedError('Test vector brams not available in this firmware!')
        tvr = np.array([x.real for x in test_vector], dtype='>%s'%self._format)
        tvi = np.array([x.imag for x in test_vector], dtype='>%s'%self._format)
        assert (tvr.shape[0] == self.n_chans), "Test vector should have self.n_chans elements!"
        core_name = '%d' % (input // self._n_serial_inputs)
        sub_index = input % self._n_serial_inputs
        offset = sub_index * self._input_size // self._n_rams
        # build contents of multiple rams
        for r in range(self._n_rams):
            ram = core_name + '_%d' % r
            b = b''
            for w in range(self.n_chans // self._n_rams // self._n_samples_per_word):
                for s in range(self._n_samples_per_word):
                    i = self._n_samples_per_word * self._n_rams * w + \
                        self._n_samples_per_word * r + s
                    b += struct.pack('>%s' % self._format, tvr[i]) 
                    b += struct.pack('>%s' % self._format, tvi[i]) 
            self.write(ram, b, offset=offset)

    def write_const_per_input(self):
        """
        Write a constant to all the channels of a input,
        with input `i` taking the value `i`.
        """
        for input in range(self.n_inputs):
            self.write_input_tvg(input, np.ones(self.n_chans)*input)

    def write_freq_ramp(self):
        """
        Write a frequency ramp to the test vector 
        that is repeated for all ADC inputs. Data are wrapped to fit into
        8 bits. I.e., the test vector value for channel 257 takes the value ``1``.
        """
        ramp = np.arange(self.n_chans)
        ramp = np.array(ramp, dtype='>%s' %self._format)
        for input in range(self.n_inputs):
            self.write_input_tvg(input, ramp)

    def read_input_tvg(self, input):
        """
        Read the test vector loaded to an ADC input.
        
        :param input: Index of input from which test vectors should be read.
        :type input: int

        :return: Test vector array
        :rtype: numpy.ndarray

        """
        if self._n_rams == 0:
            # The test vector is always a counter since there is no RAM,
            # so simply return that.
            return 1j*np.arange(self.n_chans)
        core_name = '%d' % (input // self._n_serial_inputs)
        sub_index = input % self._n_serial_inputs
        offset = sub_index * self._input_size // self._n_rams
        out = np.zeros(self.n_chans, dtype=complex)
        for r in range(self._n_rams):
            ram = core_name + '_%d' % r
            n_samples = self.n_chans // self._n_rams
            n_bytes = n_samples * 2*struct.calcsize(self._format) # to for real+imag
            s = self.read(ram, n_bytes, offset=offset)
            d = struct.unpack('>%d%s' % (2*n_samples, self._format), s)
            dr = d[0::2]
            di = d[1::2]
            j = 0
            for w in range(self.n_chans // self._n_rams // self._n_samples_per_word):
                for s in range(self._n_samples_per_word):
                    i = self._n_samples_per_word * self._n_rams * w + \
                        self._n_samples_per_word * r + s
                    out[i] = dr[j] + 1j*di[j]
                    j += 1
        return out

    def get_status(self):
        """
        Get status and error flag dictionaries.

        Status keys:

            - tvg_enabled: Currently state of test vector generator. ``True`` if
              the generator is enabled, else ``False``.

        :return: (status_dict, flags_dict) tuple. `status_dict` is a dictionary of
            status key-value pairs. flags_dict is
            a dictionary with all, or a sub-set, of the keys in `status_dict`. The values
            held in this dictionary are as defined in `error_levels.py` and indicate
            that values in the status dictionary are outside normal ranges.
        """
        stats = {}
        flags = {}
        stats['tvg_enabled'] = self.tvg_is_enabled()
        if stats['tvg_enabled']:
            flags['tvg_enabled'] = FENG_NOTIFY
        return stats, flags

    def initialize(self, read_only=False):
        """
        Initialize the block.

        :param read_only: If True, do nothing. If False, load frequency-ramp
            test vectors, but disable the test vector generator.
        :type read_only: bool

        """
        if read_only:
            pass
        else:
            self.tvg_disable()
            if self._n_rams > 0:
                self.write_freq_ramp()
