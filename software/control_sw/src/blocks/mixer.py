import struct
import numpy as np
from .block import Block

class Mixer(Block):
    """
    Instantiate a control interface for a Channel Reorder block.

    :param host: CasperFpga interface for host.
    :type host: casperfpga.CasperFpga

    :param name: Name of block in Simulink hierarchy.
    :type name: str

    :param logger: Logger instance to which log messages should be emitted.
    :type logger: logging.Logger

    :param n_chans: Number of channels this block processes
    :type n_chans: int

    :param n_parallel_chans: Number of channels this block processes in parallel
    :type n_parallel_chans: int

    :param phase_bp: Number of phase fractional bits
    :type phase_bp: int

    """
    def __init__(self, host, name,
            n_chans=4096,
            n_parallel_chans=4,
            phase_bp=31,
            logger=None):
        super(Mixer, self).__init__(host, name, logger)
        self.n_chans = n_chans
        assert n_chans % n_parallel_chans == 0
        self._n_parallel_chans = n_parallel_chans
        self._n_serial_chans = n_chans // n_parallel_chans
        self._phase_bp = phase_bp

    def enable_power_mode(self):
        """
        Instead of applying a phase rotation to the data streams,
        calculate their power.
        """
        self.write_int('power_en', 1)

    def disable_power_mode(self):
        """
        Use phase rotation, rather than power.
        """
        self.write_int('power_en', 0)

    def is_power_mode(self):
        """
        Get the current block mode.

        :return: True if the block is calculating power, False if it is
            applying phase rotation.
        :rtype: bool
        """
        return bool(self.read_int('power_en'))

    def set_phase_step(self, chan, phase):
        """
        Set the phase increment to apply on each successive sample for
        channel `chan`.

        :param chan: The channel index to which this phase-rate should be applied
        :type chan: int

        :param phase: The phase increment to be added each successive sample
            in units of radians.
        :type phase: float

        """
        p = chan % self._n_parallel_chans  # Parallel stream number
        s = chan // self._n_parallel_chans # Serial channel position
        regname = f'lo{p}_phase_inc'
        # phase written to register should be +/-1 and in units of pi
        phase_scaled = phase / np.pi
        phase_scaled = ((phase + 1) % 2) - 1
        phase_scaled = int(phase_scaled * 2**self._phase_bp)
        self.write_int(regname, phase_scaled, word_offset=s)
 

    def get_phase_offset(self, chan):
        """
        Get the currently loaded phase increment being applied to channel `chan`.

        :return: The phase increment being applied to channel `chan` on each
            successive sample, in radians.
        :rtype: float
        """
        p = chan % self._n_parallel_chans  # Parallel stream number
        s = chan // self._n_parallel_chans # Serial channel position
        regname = f'lo{p}_phase_inc'
        phase_scaled = self.read_int(regname, phase_scaled, word_offset=s)
        phase = (phase_scaled / (2**self._phase_bp)) * np.pi
        return phase
        

    def initialize(self, read_only=False):
        """
        Initialize the block.

        :param read_only: If True, this method is a no-op. If False,
            set this block to phase rotate mode, but initialize 
            with each channel having zero phase increment.
        :type read_only: bool
        """
        if read_only:
            pass
        else:
            self.disable_power_mode()
            for i in range(self.n_chans):
                self.set_phase_step(i, 0)
