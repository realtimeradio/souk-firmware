.. _control-interface:

Control Interface
=================

Overview
--------

A Python class ``SoukMkidReadout`` is provided to encapsulate control
of individual blocks in the firmware DSP pipeline.
The structure of the software interface aims to mirror the hierarchy of
the firmware modules, through the use of multiple ``Block`` class instances,
each of which encapsulates control of a single module in the firmware pipeline.

In testing, and interactive debugging, the ``SoukMkidReadout`` class provides
an easy way to probe board status for a RFSoC board on the local network.

``SoukMkidReadout`` Python Interface
------------------------------------

The ``SoukMkidReadout`` class can be instantiated and used to control
a single RFSoC board running LWA's F-Engine firmware. An example is below:


.. code-block:: python

  # Import the RFSoC F-Engine library
  from souk_mkid_readout import SoukMkidReadout

  # Instantiate a SoukMkidReadout instance to a board with
  # hostname 'my_zcu111'
  f = SoukMkidReadout('my_zcu111', configfile='my_config.yaml')

  # Program a board (if it is not already programmed)
  # and initialize all the firmware blocks
  if not f.fpga.is_programmed():
    f.program() # Load whatever firmware is specified in the configuration file
    # Initialize firmware blocks
    f.initialize()

  # Blocks are available as items in the SoukMkidReadout `blocks`
  # dictionary, or can be accessed directly as attributes
  # of the SoukMkidReadout.

  # Print available block names
  print(sorted(f.blocks.keys()))
  # Returns (eg):
  # ['rfdc', 'input', 'autocorr', 'pfb', 'pfbtvg', 'chanreorder', 'mix',
  # 'gen_lut', 'gen_cordic', 'output', 'accumulator0', 'accumulator1']

  # Grab some ADC data from the ADC
  adc_data = f.input.get_adc_snapshot()

Details of the methods provided by individual blocks are given in the next
section.


Top-Level Control
+++++++++++++++++

The Top-level ``SoukMkidReadout`` instance can be used to perform high-level
control of the firmware, such as programming and de-programming FPGA boards.
It can also be used to apply configurations which affect multiple firmware
subsystems, such as configuring LO settings.

Finally, a ``SoukMkidReadout`` instance can be used to initialize, or get status
from, all underlying firmware modules.

.. autoclass:: souk_mkid_readout.SoukMkidReadout
  :no-show-inheritance:
  :members:

.. _control-fpga:

Common Pipeline Infrastructure
++++++++++++++++++++++++++++++

The ``common`` block interface controls the multiplexors feeding
logic shared between multiple DSP pipelines.

.. autoclass:: souk_mkid_readout.blocks.common.Common
  :no-show-inheritance:
  :members:

FPGA Control
++++++++++++

The ``FPGA`` control interface allows gathering of FPGA statistics such
as temperature and voltage levels. Its methods are functional regardless of
whether the FPGA is programmed with an LWA F-Engine firmware design.

.. autoclass:: souk_mkid_readout.blocks.fpga.Fpga
  :no-show-inheritance:
  :members:

Timing Control
++++++++++++++

The ``Sync`` control interface provides an interface to configure and monitor the
multi-RFSoC timing distribution system.

.. autoclass:: souk_mkid_readout.blocks.sync.Sync
  :no-show-inheritance:
  :members:

.. _control-adc:

RFDC Control
++++++++++++

The ``Rfdc`` control interface allows control of the RFSoC's ADCs and DACs.

.. autoclass:: souk_mkid_readout.blocks.rfdc.Rfdc
  :no-show-inheritance:
  :members:

ADC Snapshot
++++++++++++

The ``AdcSnapshot`` control interface allows the capture of raw ADC samples.

.. autoclass:: souk_mkid_readout.blocks.adc_snapshot.AdcSnapshot
  :no-show-inheritance:
  :members:

Input Control
+++++++++++++

The ``Input`` control interface controls the multiplexors at the start of
the RX pipeline.

.. autoclass:: souk_mkid_readout.blocks.input.Input
  :no-show-inheritance:
  :members:

PFB Control
+++++++++++

The ``Pfb`` interface controls the RX channelizers.

.. autoclass:: souk_mkid_readout.blocks.pfb.Pfb
  :no-show-inheritance:
  :members:

PFB TVG Control
+++++++++++++++

The ``PfbTvg`` interface allows test vectors to be injected into the RX
pipeline, after the PFB block.

.. autoclass:: souk_mkid_readout.blocks.pfbtvg.PfbTvg
  :no-show-inheritance:
  :members:

Auto-correlation Control
++++++++++++++++++++++++

The ``Autocorr`` interface controls an spectral-power integrator which
can be used to accumulate spectra after the RX PFB.

.. autoclass:: souk_mkid_readout.blocks.autocorr.AutoCorr
  :no-show-inheritance:
  :members:

Channel Sub-Select Control
++++++++++++++++++++++++++

The ``ChanReorderMultiSample`` control interface allows a subset of PFB channels
to be selected for further processing.
A similar interface class -- ``ChanReorderMultiSampleIn`` -- is used to control
the assignment of LO tones to PSB channels.

.. autoclass:: souk_mkid_readout.blocks.chanreorder.ChanReorderMultiSample
  :no-show-inheritance:
  :members:

.. autoclass:: souk_mkid_readout.blocks.chanreorder.ChanReorderMultiSampleIn
  :no-show-inheritance:
  :members:

Zoom FFT Control
++++++++++++++++

The ``ZoomPfb`` control interface controls a second stage PFB which operates on
a single RX PFB channel.

.. autoclass:: souk_mkid_readout.blocks.zoom_pfb.ZoomPfb
  :no-show-inheritance:
  :members:

Zoom FFT Accumulator Control
++++++++++++++++++++++++++++

The ``Accumulator`` control interface controls a accumulation of PFB spectral power.

.. autoclass:: souk_mkid_readout.blocks.accumulator.Accumulator
  :no-show-inheritance:
  :members:


Mixer Control
+++++++++++++

The ``Mixer`` control interface allows configuration of multi-channel CORDIC-based
LO generators.

.. autoclass:: souk_mkid_readout.blocks.mixer.Mixer
  :no-show-inheritance:
  :members:

Windowed Accumulator Control
++++++++++++++++++++++++++++

The ``WindowedAccumulator`` control interface allows configuration of an accumulator
which provides runtime-programmable windowing of input data.

.. autoclass:: souk_mkid_readout.blocks.accumulator.WindowedAccumulator
  :no-show-inheritance:
  :members:

PSB Scaling
+++++++++++

The ``PsbScale`` control interface allows configuration of PSB voltage scaling.

.. autoclass:: souk_mkid_readout.blocks.psbscale.PsbScale
  :no-show-inheritance:
  :members:

Generator
+++++++++

The ``Generator`` control interface controls CORDIC- or LUT-based tone generators.

.. autoclass:: souk_mkid_readout.blocks.generator.Generator
  :no-show-inheritance:
  :members:

Output
++++++

The ``Output`` control interface allows configuration of TX output multiplexors.

.. autoclass:: souk_mkid_readout.blocks.output.Output
  :no-show-inheritance:
  :members:


Output Delay
++++++++++++

Programmable output delay is controlled via a ``Delay`` control interface.

.. autoclass:: souk_mkid_readout.blocks.delay.Delay
  :no-show-inheritance:
  :members:
