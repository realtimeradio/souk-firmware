import numpy as np
import souk_mkid_readout

HOST = 'rfsoc4x2'
FPGFILE = '../../../firmware/src/souk_single_pipeline_4x2/outputs/souk_single_pipeline_4x2.fpg'
NCHANS = 10
ACCLEN = 1024
VERBOSE = True

r = souk_mkid_readout.SoukMkidReadout(HOST, fpgfile=FPGFILE)
r.program()

r.initialize()
print('Enabling TVG')
r.pfbtvg.tvg_enable()
print('Writing TVG ramp')
r.pfbtvg.write_freq_ramp()
print('Configuring accumulator')
acc = r.accumulators[0]
acc.set_acc_len(ACCLEN)
print('Arming and waiting for sync')
r.sync.arm_sync()
r.sync.wait_for_sync()

print('Setting channel map')
chanmap = np.ones(r.chanselect.n_chans_out, dtype=int)*-1
sel = np.random.randint(0, r.chanselect.n_chans_in, NCHANS)
# BEWARE: Channel map liable to create conflicts without sorting
chanmap[0:NCHANS] = sorted(sel)
expected_output = np.round(chanmap**2 / 2.**16) # Firmware drops 16 bits
r.chanselect.set_channel_outmap(chanmap)
r.mixer.enable_power_mode()
print('Getting spectra')
acc.get_new_spectra() # Flush a spectra
x = acc.get_new_spectra()
assert x.imag.sum() == 0
x = x.real / ACCLEN

print('Checking channel order in accumulation')
passed = True
for i in range(acc.n_chans):
    if VERBOSE:
        print(i, chanmap[i], expected_output[i], x[i])
    if chanmap[i] != -1:
        if expected_output[i] != x[i]:
            passed = False

print('Checking channel order in readback')
chanmap_readback = r.chanselect.get_channel_outmap()
for i in range(r.chanselect.n_chans_out):
    if VERBOSE:
        print(i, chanmap[i], chanmap_readback[i])
    if chanmap[i] != chanmap_readback[i]:
        passed = False

if passed:
    print('#################')
    print('# Test passed   #')
    print('#################')
else:
    print('#################')
    print('# Test Failed   #')
    print('#################')
