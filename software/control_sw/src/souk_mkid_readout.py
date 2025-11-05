from os import path
import logging
import yaml
import time
import numpy as np
import casperfpga

from . import helpers
from . import __version__
from .error_levels import *
from .blocks import fpga
from .blocks import rfdc
from .blocks import adc_snapshot
from .blocks import dac_snapshot
from .blocks import sync
from .blocks import input
from .blocks import pfb
from .blocks import zoom_pfb
#from .blocks import mask
from .blocks import autocorr
#from .blocks import eq
from .blocks import pfbtvg
from .blocks import chanreorder
from .blocks import mixer
from .blocks import accumulator
from .blocks import generator
from .blocks import psbscale
from .blocks import output
from .blocks import common
from .blocks import delay
#from .blocks import packetizer
#from .blocks import eth
#from .blocks import corr
#from .blocks import powermon

N_TONE = 2048 # Number of independent tones the design can generate
N_RX_OVERSAMPLE = 2 # RX channelizer oversampling factor
ADC_FPGA_DEMUX_RATIO = 8 # ADC samples per FPGA clock
N_RX_FFT = N_RX_OVERSAMPLE*4096 # Number of FFT points in RX channelizer 
N_TX_FFT = 4096 # Number of FFT points in TX synthesizer (not including oversampling)
SYNC_DELAY = 5712 # TX vs RX skew as measured with firmware loopback

