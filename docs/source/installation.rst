.. |repopath| replace:: https://github.com/realtimeradio/souk-firmware

Installation
============

The SOUK MKID Readout pipeline firmware and software is available at |repopath|.
Follow the instructions here to download and install the pipeline.

Specify the build directory by defining the ``BUILDDIR`` environment variable, eg:

.. code-block::

  export BUILDDIR=~/src/
  mkdir -p $BUILDDIR

Get the Source Code
-------------------

Clone the repository and its dependencies with:

.. code-block::

  # Clone the main repository
  cd $BUILDDIR
  git clone https://github.com/realtimeradio/souk-firmware
  # Clone relevant submodules
  cd souk-firmware
  git submodule init
  git submodule update

Install Prerequisites
---------------------

Firmware Requirements
+++++++++++++++++++++

The SOUK MKID Readout firmware can be built with the CASPER toolflow, and was
designed using the following software stack:

  - Ubuntu 18.04.0 LTS (64-bit)
  - MATLAB R2021a
  - Simulink R2021a
  - MATLAB Fixed-Point Designer Toolbox R2021a
  - Xilinx Vivado HLx 2021.2
  - Python 3.8

It is *strongly* recommended that the same software versions be used to rebuild
the design.
