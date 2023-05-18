#!/usr/bin/env python

import sys
import argparse
import numpy as np
import matplotlib.pyplot as plt
import souk_mkid_readout

HOST = 'zcu111'
CONFIGFILE = '/home/jackh/src/souk-firmware/software/control_sw/config/souk-single-pipeline.yaml'

def set_output_freq(r, f, lut=False):
    if lut:
        r.output.use_lut()
        r.gen_lut.set_output_freq(0, f, r.adc_clk_hz, 0.25)
    else:
        r.output.use_cordic()
        for i in range(4):
            r.gen_cordic.set_output_freq(i, f, r.adc_clk_hz)
        r.gen_cordic.reset_phase()

def scan_bin(r, n, p=50, b=4):
    """
    params:
      r: SoukMkidReadout Instance
      n: PFB bin to center on
      p: Number of frequency points to plot
      b: Number of PFB bins to sweep over
    """
    df = r.adc_clk_hz / 2048 / 2
    print(f'Using ADC clk {r.adc_clk_hz} Hz')
    print(f'Bin separation is {df} Hz')
    freqs = np.linspace((n-b//2)*df, (n+b//2)*df, p)
    d = np.zeros([b, p])
    for fn, freq in enumerate(freqs):
        print(f"Sweeping tone {fn+1} of {p} ({freq:.3f} Hz)", end=' ')
        set_output_freq(r, freq)
        x = np.fft.fftshift(r.autocorr.get_new_spectra(0, True)[0])
        binstart = 2048 + n - b//2
        binstop  = 2048 + n - b//2 + b
        print(f"(Maximum power found in bin {x.argmax()}, getting data from bins {binstart}-{binstop})")
        for i in range(b):
            d[i,fn] = x[2048 + n - b//2 + i]
    return d

def plot_scan(r, n, p, b, normalize=True):
    d = scan_bin(r, n, p, b)
    if normalize:
        d /= d.max()
    for i in range(b):
        plt.plot(10*np.log10(d[i]), label=i)
    plt.legend()
    plt.show()

def main(host, configfile):
    r = souk_mkid_readout.SoukMkidReadout(host, configfile=configfile)
    r.program()
    r.initialize()
    r.output.use_cordic()
    r.input.enable_loopback()
    r.pfb.set_fftshift(0xffffffff)
    r.autocorr.set_acc_len(1000)
    r.sync.arm_sync()
    r.sync.sw_sync()
    overflow_before = r.pfb.get_overflow_count()
    plot_scan(r, 100, 200, 6)
    overflow_after = r.pfb.get_overflow_count()
    overflow_count = overflow_after - overflow_before
    print(f"Total FFT overflows during scan: {overflow_count}")

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

    args = parser.parse_args()
    main(args.host, args.configfile)
