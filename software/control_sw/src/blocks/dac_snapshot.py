import numpy as np

from .adc_snapshot import AdcSnapshot

class DacSnapshot(AdcSnapshot):
    NBYTE = 32 * 2**9 # Number of bytes in each of the buffers
    def _read_samples(self):
        """
        Read samples from the DAC data buffers.

        :return: 2D complex-valued array of DAC samples
        :rtype: numpy.ndarray
        """
        d0_raw = self.read('0', self.NBYTE)
        d1_raw = self.read('1', self.NBYTE)
        d0iq = np.frombuffer(d0_raw, dtype=self.dtype)
        d1iq = np.frombuffer(d1_raw, dtype=self.dtype)
        d0 = d0iq[0::2] + 1j*d0iq[1::2]
        d1 = d1iq[0::2] + 1j*d1iq[1::2]
        return np.vstack([d0, d1])
