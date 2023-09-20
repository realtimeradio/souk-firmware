from .pfb import Pfb

class ZoomPfb(Pfb):
    def __init__(self, host, name, logger=None, fftshift=0xffffffff):
        """
        :param host: CasperFpga interface for host.
        :type host: casperfpga.CasperFpga

        :param name: Name of block in Simulink hierarchy.
        :type name: str

        :param logger: Logger instance to which log messages should be emitted.
        :type logger: logging.Logger

        :param fftshift: Default FFT shift to apply
        :type fftshift: int
        """
        super(ZoomPfb, self).__init__(host, name, logger=logger, fftshift=fftshift)

    def set_channel(self, chan):
        """
        Set the channel to select

        :param chan: Channel to select
        :type chan: int
        """
        self.write_int('chan_sel', chan)

    def get_channel(self):
        """
        Get the currently selected channel.

        :return: Channel currently selected
        :rtype: int

        """
        return self.read_uint('chan_sel')

    def get_status(self):
        """
        Get status and error flag dictionaries.

        Status keys:

            - overflow_count (int) : Number of FFT overflow events since last
              statistics reset. Any non-zero value is flagged with "WARNING".

            - fftshift (str) : Currently loaded FFT shift schedule, formatted
              as a binary string, prefixed with "0b".

            - channel (int) : Currently selected input channel

        :return: (status_dict, flags_dict) tuple. `status_dict` is a dictionary of
            status key-value pairs. flags_dict is
            a dictionary with all, or a sub-set, of the keys in `status_dict`. The values
            held in this dictionary are as defined in `error_levels.py` and indicate
            that values in the status dictionary are outside normal ranges.

        """

        stats, flags = super(ZoomPfb, self).get_status()
        stats['channel'] = self.get_channel()
        return stats, flags

    def initialize(self, read_only=False):
        """
        :param read_only: If False, set the FFT shift to the default value,
            reset the overflow count, and set the channel selection to 0.
            If True, do nothing.
        :type read_only: bool
        """
        super(ZoomPfb, self).initialize(read_only)
        if not read_only:
            self.set_channel(0)