FW_TYPE_PARAMS = {
        10: {
            'n_chan_rx': 2**16,
            'rx_only': True,
            'pfb_descrambled':True,
            },
        'defaults': {
            'n_chan_rx': N_RX_FFT,
            'rx_only': False,
            'pfb_descrambled':False,
            },
        }

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

    :param pipeline_id: Pipeline number within a single RFSoC board.
    :type pipeline_id: int

    :param local: If True, use local memory accesses rather than katcp. Only works as root!
    :type local: bool

    """
    def __init__(self, host, fpgfile=None, configfile=None, logger=None, pipeline_id=0, local=False):
        self.hostname = host #: hostname of FPGA board
        #: Python Logger instance
        self.logger = logger or helpers.add_default_log_handlers(logging.getLogger(f'{__name__}:{host}:{pipeline_id}'))
        #: fpgfile currently in use
        self.fpgfile = fpgfile
        #: configuration YAML file
        self.configfile = configfile
        self.config = {}
        self.adc_clk_hz = None
        self.pipeline_id = pipeline_id
        self.fw_params = None
        #: CasperFpga transport class
        if local:
            transport = casperfpga.LocalMemTransport
        else:
            transport = casperfpga.KatcpTransport
        #: Underlying CasperFpga control instance
        self._cfpga = casperfpga.CasperFpga(
                        host=self.hostname,
                        transport=transport,
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
            self.logger.exception("Failed to initialize firmware blocks.")

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
            if self._cfpga.is_running():
                self._get_adc_clk_hz()
        except:
            self.logger.exception(f"Failed to parse fpg file {f}")
            raise

    def _get_adc_clk_hz(self):
        """
        Try to get the current ADC clock rate by examining
        the FPGA fabric rate and multiplying by the expected demux ratio.
        """
        try:
            rfdc = self._cfpga.adcs['rfdc']
            fpga_clk_hz = int(rfdc.get_fabric_clk_freq(0, 'adc') * 1e6)
            self.adc_clk_hz = fpga_clk_hz * ADC_FPGA_DEMUX_RATIO
        except:
            self.logger.warning('Tried to get adc_clk_hz and failed')

    def read_config(self, f):
        helpers.file_exists(f, self.logger)
        try:
            with open(f, 'r') as fh:
                self.config = yaml.load(fh.read(), Loader=yaml.loader.SafeLoader)
        except:
            self.logger.exception(f"Failed to parse config file {f}")
            raise
        fpgfile = self.config.get('fpgfile', self.fpgfile)
        if fpgfile is not None and fpgfile.startswith('.'):
            fpgfile = path.realpath(path.join(path.dirname(f), fpgfile))
        self.fpgfile = fpgfile
        try:
            self.adc_clk_hz = self.config['adc_clk_hz']
        except KeyError:
            pass
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
        realpath = path.realpath(self.fpgfile)
        self.logger.info(f"Programming with {realpath}")
        self._cfpga.upload_to_ram_and_program(realpath)
        self._initialize_blocks()
        self.rfdc.initialize() # Required before attempting to read ADC clock
        self._get_adc_clk_hz()

    def _initialize_blocks(self, ignore_unsupported=False):
        """
        Initialize firmware blocks, populating the ``blocks`` attribute.

        :param ignore_unsupported: If True, try initializing all blocks even if the firmware
            version doesn't match that supported by this software.
        :type ignore_unsupported: bool
        """
        # blocks
        prefix = f'p{self.pipeline_id}_'
        #: Control interface to high-level FPGA functionality
        self.fpga        = fpga.Fpga(self._cfpga, "")
        if not self.fpga.is_programmed():
            self.logger.info('Board is not programmed with valid firmware. Skipping block initialization')
            return
        if not self.fpga.check_firmware_support():
            self.logger.error('Firmware not supported. Try reprogramming with self.program()')
            if not ignore_unsupported:
                raise RuntimeError
        fw_type = self.fpga.get_firmware_type()
        try:
            self.fw_params = FW_TYPE_PARAMS[fw_type]
        except KeyError:
            try:
                self.fw_params = FW_TYPE_PARAMS['defaults']
            except KeyError:
                self.logger.error('No default firmware parameters available!')
                raise
        #: Common block shared with other pipelines
        self.common      = common.Common(self._cfpga, 'common')
        #: Control interface to RFDC block
        self.rfdc        = rfdc.Rfdc(self._cfpga, 'rfdc',
                               lmkfile=self.config.get('lmkfile', None),
                               lmxfile=self.config.get('lmxfile', None),
                               pipeline_id=self.pipeline_id,
                           )
        #: Control interface to Synchronization / Timing block
        self.sync        = sync.Sync(self._cfpga, f'{prefix}sync', sync_delay=SYNC_DELAY)
        #: Control interface to Input Multiplex block
        self.input       = input.Input(self._cfpga, f'{prefix}input')
        #: Control interface to ADC Snapshot block
        self.adc_snapshot = adc_snapshot.AdcSnapshot(self._cfpga, f'common_adc_ss')
        #: Control interface to DAC Snapshot block
        self.dac_snapshot = dac_snapshot.DacSnapshot(self._cfpga, f'common_dac_ss')

        #: Control interface to PFB block
        self.pfb         = pfb.Pfb(self._cfpga, f'{prefix}pfb',
                               fftshift=self.config.get('fftshift', 0xffffffff),
                           )
        #: Control interface to Autocorrelation block
        self.autocorr    = autocorr.AutoCorr(self._cfpga, f'common_autocorr',
                               n_chans=self.fw_params['n_chan_rx'],
                               n_signals=1,
                               n_parallel_streams=16,
                               n_cores=1,
                               use_mux=False,
                               is_descrambled=self.fw_params['pfb_descrambled'],
                           )
        #: Control interface to post-PFB Test Vector Generator block
        self.pfbtvg       = pfbtvg.PfbTvg(self._cfpga, f'{prefix}pfbtvg',
                                n_inputs=1,
                                n_chans=self.fw_params['n_chan_rx'],
                                n_serial_inputs=1,
                                n_rams=0,
                                n_samples_per_word=4,
                                sample_format='h',
                            )
        #: Control interface to Channel Reorder block
        if not self.fw_params['rx_only']:
            self.chanselect   = chanreorder.ChanReorderMultiSample(self._cfpga, f'{prefix}chan_select',
                                    n_serial_chans_in=self.fw_params['n_chan_rx'] // 2**4,
                                    n_parallel_chans_in = 2**4,
                                    n_parallel_samples=2**2,
                                    support_zeroing=True,
                                    default_descramble_input = not self.fw_params['pfb_descrambled'],
                                )
        #: Control interface to Zoom FFT
        self.zoomfft      = zoom_pfb.ZoomPfb(self._cfpga, f'common_zoom_fft',
                               fftshift=0xffffffff
                            )
        #: Control interface to Zoom FFT Power Accumulator
        self.zoomacc      = accumulator.Accumulator(self._cfpga, f'common_zoom_acc',
                                    n_chans=1024,
                                    n_parallel_chans=1,
                                    n_parallel_samples=4,
                                    dtype='>u8',
                                    is_complex=False,
                                    has_dest_ip=False,
                            )
        #: Control interface to Mixer block
        self.mixer        = mixer.Mixer(self._cfpga, f'{prefix}mix',
                                n_chans=N_TONE,
                                n_upstream_chans=self.fw_params['n_chan_rx'],
                                upstream_oversample_factor = N_RX_OVERSAMPLE,
                                n_parallel_chans=1,
                                phase_bp=31,
                                phase_offset_bp=31,
                                n_scale_bits=12,
                                n_ri_step_bits=16,
                            )
        if not self.fw_params['rx_only']:
            #: Control interface to Accumulator Blocks
            self.accumulators   =  []
            self.accumulators   += [accumulator.WindowedAccumulator(self._cfpga, f'{prefix}acc0',
                                        n_chans=N_TONE,
                                        n_parallel_chans=1,
                                        n_parallel_samples=4,
                                        dtype='>i4',
                                        is_complex=True,
                                        has_dest_ip=True,
                                        window_n_points=2**11,
                                    )
                                   ]
            self.accumulators   += [accumulator.WindowedAccumulator(self._cfpga, f'{prefix}acc1',
                                        n_chans=N_TONE,
                                        n_parallel_chans=1,
                                        n_parallel_samples=4,
                                        dtype='>i4',
                                        is_complex=True,
                                        has_dest_ip=True,
                                        window_n_points=2**11,
                                    )
                                   ]
        #: Control interface to CORDIC generators
        self.gen_cordic    = generator.Generator(self._cfpga, f'common_cordic_gen')
        #: Control interface to LUT generators
        self.gen_lut       = generator.Generator(self._cfpga, f'common_lut_gen')
        if not self.fw_params['rx_only']:
            #: Control interface to Pre-Polyphase Synthesizer Reorder
            self.psb_chanselect = chanreorder.VaccReorderMultiSampleIn(self._cfpga, f'{prefix}synth_input_reorder',
                                    n_serial_chans_out = N_TONE // 4,
                                    n_parallel_chans_out=16,
                                    n_parallel_samples=4,
                                )
            #: Control interface to Polyphase Synthesizer block
            self.psb           = pfb.Pfb(self._cfpga, f'{prefix}psb', fftshift=0b111)
            #: Control interface to PSB scale block
            self.psbscale      = psbscale.PsbScale(self._cfpga, f'{prefix}psb') # This is a hack because the scale doesn't have its own block
            #: Control interface to Output Multiplex block
            self.output        = output.Output(self._cfpga, f'{prefix}output')
            #: Control interface to output Delay block
            self.out_delay     = delay.Delay(self._cfpga, f'{prefix}outdelay')

        # The order here can be important, blocks are initialized in the
        # order they appear here

        #: Dictionary of all control blocks in the firmware system.
        self.blocks = {}
        self.blocks['fpga'       ] =  self.fpga
        self.blocks['rfdc'       ] =  self.rfdc
        self.blocks['sync'       ] =  self.sync
        self.blocks['input'      ] =  self.input
        self.blocks['pfb'        ] =  self.pfb
        self.blocks['pfbtvg'     ] =  self.pfbtvg
        self.blocks['autocorr'     ] =  self.autocorr
        self.blocks['gen_cordic'   ] =  self.gen_cordic
        self.blocks['gen_lut'      ] =  self.gen_lut
        self.blocks['psbscale'     ] =  self.psbscale
        self.blocks['zoomfft'    ] =  self.zoomfft
        self.blocks['zoomacc'    ] =  self.zoomacc
        if not self.fw_params['rx_only']:
            self.blocks['chanselect' ] =  self.chanselect
            self.blocks['mixer'      ] =  self.mixer
            self.blocks['psb_chanselect'] =  self.psb_chanselect
            self.blocks['psb'        ] =  self.psb
            self.blocks['psbscale'   ] =  self.psbscale
            self.blocks['accumulator0' ] =  self.accumulators[0]
            self.blocks['accumulator1' ] =  self.accumulators[1]
            self.blocks['output'       ] =  self.output
            self.blocks['out_delay'    ] =  self.out_delay

    def use_dual_dac(self):
        """
        Use dual DAC outputs, with 1 output for "even" frequency tones, and another for "odd".
        """
        self.fpga.write_int(f'p{self.pipeline_id}_use_dual_dac', 1)

    def use_single_dac(self):
        """
        Use single DAC output, with "even" and "odd" frequency tones summed.
        """
        self.fpga.write_int(f'p{self.pipeline_id}_use_dual_dac', 0)

    #def get_rx_tx_skew(self):
    #    """
    #    Get the difference in arrival time of a sync pulse at the start of the RX chain
    #    and at the end of the TX chain, in units of FPGA clock cycles.
    #    Depending on the `mix` block signal sharing settings, this is either the total
    #    latency (when the TX pipeline sync is shared with the RX pipeline sync) or
    #    is the residual skew when the RX pipeline sync is a delayed copy of the TX sync.

    #    :return: Sync time difference, in FPGA clock cycles
    #    :rtype: int
    #    """
    #    return self.fpga.read_uint(f'p{self.pipeline_id}_rx_tx_skew')

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
            self.use_single_dac()
            self.logger.info("Detecting and compensating RX vs TX pipeline skew")
            self.sync.arm_sync()
            self.sync.sw_sync()
            #skew = self.sync.get_pipeline_latency()
            skew = SYNC_DELAY
            self.sync.set_delay(skew)
            self.logger.info(f"Set sync delay to {skew} FPGA clocks")
            self.logger.info("Performing software global reset")
            self.sync.arm_sync()
            self.sync.sw_sync()

    def reset_psb_outputs(self):
        """
        Zero out all synthesis bank outputs.
        """
        for synth in [self.psb_chanselect, self.psb_offset_chanselect]:
            synth.initialize()

    def _get_closest_pfb_bin(self, freq_hz):
        """
        Return the bin index of the closest PFB bin to a given tone frequency,
        and the offset from this bin center, in Hz.

        :param freq_hz: Tone frequency, in Hz
        :type freq_hz: float

        :return: PFB bin index, offset from this bin in Hz
        :rtype: (int, float)
        """
        # Select appropriate RX FFT bin and place this in tone slot ``tone_id``
        rx_bin_centers_hz = np.fft.fftfreq(self.fw_params['n_chan_rx'], 1./self.adc_clk_hz)
        rx_bin_centers_hz += self.adc_clk_hz/2. # account for upstream mixing
        # Distance of freq_hz from each bin center
        rx_freq_bins_offset_hz = freq_hz - rx_bin_centers_hz
        # Index of nearest bin
        rx_nearest_bin = np.argmin(np.abs(rx_freq_bins_offset_hz))
        rx_freq_offset_hz = rx_freq_bins_offset_hz[rx_nearest_bin]
        return rx_nearest_bin, rx_freq_offset_hz

    def _get_closest_psb_bin(self, freq_hz):
        """
        Return the bin index of the closest Polyphase Synthesis bin
        to a given tone frequency.

        :param freq_hz: Tone frequency, in Hz
        :type freq_hz: float

        :return: PSB bin index
        :rtype: int
        """
        # Select appropriate transmission FFT bin number (x2 because there are 2 banks)
        tx_bin_centers_hz = np.fft.fftfreq(2*N_TX_FFT, 1./self.adc_clk_hz)
        tx_bin_centers_hz += self.adc_clk_hz/2. # account for downstream mixing
        # Distance of desired tone from these centers
        tx_freq_bins_offset_hz = freq_hz - tx_bin_centers_hz
        # Index of nearest bin
        tx_nearest_bin = np.argmin(np.abs(tx_freq_bins_offset_hz))
        return tx_nearest_bin

    def set_multi_tone(self, freqs_hz, phase_offsets_rads=None, amplitudes=None, los=['rx','tx']):
        """
        Configure both TX and RX paths for ``i`` tones at frequencies ``freqs_hz[i]``.
        Disables all tones except those provided.

        :param freqs_hz: Tone frequencies, in Hz.
        :type freqs_hz: list of float

        :param phase_offsets_rads: Phase offset of tones, in radians. If none is
            provided, offsets of 0 are used.
        :type phase_offsets_rads: list of float

        :param amplitudes: Relative amplitude of tones, provided as a list
            of floats between 0 and 1. If none is provided, amplitudes of 1.0
            are used.
        :type amplitudes: list of float

        :param los: List of LOs to write to. Can be ['rx'], ['tx'] or ['rx', 'tx']
        :type los: list
        """

        # Start with maps with everything disabled
        n_tones = len(freqs_hz)
        if phase_offsets_rads is None:
            phase_offsets_rads = np.zeros(n_tones, dtype=float)
        if amplitudes is None:
            amplitudes = np.ones(n_tones, dtype=float)
        assert len(freqs_hz) == n_tones
        assert len(phase_offsets_rads) == n_tones
        assert len(amplitudes) == n_tones
        chanmap_in = -1*np.ones(self.chanselect.n_chans_out, dtype=int)
        chanmap_psb = -1*np.ones(self.psb_chanselect.n_chans_out, dtype=int)
        lo_freqs_hz = np.zeros(n_tones, dtype=float)
        
        for fn, freq_hz in enumerate(freqs_hz):
            ### Configure receiving side
            rx_nearest_bin, rx_freq_offset_hz = self._get_closest_pfb_bin(freq_hz)
            chanmap_in[fn] = rx_nearest_bin
            lo_freqs_hz[fn] = rx_freq_offset_hz
            ### Configure transmit side
            tx_nearest_bin = self._get_closest_psb_bin(freq_hz)
            chanmap_psb[tx_nearest_bin] = fn
        # Write input map
        self.chanselect.set_channel_outmap(chanmap_in)
        # Write mixer tones
        self.mixer.set_freqs(lo_freqs_hz, phase_offsets_rads, amplitudes, self.adc_clk_hz, los)
        # Write output maps
        self.psb_chanselect.set_channel_outmap(chanmap_psb)

    def set_output_psb_scale(self, nshift, scale=1., check_overflow=True):
        """
        Set the PSB to scale down by 2^nshift in amplitude.

        :param nshift: Number of shift down stages in the PSB FFTs
        :type nshift: int

        :param scale: Post PSB scaling factor
        :type scale: float

        :param check_overflow: If True, warn about PSB overflow before returning.
        :type check_overflow: bool

        :return: If check_overflow is set, return FENG_OK if no overflows are detected,
            of FENG_ERROR otherwise. Return FENG_OK if check_overflow is not set.
        :rtype: int

        """
        shift = 2**nshift - 1
        self.psb.set_fftshift(shift)
        self.psbscale.set_scale(scale)
        if not check_overflow:
            return FENG_OK
        rv = FENG_OK
        psb_of = self.psb.get_overflow_count()
        psbsum_of = self.psbscale.get_overflow_count()
        time.sleep(1)
        if not self.psb.get_overflow_count() == psb_of:
            self.logger.warning('PSB appears to be overflowing. Check psb.get_status() for more info')
            rv = FENG_ERROR
        if not psbsum_of == 0:
            self.logger.warning('PSB overflow when summing overlapped banks')
            rv = FENG_ERROR
        return rv

    def set_tone(self, tone_id, freq_hz, phase_offset_rads=0.0, amp=1.0):
        """
        Configure both TX and RX paths for a tone at frequency ``freq_hz``
        with ID ``tone_id``.

        :param tone_id: Index number of tone to set
        :type tone_id: int

        :param freq_hz: Tone frequency, in Hz. Or, use ``None`` to disable
            this tone index.
        :type freq_hz: float

        :param phase_offset_rads: Phase offset of tone, in radians.
        :type phase_offset_rads: float

        :param amp: Tone amplitude, (<=1.0)
        :type amp: float
        """

        assert tone_id < N_TONE, f'Only tone IDs 0..{N_TONE-1} supported'
        # Disable anywhere either synthesizer is already using this tone ID
        # TODO: is this the best behaviour?
        chanmap = self.psb_chanselect.get_channel_outmap()
        for b in np.where(chanmap == tone_id)[0]:
            self.psb_chanselect.set_single_channel(b, -1)
        if freq_hz is None:
            return
        ### Configure receiving side
        rx_nearest_bin, rx_freq_offset_hz = self._get_closest_pfb_bin(freq_hz)
        # Put this bin in the correct tone slot
        self.chanselect.set_single_channel(tone_id, rx_nearest_bin)
        # Configure the mixer at this ID to the appropriate offset freq
        self.mixer.set_chan_freq(tone_id, freq_offset_hz=rx_freq_offset_hz,
                                 phase_offset=phase_offset_rads,
                                 sample_rate_hz=self.adc_clk_hz)
        self.mixer.set_amplitude_scale(tone_id, amp)
        
        ### Configure transmit side
        # Index of nearest bin
        tx_nearest_bin = self._get_closest_psb_bin(freq_hz)
        # Get index of nearest bin, and place tone in this bin for relevant
        # synth bank.
        self.psb_chanselect.set_single_channel(tx_nearest_bin, tone_id)
