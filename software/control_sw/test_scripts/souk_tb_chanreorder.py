#!/usr/bin/env python

import argparse
import numpy as np
import souk_mkid_readout

HOST = 'rfsoc4x2'
FPGFILE = '../../../firmware/src/souk_single_pipeline_4x2/outputs/souk_single_pipeline_4x2.fpg'
NCHAN = 10
ACCLEN = 1024

def main(args):
    r = souk_mkid_readout.SoukMkidReadout(args.host, fpgfile=args.fpgfile)
    r.program()
    
    r.initialize()
    print('Enabling TVG')
    r.pfbtvg.tvg_enable()
    print('Writing TVG ramp')
    r.pfbtvg.write_freq_ramp()
    print('Configuring accumulator')
    acc = r.accumulators[0]
    acc.set_acc_len(args.acclen)
    print('Arming and waiting for sync')
    r.sync.arm_sync(wait=False)
    r.sync.sw_sync()
    
    print('Setting channel map')
    chanmap = np.ones(r.chanselect.n_chans_out, dtype=int)*-1
    if args.force_chans is not None:
        sel = [int(i) for i in args.force_chans.split(',')]
        args.nchan = len(sel) # override
    else:
        rng = np.random.default_rng(seed=args.seed)
        sel = rng.integers(0, r.chanselect.n_chans_in, args.nchan)
    chanmap[0:args.nchan] = sel
    expected_output = np.round((chanmap*4/2**17)**2 * 2**18) # Firmware drops 16 bits
    r.chanselect.set_channel_outmap(chanmap, descramble_input=False) # TVG isn't scrambled
    r.mixer.enable_power_mode()
    print('Getting spectra')
    acc.get_new_spectra() # Flush a spectra
    x = acc.get_new_spectra()
    assert x.imag.sum() == 0
    x = x.real / args.acclen
    
    print('Checking channel order in accumulation')
    passed = True
    for i in range(acc.n_chans):
        if i < args.nchan_print:
            print(i, chanmap[i], 'expected:', expected_output[i], 'read:', x[i])
        if chanmap[i] != -1:
            if expected_output[i] != x[i]:
                passed = False
    
    print('Checking channel order in readback')
    chanmap_readback = r.chanselect.get_channel_outmap(descramble_input=False)
    for i in range(r.chanselect.n_chans_out):
        if i < args.nchan_print:
            print(i, 'expected:', chanmap[i], 'read:', chanmap_readback[i])
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

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description = "Run RX path TVG test",
        formatter_class = argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("host", type=str, default=HOST,
        help = "Hostname / IP of board on which to run tests",
    )

    parser.add_argument("fpgfile", type=str, default=FPGFILE,
        help = "Configuration .fpg file to program",
    )

    parser.add_argument("--nchan", type=int, default=NCHAN,
        help = "Number of tone paths to use",
    )

    parser.add_argument("--acclen", type=int, default=ACCLEN,
        help = "Number of spectra to accumulate",
    )

    parser.add_argument("--nchan_print", type=int, default=0,
        help = "Number of channels for which to print results",
    )

    parser.add_argument("--seed", type=int, default=0xbeefbeef,
        help = "Seed for random channel selection",
    )

    parser.add_argument("--force_chans", type=str, default=None,
        help = "Optionally provide a comma-separated list of channels to select. Eg. '1,2,3'",
    )

    args = parser.parse_args()
    main(args)

