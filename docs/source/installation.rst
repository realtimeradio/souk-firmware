.. |repopath| replace:: https://github.com/realtimeradio/souk-firmware

Installation
============

The SOUK MKID Readout pipeline firmware and software is available at |repopath|.
Follow the instructions here to download and install the pipeline.

Install Prerequisites
---------------------

Firmware Requirements
+++++++++++++++++++++

The SOUK MKID Readout firmware can be built with the CASPER toolflow, and was
designed using the following software stack:

  - Ubuntu 20.04.6 LTS (64-bit)
  - MATLAB R2021a
  - Simulink R2021a
  - MATLAB Fixed-Point Designer Toolbox R2021a
  - Xilinx Vivado HLx 2021.2
  - Python 3.8.10

It is *strongly* recommended that the same software versions be used to rebuild
the design.

Get the Source Code
-------------------

Specify the repository root directory by defining the ``REPOROOT`` environment variable, eg:

.. code-block::

  export REPOROOT=~/src/
  mkdir -p $REPOROOT

Clone the repository and its dependencies with:

.. code-block::

  # Clone the main repository
  cd $REPOROOT
  git clone https://github.com/realtimeradio/souk-firmware
  # Clone relevant submodules
  cd souk-firmware
  git submodule init
  git submodule update

Create a Local Environment Configuration
----------------------------------------

Create a local configuration file which specifies the location to which various tools have been installed.
An example configuration is given in `$REPOROOT/firmware/startsg.local`:

.. code-block::

  export XILINX_PATH=/data/Xilinx/Vivado/2021.2
  export COMPOSER_PATH=/data/Xilinx/Model_Composer/2021.2
  export MATLAB_PATH=/data/MATLAB/R2021a
  export PLATFORM=lin64
  export JASPER_BACKEND=vitis
  export CASPER_SKIP_STARTUP_LOAD_SYSTEM=yesplease
  export XILINXD_LICENSE_FILE=/home/jackh/.Xilinx/Xilinx.lic
  export XLNX_DT_REPO_PATH=/home/jackh/src/souk-firmware/firmware/lib/device-tree-xlnx
  
  # over-ride the MATLAB libexpat version with the OS's one.
  # Using LD_PRELOAD=${LD_PRELOAD}:"..." rather than just LD_PRELOAD="..."
  # ensures that we preserve any other settings already configured
  export LD_PRELOAD=${LD_PRELOAD}:"/usr/lib/x86_64-linux-gnu/libexpat.so"

When launching Simulink to modify or compile firmware, use the incantation:

.. code-block::

   cd $REPOROOT/firmware
   ./startsg <custom_startsg_local_file>
