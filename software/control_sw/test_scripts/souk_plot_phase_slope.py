#!/usr/bin/env python

import sys
import time
import argparse
import numpy as np
import matplotlib.pyplot as plt
import souk_mkid_readout

HOST = 'krc4700.work.pvt'
CONFIGFILE = '/home/jackh/src/souk-firmware/software/control_sw/config/souk-dual-pipeline.yaml'
SYNC_DELAY = 5709

def set_tones(r, offset):
    tones_hz = np.fft.fftfreq(r.fw_params['n_chan_rx'], 1./r.adc_clk_hz) + r.adc_clk_hz/2.
    bin_width = tones_hz[1] - tones_hz[0]
    tones_hz += offset * bin_width
    r.set_multi_tone_vacc(tones_hz[0:r.chanselect.n_chans_out-100])
    r.psb.set_fftshift(0b110110110111111)
    r.psb.reset_overflow_count()
    time.sleep(0.5)
    print('%s status:' % r.psb.name)
    r.psb.print_status()
    
def main(host, configfile, pipeline_id, offset, sync_delay):
    r = souk_mkid_readout.SoukMkidReadout(host, configfile=configfile, pipeline_id=pipeline_id)
    r.program()
    r.initialize()
    r.output.use_psb()
    r.input.enable_loopback()
    r.pfb.set_fftshift(0b110110110110110)
    r.pfb.reset_overflow_count()
    time.sleep(0.5)
    print('%s status:' % r.pfb.name)
    r.pfb.print_status()
    acc = r.accumulators[0]
    acc.set_acc_len(1000)
    set_tones(r, offset)
    print('Setting sync delay to %s' % sync_delay)
    r.sync.set_delay(sync_delay)
    r.sync.arm_sync(wait=False)
    r.sync.sw_sync()
    acc._wait_for_acc()
    acc.plot_spectra(power=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description = "A script to sweep a CW tone over a PFB bin and print response",
        formatter_class = argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("host", type=str, default=HOST,
        help = "Hostname / IP address of FPGA board to test",
    )

    parser.add_argument("configfile", type=str, default=CONFIGFILE,
        help = "Configuration YAML file with which to test",
    )

    parser.add_argument("-o", "--offset", type=float, default="0.0",
        help = "Offset of tone in each bin, in units of bin width.",
    )

    parser.add_argument("-d", "--delay", type=int, default=SYNC_DELAY,
        help = "Sync delay to load",
    )

    parser.add_argument("-p", "--pipeline_id", type=int, default=0,
        help = "pipeline ID",
    )

    args = parser.parse_args()
    assert args.pipeline_id in [0,1]

    main(args.host, args.configfile, args.pipeline_id, args.offset, args.delay)
