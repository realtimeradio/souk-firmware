F-Engine System Overview
========================

Overview
--------

TODO

Initialization
++++++++++++++

The functionality of individual blocks is described below.
However, in order to simply get the firmware into a basic working state the following process should be followed:

  1. Program the FPGA
  2. Initialize all blocks in the system
  3. Trigger master reset and timing synchronization event.

In a multi-board system, the process of synchronizing a board can be relatively involved.
For testing purposes, using single board, a simple software reset can be used in place of a hardware timing signal to perform an artificial synchronization.
A software reset is automatically issued as part of system initialization.

The following commands bring the F-engine firmware into a functional state, suitable for testing.
See :numref:`control-interface` for a full software API description

.. code-block:: python

  # Import the SNAP2 F-Engine library
  from souk_mkid_readout import SoukFirmwareReadout

  # Instantiate an SoukFirmwareReadout instance, connecting to a board with
  # hostname 'my_zcu111'
  f = SoukFirmwareReadout('my_zcu111', config_file='my_config_file.yaml')

  # Program a board
  f.program() # Load whatever firmware was listed in the config file

  # Initialize all the firmware blocks
  # and issue a global software reset
  f.initialize(read_only=False)


Block Descriptions
++++++++++++++++++

Each block in the firmware design can be controlled using an API described in :numref:`control-interface`.
