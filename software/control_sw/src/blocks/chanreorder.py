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

    :param parallel_first: If True, the firmware reorders in the parallel signal
        dimension before the serial dimension.
    :type parallel_first: bool

    """
    _map_format = 'i4' # CASPER library-defined map word format
    _map_reg = 'map1' # CASPER library-defined map name in reorder block
    def __init__(self, host, name,
            n_chans_in=4096,
            n_chans_out=2048,
            n_parallel_chans_in=4,
            support_zeroing=False,
            parallel_first=False,
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
        self._parallel_first = parallel_first
        self._n_parallel_chans_in = n_parallel_chans_in
        self._n_serial_chans_in = n_chans_in // n_parallel_chans_in
        # These asserts probably don't catch all configuration issues
        if not n_chans_in % n_chans_out == 0:
            self.logger.error(f'n_chans_in ({n_chans_in}) not divisible by n_chans_out ({n_chans_out})')
            raise ValueError
        self._inout_ratio = n_chans_in // n_chans_out
        assert n_parallel_chans_in % self._inout_ratio == 0
        # If reordering parallel first, the reorder is completed with the
        # same number of input and output samples in parallel, and then
        # the decimation occurs after reordering.
        # If serial reordering first, we decimate the samples prior
        # to reordering in the parallel dimension.
        if self._parallel_first:
            self._n_parallel_chans_out = n_parallel_chans_in
        else:
            self._n_parallel_chans_out = n_parallel_chans_in // self._inout_ratio

    def _validate_outmap(self, outmap):
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
        return outmap

    def set_channel_outmap(self, outmap):
        """
        Remap the channels such that the channel outmap[i]
        emerges out of the reorder map in position i.

        The provided map must be `self.n_chans_out` elements long, else
        `ValueError` is raised

        :param outmap: The outmap to which data should be mapped. I.e., if
            `outmap[0] = 16`, then the first channel out of the reorder block
            will be channel 16. 
        :type outmap: list of int

        """
        outmap = self._validate_outmap(outmap)

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
            debug_msg = f'{outn}->{outchan} Setting input (p:s) {in_pstream}:{in_spos} to {out_pstream}:{out_spos}'
            self.logger.debug(debug_msg)
            if self._parallel_first:
                # Reorder the parallel streams first,
                # so serial reorder maps should be chosen
                # based on the "new" parallel stream number
                s_reorder = out_pstream
                # Parallel map location reflects original serial position
                p_map_loc = in_spos
            else:
                # Reorder serial first,
                # so serial map choice reflects original parallel position
                s_reorder = in_pstream
                # Parallel ordering reflects new serial position
                p_map_loc = out_spos
            if outchan != -1:
                if serial_maps_written[s_reorder][out_spos] != False:
                    last_msg = serial_maps_written[s_reorder][out_spos]
                    self.logger.error('Serial reorder clash!')
                    self.logger.info(f'Attempted: {debug_msg}')
                    self.logger.info(f'Previously: {last_msg}')
                if parallel_maps_written[p_map_loc][out_pstream] != False:
                    last_msg = parallel_maps_written[p_map_loc][out_pstream]
                    self.logger.error('Parallel reorder clash!')
                    self.logger.info(f'Attempted: {debug_msg}')
                    self.logger.info(f'Previously: {last_msg}')
                serial_maps[s_reorder, out_spos] = in_spos
                parallel_maps[p_map_loc, out_pstream] = in_pstream
                serial_maps_written[s_reorder][out_spos] = debug_msg
                parallel_maps_written[p_map_loc][out_pstream] = debug_msg
            else:
                if self._parallel_first:
                    # Use special mux input which is tied to 0
                    if serial_maps_written[s_reorder][out_spos] != False:
                        last_msg = serial_maps_written[s_reorder][out_spos]
                        self.logger.error('Serial reorder clash!')
                        self.logger.info(f'Attempted: {debug_msg}')
                        self.logger.info(f'Previously: {last_msg}')
                    # This doesn't actually do anything in firmware, but makes it
                    # clear in software that we don't care about this channel
                    serial_maps[s_reorder][out_spos] = -1
                    serial_maps_written[s_reorder][out_spos] = debug_msg
                else:
                    # Use special mux input which is tied to 0
                    if parallel_maps_written[out_spos][out_pstream] != False:
                        last_msg = parallel_maps_written[out_spos][out_pstream]
                        self.logger.error('Parallel reorder clash!')
                        self.logger.info(f'Attempted: {debug_msg}')
                        self.logger.info(f'Previously: {last_msg}')
                    parallel_maps[p_map_loc, out_pstream] = self._n_parallel_chans_in + 1
                    parallel_maps_written[p_map_loc][out_pstream] = debug_msg
        for i in range(self._n_parallel_chans_in):
            self.write(f'reorder_{i}_{self._map_reg}', serial_maps[i].tobytes())
        self.write('pmap', parallel_maps.flatten().tobytes())
            

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
            if self._parallel_first:
                in_spos = serial_maps[out_pstream, out_spos] # serial input position
                if in_spos == -1: # indicates not enabled
                    in_chan = -1
                else:
                    in_pstream = parallel_maps[in_spos, out_pstream]
                    in_chan = in_spos * self._n_parallel_chans_in + in_pstream
            else:
                in_pstream = parallel_maps[out_spos, out_pstream]
                # Catch special case where input is disabled
                if in_pstream == self._n_parallel_chans_in + 1:
                    in_chan = -1 # -1 indicates disabled
                else:
                    in_stream = serial_maps[in_pstream, out_spos]
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

class ChanReorderMultiSample(ChanReorder):
    """
    Instantiate a control interface for a Channel Reorder block.

    :param host: CasperFpga interface for host.
    :type host: casperfpga.CasperFpga

    :param name: Name of block in Simulink hierarchy.
    :type name: str

    :param logger: Logger instance to which log messages should be emitted.
    :type logger: logging.Logger

    :param n_serial_chans_in: Number of serial channels input to the reorder
    :type n_serial_chans_in: int

    :param n_parallel_chans_in: Number of parallel channels input to the reorder
    :type n_parallel_chans_in: int

    :param n_parallel_samples: Number of parallel samples output
    :type n_parallel_samples: int

    :param support_zeroing: If True, allow the use of channel index ``-1`` to mean
        "zero out this channel"
    :type support_zeroing: bool
    """
    _pmap_format = '>i4'
    _map_format = '>i4'
    def __init__(self, host, name,
            n_serial_chans_in=2**9,
            n_parallel_chans_in=2**4,
            n_parallel_samples=2**2,
            support_zeroing=True,
            logger=None):
        super(ChanReorder, self).__init__(host, name, logger)
        self.n_chans_in = n_serial_chans_in * n_parallel_chans_in
        self.n_serial_chans_in = n_serial_chans_in
        self.n_parallel_chans_in = n_parallel_chans_in
        self.n_parallel_samples = n_parallel_samples
        assert n_parallel_chans_in % n_parallel_samples == 0
        self._reduction_factor = n_parallel_chans_in // n_parallel_samples # Number of parallel transpose blocks (see firmware!)
        self._reorder_depth = self.n_chans_in // self._reduction_factor
        self.support_zeroing = support_zeroing
        self.n_chans_out = self._reorder_depth

    def set_channel_outmap(self, outmap):
        """
        Remap the channels such that the channel outmap[i]
        emerges out of the reorder map in position i.

        The provided map must be `self.n_chans_out` elements long, else
        `ValueError` is raised

        :param outmap: The outmap to which data should be mapped. I.e., if
            `outmap[0] = 16`, then the first channel out of the reorder block
            will be channel 16. 
        :type outmap: list of int

        """
        serial_map = np.zeros(self._reorder_depth)
        parallel_map = (self._reduction_factor + 1) * np.ones(self._reorder_depth)

        nout = len(outmap)

        block_id = np.zeros(nout)
        block_s_offset = np.zeros(nout)
        block_p_offset = np.zeros(nout)

        outmap = np.array(outmap, dtype=int)

        block_id[:] = outmap // self.n_parallel_chans_in
        block_s_offset[:] = (outmap % self.n_parallel_chans_in) % self.n_parallel_samples
        block_p_offset[:] = (outmap % self.n_parallel_chans_in) // self.n_parallel_samples

        serial_map[0:nout] = (block_id * self.n_parallel_samples) + block_s_offset
        parallel_map[0:nout] = block_p_offset
        parallel_map[0:nout][outmap == -1] = self._reduction_factor + 1

        self.write(f'map0_{self._map_reg}', np.array(serial_map, dtype=self._map_format).tobytes())
        self.write('pmap', np.array(parallel_map, dtype=self._pmap_format).tobytes())

    def get_channel_outmap(self):
        """
        Read the currently loaded reorder map.

        :return: The reorder map currently loaded. Entry `i` in this map is the
            channel number which emerges in the `i`th output position.
        :rtype: list
        """

        nbytes = self._reorder_depth * np.dtype(self._map_format).itemsize
        serial_map = np.frombuffer(self.read(f'map0_{self._map_reg}', nbytes), dtype=self._map_format)
        nbytes = self._reorder_depth * np.dtype(self._pmap_format).itemsize
        parallel_map = np.frombuffer(self.read('pmap', nbytes), dtype=self._pmap_format)

        block_id = serial_map // self.n_parallel_samples
        block_s_offset = serial_map % self.n_parallel_samples
        block_p_offset = parallel_map

        outmap = self.n_parallel_chans_in * block_id + block_s_offset + (self.n_parallel_samples * block_p_offset)
        outmap[parallel_map == self._reduction_factor + 1] = -1
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
        assert np.dtype(self._map_format).itemsize == 4
        assert np.dtype(self._pmap_format).itemsize == 4
        block_id = inidx // self.n_parallel_chans_in
        block_s_offset = (inidx % self.n_parallel_chans_in) % self.n_parallel_samples
        block_p_offset = (inidx % self.n_parallel_chans_in) // self.n_parallel_samples
        if inidx == -1:
            block_p_offset = self._reduction_factor + 1
        else:
            self.write_int(f'map0_{self._map_reg}', block_id*self.n_parallel_samples + block_s_offset, word_offset=outidx)
        self.write_int('pmap', block_p_offset, word_offset=outidx)

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
                chan_order = np.ones(self._reorder_depth) * -1 # Disable everything
            else:
                chan_order = np.arange(0, self.n_chans_in, self._reduction_factor) # output every Nth channel
            self.set_channel_outmap(chan_order)

class ChanReorderMultiSampleIn(ChanReorder):
    """
    Instantiate a control interface for a Channel Reorder block.

    :param host: CasperFpga interface for host.
    :type host: casperfpga.CasperFpga

    :param name: Name of block in Simulink hierarchy.
    :type name: str

    :param logger: Logger instance to which log messages should be emitted.
    :type logger: logging.Logger

    :param n_serial_chans_out: Number of serial channels output from the reorder
    :type n_serial_chans_out: int

    :param n_parallel_chans_out: Number of parallel channels output from the reorder
    :type n_parallel_chans_out: int

    :param n_parallel_samples: Number of parallel samples input
    :type n_parallel_samples: int

    """
    _map_format = '>i4'
    def __init__(self, host, name,
            n_serial_chans_out=2**9,
            n_parallel_chans_out=2**4,
            n_parallel_samples=2**2,
            logger=None):
        super(ChanReorder, self).__init__(host, name, logger)
        self.n_chans_out = n_serial_chans_out * n_parallel_chans_out
        self.n_serial_chans_out = n_serial_chans_out
        self.n_parallel_chans_out = n_parallel_chans_out
        self.n_parallel_samples = n_parallel_samples
        assert n_parallel_chans_out % n_parallel_samples == 0
        self._expansion_factor = n_parallel_chans_out // n_parallel_samples
        self._reorder_depth = self.n_chans_out // self._expansion_factor
        self.n_chans_in = self._reorder_depth

    def set_channel_outmap(self, outmap):
        """
        Remap the channels such that the channel outmap[i]
        emerges out of the reorder map in position i.

        The provided map must be `self.n_chans_out` elements long, else
        `ValueError` is raised

        :param outmap: The outmap to which data should be mapped. I.e., if
            `outmap[0] = 16`, then the first channel out of the reorder block
            will be channel 16. 
        :type outmap: list of int

        """
        # default to outputting last input
        serial_maps = (self.n_chans_in - 1) * np.ones([self._expansion_factor, self._reorder_depth])
        outmap = np.array(outmap, dtype=int)
        nout = len(outmap)

        outchans = np.arange(self.n_chans_out)
        # Which parallel path does a given output channel
        # map to
        block_id = (outchans // self.n_parallel_samples) % self._expansion_factor
        # Which serial position in this path does a channel map to
        block_s_offset = (outchans // self.n_parallel_chans_out)
        # Which parallel position in this word in this path
        block_p_offset = (outchans % self.n_parallel_samples)

        # Combined position in a block
        block_offset = block_s_offset * self.n_parallel_samples + block_p_offset

        # We want the user-select channel to end up in position `block_offset` of the block `block_id`
        for i in range(nout):
            serial_maps[block_id[i], block_offset[i]] = outmap[i]

        serial_maps = np.array(serial_maps, dtype=self._map_format)

        for i in range(self._expansion_factor):
            self.write(f'map{i}_{self._map_reg}', serial_maps[i].tobytes())

    def get_channel_outmap(self):
        """
        Read the currently loaded reorder map.

        :return: The reorder map currently loaded. Entry `i` in this map is the
            channel number which emerges in the `i`th output position.
        :rtype: list
        """
        nbytes = self._reorder_depth * np.dtype(self._map_format).itemsize
        serial_maps = np.zeros([self._expansion_factor, self._reorder_depth])
        for i in range(self._expansion_factor):
            serial_maps[i] = np.frombuffer(self.read(f'map{i}_{self._map_reg}', nbytes), dtype=self._map_format)

        # Which serial position in each path does a channel map to
        block_s_offset = serial_maps // self.n_parallel_samples
        # Which parallel position in this word in this path
        block_p_offset = serial_maps % self.n_parallel_samples

        outmap = np.zeros(self.n_chans_out, dtype=int)
        for i in range(self._expansion_factor):
            for j in range(self._reorder_depth):
                s_off = j // self.n_parallel_samples
                p_off = j % self.n_parallel_samples
                outmap[i * self.n_parallel_samples + s_off*self.n_parallel_chans_out + p_off] = serial_maps[i, j]
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
        assert np.dtype(self._map_format).itemsize == 4
        # Which parallel path does a given output channel map to
        block_id = (outidx // self._expansion_factor) % self.n_parallel_samples
        # Which serial position in this path does a channel map to
        block_s_offset = (outidx // self.n_parallel_chans_out)
        # Which parallel position in this word in this path
        block_p_offset = (outidx % self.n_parallel_samples)

        # Combined position in a block
        block_offset = block_s_offset * self.n_parallel_samples + block_p_offset
        self.write_int(f'map{block_id}_{self._map_reg}', inidx, word_offset=block_offset)
        

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
            chan_order = (self.n_chans_in - 1) * np.ones(self.n_chans_out) # output all last channel
            self.set_channel_outmap(chan_order)

class ChanReorderPS(ChanReorder):
    """
    Instantiate a control interface for a Channel Reorder "Parallel First" block.

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
        outmap = self._validate_outmap(outmap)

        serial_maps = np.zeros([self._n_parallel_chans_in, self._n_serial_chans_in],
                          dtype='>%s' % self._map_format)
        parallel_maps = np.zeros([self._n_serial_chans_in, self._n_parallel_chans_in],
                          dtype='>i1')
        # Keep track of which entries have been written
        # so we can warn if something is overwritten
        serial_maps_written = [[False for _ in range(self._n_serial_chans_in)]
                for _ in range(self._n_parallel_chans_in)]
        parallel_maps_written = [[False for _ in range(self._n_parallel_chans_in)]
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
            out_pstream = outn % self._n_parallel_chans_in
            # Which output serial position would we like outchan to be in
            out_spos = outn // self._n_parallel_chans_in
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
