import logging
import yaml
import casperfpga
from . import helpers
from . import __version__
from .error_levels import *
from .blocks import fpga
from .blocks import rfdc
from .blocks import sync
#from .blocks import noisegen
from .blocks import input
#from .blocks import delay
from .blocks import pfb
#from .blocks import mask
from .blocks import autocorr
#from .blocks import eq
from .blocks import pfbtvg
from .blocks import chanreorder
from .blocks import mixer
from .blocks import accumulator
from .blocks import generator
from .blocks import output
#from .blocks import packetizer
#from .blocks import eth
#from .blocks import corr
#from .blocks import powermon

    

class SoukMkidReadout():
    """
    A control class for SOUK MKID Readout firmware on a single board

    :param host: Hostname/IP address of FPGA board
    :type host: str

    :param fpgfile: Path to .fpg file running on the board
    :type fpgfile: str

    :param configfile: Path to configuration YAML file for system
    :type configfile: str

    :param logger: Logger instance to which log messages should be emitted.
    :type logger: logging.Logger

    """
    def __init__(self, host, fpgfile=None, configfile=None, logger=None):
        self.hostname = host #: hostname of FPGA board
        #: Python Logger instance
        self.logger = logger or helpers.add_default_log_handlers(logging.getLogger(__name__ + ":%s" % (host)))
        #: fpgfile currently in use
        self.fpgfile = fpgfile
        #: configuration YAML file
        self.configfile = configfile
        self.config = {}
        self.adc_clk_mhz = None
        #: Underlying CasperFpga control instance
        self._cfpga = casperfpga.CasperFpga(
                        host=self.hostname,
                        transport=casperfpga.KatcpTransport,
                    )
        # Try to read configuration files
        if configfile is not None:
            self.read_config(configfile)
        if fpgfile is not None:
            self.read_fpg(fpgfile)
        self.blocks = {}
        try:
            self._initialize_blocks()
        except:
            self.logger.exception("Failed to initialize firmware blocks. "
                                  "Maybe the board needs programming.")

    def is_connected(self):
        """
        :return: True if there is a working connection to a board. False otherwise.
        :rtype: bool
        """
        return self._cfpga.is_connected()

    def read_fpg(self, f):
        helpers.file_exists(f, self.logger)
        try:
            self._cfpga.get_system_information(f)
        except:
            self.logger.exception(f"Failed to parse fpg file {f}")
            raise

    def read_config(self, f):
        helpers.file_exists(f, self.logger)
        try:
            with open(f, 'r') as fh:
                self.config = yaml.load(fh.read(), Loader=yaml.loader.SafeLoader)
        except:
            self.logger.exception(f"Failed to parse config file {f}")
            raise
        self.fpgfile = self.config.get('fpgfile', self.fpgfile)
        self.adc_clk_mhz = self.config.get('adc_clk_mhz', None)
        if self.fpgfile is not None:
            self.read_fpg(self.fpgfile)
        
    def get_status_all(self):
        """
        Call the ``get_status`` methods of all blocks in ``self.blocks``.
        If the FPGA is not programmed with F-engine firmware, will only
        return basic FPGA status.

        :return: (status_dict, flags_dict) tuple.
            Each is a dictionary, keyed by the names of the blocks in
            ``self.blocks``. These dictionaries contain, respectively, the
            status and flags returned by the ``get_status`` calls of
            each of this F-Engine's blocks.
        """
        stats = {}
        flags = {}
        if not self.blocks['fpga'].is_programmed():
            stats['fpga'], flags['fpga'] = self.blocks['fpga'].get_status()
        else:
            for blockname, block in self.blocks.items():
                try:
                    stats[blockname], flags[blockname] = block.get_status()
                except:
                    self.logger.info("Failed to poll stats from block %s" % blockname)
        return stats, flags

    def print_status_all(self, use_color=True, ignore_ok=False):
        """
        Print the status returned by ``get_status`` for all blocks in the system.
        If the FPGA is not programmed with F-engine firmware, will only
        print basic FPGA status.

        :param use_color: If True, highlight values with colors based on
            error codes.
        :type use_color: bool

        :param ignore_ok: If True, only print status values which are outside the
           normal range.
        :type ignore_ok: bool

        """
        if not self.blocks['fpga'].is_programmed():
            print('FPGA stats (not programmed with F-engine image):')
            self.blocks['fpga'].print_status()
        else:
            for blockname, block in self.blocks.items():
                print('Block %s stats:' % blockname)
                block.print_status(use_color=use_color, ignore_ok=ignore_ok)

    def program(self, fpgfile=None):
        """
        Program an .fpg file to an FPGA. 

        :param fpgfile: The .fpg file to be loaded. Should be a path to a
            valid .fpg file. If None is given, `self.fpgfile`
            will be loaded. If this is None, RuntimeError is raised
        :type fpgfile: str

        """

        if fpgfile is not None:
            helpers.file_exists(fpgfile, self.logger)
            self.fpgfile = fpgfile
        if self.fpgfile is None:
            self.logger.exception("Couldn't figure out what .fpg to program")
            raise RuntimeError
        self.logger.info(f"Programming with {self.fpgfile}")
        self._cfpga.upload_to_ram_and_program(self.fpgfile)
        self._initialize_blocks()

    def _initialize_blocks(self):
        """
        Initialize firmware blocks, populating the ``blocks`` attribute.
        """
        # blocks
        #: Control interface to high-level FPGA functionality
        self.fpga        = fpga.Fpga(self._cfpga, "")
        #: Control interface to RFDC block
        self.rfdc        = rfdc.Rfdc(self._cfpga, 'rfdc',
                               lmkfile=self.config.get('lmkfile', None),
                               lmxfile=self.config.get('lmxfile', None),
                           )
        #: Control interface to Synchronization / Timing block
        self.sync        = sync.Sync(self._cfpga, 'sync')
        ##: Control interface to Noise Generation block
        #self.noise       = noisegen.NoiseGen(self._cfpga, 'noise', n_noise=2, n_outputs=64)
        #: Control interface to Input Multiplex block
        self.input       = input.Input(self._cfpga, 'input')
        ##: Control interface to Coarse Delay block
        #self.delay       = delay.Delay(self._cfpga, 'delay', n_streams=64)
        #: Control interface to PFB block
        self.pfb         = pfb.Pfb(self._cfpga, 'pfb',
                               fftshift=self.config.get('fftshift', 0xffffffff),
                           )
        ##: Control interface to Mask (flagging) block
        #self.mask        = mask.Mask(self._cfpga, 'mask')
        #: Control interface to Autocorrelation block
        self.autocorr    = autocorr.AutoCorr(self._cfpga, 'autocorr',
                               n_chans=4096,
                               n_signals=1,
                               n_parallel_streams=16,
                               n_cores=1,
                               use_mux=False,
                           )
        ##: Control interface to Equalization block
        #self.eq          = eq.Eq(self._cfpga, 'eq', n_streams=64, n_coeffs=2**9)
        #: Control interface to post-PFB Test Vector Generator block
        self.pfbtvg       = pfbtvg.PfbTvg(self._cfpga, 'pfbtvg',
                                n_inputs=1,
                                n_chans=4096,
                                n_serial_inputs=1,
                                n_rams=4,
                                n_samples_per_word=4,
                                sample_format='h',
                            )
        #: Control interface to Channel Reorder block
        self.chanselect   = chanreorder.ChanReorder(self._cfpga, 'chan_select',
                                n_chans_in=4096,
                                n_chans_out=2048,
                                n_parallel_chans_in=16,
                            )
        #: Control interface to Zoom FFT
        self.zoomfft      = pfb.Pfb(self._cfpga, 'zoom_fft',
                               fftshift=0xffffffff
                            )
        #: Control interface to Zoom FFT Power Accumulator
        self.zoomacc      = accumulator.Accumulator(self._cfpga, 'zoom_acc',
                                    n_chans=1024,
                                    n_parallel_chans=1,
                                    dtype='>u8',
                                    is_complex=False,
                            )
        #: Control interface to Mixer block
        self.mixer        = mixer.Mixer(self._cfpga, 'mix',
                                n_chans=2048,
                                n_parallel_chans=8,
                                phase_bp=30,
                                phase_offset_bp=31,
                            )
        #: Control interface to Accumulator Blocks
        self.accumulators   =  []
        self.accumulators   += [accumulator.Accumulator(self._cfpga, 'acc0',
                                    n_chans=2048,
                                    n_parallel_chans=8,
                                    dtype='>i4',
                                    is_complex=True,
                                )
                               ]
        self.accumulators   += [accumulator.Accumulator(self._cfpga, 'acc1',
                                    n_chans=2048,
                                    n_parallel_chans=8,
                                    dtype='>i4',
                                    is_complex=True,
                                )
                               ]
        #: Control interface to CORDIC generators
        self.gen_cordic    = generator.Generator(self._cfpga, 'cordic_gen')
        #: Control interface to LUT generators
        self.gen_lut       = generator.Generator(self._cfpga, 'lut_gen')
        #: Control interface to Pre-Polyphase Synthesizer Reorder
        self.pfs_chanselect   = chanreorder.ChanReorder(self._cfpga, 'synth_input_reorder',
                                n_chans_in=2048,
                                n_chans_out=2048,
                                n_parallel_chans_in=8,
                                support_zeroing=True
                            )
        #: Control interface to Pre-Offset-Polyphase Synthesizer Reorder
        self.pfs_offset_chanselect = chanreorder.ChanReorder(self._cfpga, 'synth_offset_input_reorder',
                                n_chans_in=2048,
                                n_chans_out=2048,
                                n_parallel_chans_in=8,
                                support_zeroing=True
                            )
        #: Control interface to Polyphase Synthesizer block
        self.pfs           = pfb.Pfb(self._cfpga, 'psb', fftshift=0xffffffff)
        #: Control interface to Output Multiplex block
        self.output        = output.Output(self._cfpga, 'output')
        ##: Control interface to Packetizer block
        #self.packetizer  = packetizer.Packetizer(self._cfpga, 'packetizer', sample_rate_mhz=196.608)
        ##: Control interface to 40GbE interface block
        #self.eth         = eth.Eth(self._cfpga, 'eth')
        ##: Control interface to Correlation block
        #self.corr        = corr.Corr(self._cfpga,'corr_0', n_chans=2**12 // 8) # Corr module collapses channels by 8x
        ##: Control interface to Power Monitor block
        #self.powermon    = powermon.PowerMon(self._cfpga, 'powermon')

        # The order here can be important, blocks are initialized in the
        # order they appear here

        #: Dictionary of all control blocks in the firmware system.
        self.blocks = {
            'fpga'      : self.fpga,
            'rfdc'      : self.rfdc,
            'sync'      : self.sync,
            #'noise'     : self.noise,
            'input'     : self.input,
            #'delay'     : self.delay,
            'pfb'       : self.pfb,
            #'mask'      : self.mask,
            #'eq'        : self.eq,
            'pfbtvg'     : self.pfbtvg,
            'chanselect' : self.chanselect,
            'zoomfft'    : self.zoomfft,
            'zoomacc'    : self.zoomacc,
						'mixer'      : self.mixer,
            'pfs_chanselect' : self.pfs_chanselect,
            'pfs_offset_chanselect' : self.pfs_offset_chanselect,
            'pfs'        : self.pfs,
            #'packetizer': self.packetizer,
            #'eth'       : self.eth,
            'autocorr'     : self.autocorr,
            'accumulator0' : self.accumulators[0],
            'accumulator1' : self.accumulators[1],
            'output'       : self.output,
            'gen_cordic'   : self.gen_cordic,
            'gen_lut'      : self.gen_lut,
            #'corr'      : self.corr,
            #'powermon'  : self.powermon,
        }

    def initialize(self, read_only=False):
        """
        Call the ```initialize`` methods of all underlying blocks, then
        optionally issue a software global reset.

        :param read_only: If True, call the underlying initialization methods
            in a read_only manner, and skip software reset.
        :type read_only: bool
        """
        if not self.fpga.is_programmed():
            self.logger.info("Board is _NOT_ programmed")
            if not read_only:
                self.program() 
        for blockname, block in self.blocks.items():
            if read_only:
                self.logger.info("Initializing block (read only): %s" % blockname)
            else:
                self.logger.info("Initializing block (writable): %s" % blockname)
            block.initialize(read_only=read_only)
        if not read_only:
            self.logger.info("Performing software global reset")
            self.sync.arm_sync()
            self.sync.sw_sync()
