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

    :param support_zeroing: If True, allow the use of channel index ``-1`` to mean
        "zero out this channel"
    :type support_zeroing: bool

    """
    _map_format = 'i4' # CASPER library-defined map word format
    _map_reg = 'map1' # CASPER library-defined map name in reorder block
    def __init__(self, host, name,
            n_chans_in=4096,
            n_chans_out=2048,
            n_parallel_chans_in=4,
            support_zeroing=False,
            logger=None):
        super(ChanReorder, self).__init__(host, name, logger)
        assert n_chans_in % n_parallel_chans_in == 0
        # firmware uses 1 byte mux inputs, so breaks if >256 inputs,
        # or >255 inputs when using one input for zeros
        if not support_zeroing:
            assert np.log2(n_parallel_chans_in) <= 256
        else:
            assert np.log2(n_parallel_chans_in) <= 256-1
        self.support_zeroing = support_zeroing
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
        Remap the channels such that the channel outmap[i]
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
                # Allow -1 as a special case, meaning "set this output to 0"
                if self.support_zeroing and outchan == -1:
                    continue
                raise ValueError(f'Selected channel {outchan} not in input range')

        serial_maps = np.zeros([self._n_parallel_chans_in, self._n_serial_chans_in],
                          dtype='>%s' % self._map_format)
        parallel_maps = np.zeros([self._n_serial_chans_in, self._n_parallel_chans_out],
                          dtype='>i1')
        # Keep track of which entries have been written
        # so we can warn if something is overwritten
        serial_maps_written = [[False for _ in range(self._n_serial_chans_in)]
                for _ in range(self._n_parallel_chans_in)]
        parallel_maps_written = [[False for _ in range(self._n_parallel_chans_out)]
                for _ in range(self._n_serial_chans_in)]
        # outn is where we want this channel in the output
        # outchan is where this channel is at the input
        for outn, outchan in enumerate(outmap):
            if outchan != -1:
                # Which of the parallel input streams contains this channel
                in_pstream = outchan % self._n_parallel_chans_in
                # Which input serial position contains this channel
                in_spos = outchan // self._n_parallel_chans_in
            else:
                in_pstream = None
                in_spos = None
            # Which output parallel stream would we like outchan to be in
            out_pstream = outn % self._n_parallel_chans_out
            # Which output serial position would we like outchan to be in
            out_spos = outn // self._n_parallel_chans_out
            # build maps appropriately
            debug_msg = f'{outn}->{outchan} Setting input {in_pstream}:{in_spos} to {out_pstream}:{out_spos}'
            self.logger.debug(debug_msg)
            if outchan != -1:
                if serial_maps_written[in_pstream][out_spos] != False:
                    last_msg = serial_maps_written[in_pstream][out_spos]
                    self.logger.error('Serial reorder clash!')
                    self.logger.info(f'Attempted: {debug_msg}')
                    self.logger.info(f'Previously: {last_msg}')
                if parallel_maps_written[out_spos][out_pstream] != False:
                    last_msg = parallel_maps_written[out_spos][out_pstream]
                    self.logger.error('Parallel reorder clash!')
                    self.logger.info(f'Attempted: {debug_msg}')
                    self.logger.info(f'Previously: {last_msg}')
                serial_maps[in_pstream, out_spos] = in_spos
                parallel_maps[out_spos, out_pstream] = in_pstream
                serial_maps_written[in_pstream][out_spos] = debug_msg
                parallel_maps_written[out_spos][out_pstream] = debug_msg
            else:
                # Use special mux input which is tied to 0
                if parallel_maps_written[out_spos][out_pstream] != False:
                    last_msg = parallel_maps_written[out_spos][out_pstream]
                    self.logger.error('Parallel reorder clash!')
                    self.logger.info(f'Attempted: {debug_msg}')
                    self.logger.info(f'Previously: {last_msg}')
                parallel_maps[out_spos, out_pstream] = self._n_parallel_chans_in + 1
                parallel_maps_written[out_spos][out_pstream] = debug_msg
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
        parallel_maps = np.zeros([self._n_serial_chans_in, self._n_parallel_chans_out],
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
            in_pstream = parallel_maps[out_spos, out_pstream]
            # Catch special case where input is disabled
            if in_pstream == self._n_parallel_chans_in + 1:
                in_chan = -1 # -1 indicates disabled
            else:
                # Which input serial position was feeding out_spos
                in_stream = serial_maps[in_pstream, out_spos]
                # convert to an input channel number
                in_chan = in_stream * self._n_parallel_chans_in + in_pstream
            outmap[outn] = in_chan
        return outmap

    def set_single_channel(self, outidx, inidx):
        """
        Set output channel number ``outidx`` to input number ``inidx``.
        Do this by reading the total channel map, modifying a single entry,
        and writing back.

        Example usage:
            # Set the first channel out of the reorder to 33
            ```set_single_channel(0, 33)``

        :param outidx: Index of output channel to set.
        :type outidx: int

        :param inidx: Input channel index to select.
        :type inidx: int
        """
        self.logger.info(f'Setting output {outidx} to channel {inidx}')
        chanmap = self.get_channel_outmap()
        chanmap[outidx] = inidx
        self.set_channel_outmap(chanmap)
        

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
            if self.support_zeroing:
                chan_order = np.ones(self.n_chans_out) * -1 # Disable everything
            else:
                chan_order = np.arange(0, self.n_chans_in, 2) # output every other channel
            self.set_channel_outmap(chan_order)
