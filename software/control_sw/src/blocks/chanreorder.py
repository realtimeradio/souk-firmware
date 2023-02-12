import struct
import numpy as np
from .block import Block

class ChanReorder(Block):
    """
    Instantiate a control interface for a Channel Reorder block.

    :param host: CasperFpga interface for host.
    :type host: casperfpga.CasperFpga

    :param name: Name of block in Simulink hierarchy.
    :type name: str

    :param logger: Logger instance to which log messages should be emitted.
    :type logger: logging.Logger

    :param n_chans_in: Number of channels input to the reorder
    :type n_chans_in: int

    :param n_chans_out: Number of channels output to the reorder
    :type n_chans_out: int

    :param n_parallel_chans_in: Number of channels handled in parallel at the input
    :type n_parallel_chans_in: int
    """
    _map_format = 'I' # CASPER library-defined map word format
    _map_reg = 'map1' # CASPER library-defined map name in reorder block
    def __init__(self, host, name,
            n_chans_in=4096,
            n_chans_out=2048,
            n_parallel_chans_in=4,
            logger=None):
        super(ChanReorder, self).__init__(host, name, logger)
        assert n_chans_in % n_parallel_chans_in == 0
        # firmware uses 1 byte mux inputs, so breaks if >256 inputs
        assert np.log2(n_parallel_chans_in) <= 256
        self.n_chans_in = n_chans_in
        self.n_chans_out = n_chans_out
        self._n_parallel_chans_in = n_parallel_chans_in
        self._n_serial_chans_in = n_chans_in // n_parallel_chans_in
        # These asserts probably don't catch all configuration issues
        assert n_chans_in % n_chans_out == 0
        self._inout_ratio = n_chans_in // n_chans_out
        assert n_parallel_chans_in % self._inout_ratio == 0
        self._n_parallel_chans_out = n_parallel_chans_in // self._inout_ratio

    def set_channel_outmap(self, outmap):
        """
        Reoutmap the channels such that the channel outmap[i]
        emerges out of the reorder map in position i.

        The provided map must be `self.n_chans_out` elements long, else
        `ValueError` is raised

        :param outmap: The outmap to which data should be mapped. I.e., if
            `outmap[0] = 16`, then the first channel out of the reordr block
            will be channel 16. 
        :type outmap: list of int


        """
        outmap = np.array(outmap)
        # We must load the reorder map in one go, so it should be for all chans
        if outmap.shape[0] != self.n_chans_out:
            raise ValueError(f'Input outmap should be {self.n_chans_out} elements long')
        # Check the output chans are all in the input
        for outchan in outmap:
            if outchan >= self.n_chans_in:
                raise ValueError(f'Selected channel {outchan} not in input range')

        serial_maps = np.zeros([self._n_parallel_chans_in, self._n_serial_chans_in],
                          dtype='>%s' % self._map_format)
        parallel_maps = np.zeros([self._n_parallel_chans_out, self._n_serial_chans_in],
                          dtype='>B')
        # outn is where we want this channel in the output
        # outchan is where this channel is at the input
        for outn, outchan in enumerate(outmap):
            # Which of the parallel input streams contains this channel
            in_pstream = outchan % self._n_parallel_chans_in
            # Which input serial position contains this channel
            in_spos = outchan // self._n_parallel_chans_in
            # Which output parallel stream would we like outchan to be in
            out_pstream = outn % self._n_parallel_chans_out
            # Which output serial position would we like outchan to be in
            out_spos = outn // self._n_parallel_chans_out
            # build maps appropriately
            self._debug(f'Chan {outchan} Setting input {in_pstream}:{in_spos} to {out_pstream}:{out_spos}')
            serial_maps[in_pstream, out_spos] = in_spos
            parallel_maps[out_pstream, out_spos] = in_pstream
        for i in range(self._n_parallel_chans_in):
            self.write(f'reorder_{i}_{self._map_reg}', serial_maps[i].tobytes())
        self.write('pmap', parallel_maps.reshape(self.n_chans_out).tobytes())
            

    def get_channel_outmap(self):
        """
        Read the currently loaded reorder map.

        :return: The reorder map currently loaded. Entry `i` in this map is the
            channel number which emerges in the `i`th output position.
        :rtype: list
        """

        serial_maps = np.zeros([self._n_parallel_chans_in, self._n_serial_chans_in],
                          dtype='>%s' % self._map_format)
        parallel_maps = np.zeros([self._n_parallel_chans_out, self._n_serial_chans_in],
                          dtype='>B')

        nbytes_s = len(serial_maps[0].tobytes())
        for i in range(self._n_parallel_chans_in):
            raw = self.read(f'reorder_{i}_{self._map_reg}', nbytes_s)
            serial_maps[i] = np.frombuffer(raw, dtype=serial_maps.dtype)
        nbytes_p = len(parallel_maps.tobytes())
        raw = self.read('pmap', nbytes_p)
        parallel_map1d = np.frombuffer(raw, dtype=parallel_maps.dtype)
        parallel_maps[:,:] = parallel_map1d.reshape(parallel_maps.shape)

        outmap = np.zeros(self.n_chans_out, dtype=int)
        for outn in range(self.n_chans_out):
            # Which output parallel stream is output outn in
            out_pstream = outn % self._n_parallel_chans_out
            # Which output serial position is output outn in
            out_spos = outn // self._n_parallel_chans_out
            # Which input parallel stream was feeding out_pstream?
            in_pstream = parallel_maps[out_pstream, out_spos]
            # Which input serial position was feeding out_spos
            in_stream = serial_maps[in_pstream, out_spos]
            # convert to an input channel number
            in_chan = in_stream * self._n_parallel_chans_in + in_pstream
            outmap[outn] = in_chan
        return outmap
        

    def initialize(self, read_only=False):
        """
        Initialize the block.

        :param read_only: If True, this method is a no-op. If False,
            initialize the block with the identity map. I.e., map channel
            `n` to channel `n`.
        :type read_only: bool
        """
        if read_only:
            pass
        else:
            chan_order = np.arange(0, self.n_chans_out) # output first channels
            self.set_channel_outmap(chan_order)
