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
    f.program() # Load whatever firmware is in flash
    # Wait 30 seconds for the board to reboot...
    # Initialize firmware blocks, including ADC link training
    f.initialize(read_only=False)

  # Blocks are available as items in the SoukMkidReadout `blocks`
  # dictionary, or can be accessed directly as attributes
  # of the SoukMkidReadout.

  # Print available block names
  print(sorted(f.blocks.keys()))
  # Returns:
  # ['adc', 'autocorr', 'corr', 'delay', 'eq', 'eq_tvg', 'eth',
  # 'fpga', 'input', 'noise', 'packetizer', 'pfb', 'reorder', 'sync']

  # Grab some ADC data from the ADC
  adc_data = f.input.get_adc_snapshot()

Details of the methods provided by individual blocks are given in the next
section.


Top-Level Control
+++++++++++++++++

The Top-level ``SoukMkidReadout`` instance can be used to perform high-level
control of the firmware, such as programming and de-programming FPGA boards.
It can also be used to apply configurations which affect multiple firmware
subsystems, such as configuring channel selection and packet destination.

Finally, a ``SoukMkidReadout`` instance can be used to initialize, or get status
from, all underlying firmware modules.

.. autoclass:: souk_mkid_readout.SoukMkidReadout
  :no-show-inheritance:
  :members:

.. _control-fpga:

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

Input Control
+++++++++++++

.. autoclass:: souk_mkid_readout.blocks.input.Input
  :no-show-inheritance:
  :members:

PFB Control
+++++++++++

.. autoclass:: souk_mkid_readout.blocks.pfb.Pfb
  :no-show-inheritance:
  :members:

PFB TVG Control
+++++++++++++++

.. autoclass:: souk_mkid_readout.blocks.pfbtvg.PfbTvg
  :no-show-inheritance:
  :members:

Auto-correlation Control
++++++++++++++++++++++++

.. autoclass:: souk_mkid_readout.blocks.autocorr.AutoCorr
  :no-show-inheritance:
  :members:
