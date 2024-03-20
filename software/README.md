# Installing Control Software

## Ubuntu 18.04 LTS / Python 3.6.9

```
# Make sure you have the casperfpga git submodule checked out
git submodule update --init casperfpga

# Get non-standard header dependencies
sudo apt install libjpeg-dev

# Install the python wheel package, needed to install other packages
pip install wheel

# install casperfpga
cd casperfpga
pip install -r requirements.txt
pip install .
cd ..

# install the SOUK control library
cd control_sw
pip install -r requirements.txt
pip install .
```

You should now be able to successfully import the control library in a python shell.

I.e.

```
python
>>> import souk_mkid_readout
```

# Zynq Local Software

Current version of tcpborphserver is available in `./zynq` and should be installed on the RFSoC board per the `readme` in that directory
