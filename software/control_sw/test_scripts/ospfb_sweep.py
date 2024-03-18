#!/usr/bin/env python

import sys
import argparse
import numpy as np
import matplotlib.pyplot as plt
import souk_mkid_readout

HOST = 'zcu111'
CONFIGFILE = '/home/jackh/src/souk-firmware/software/control_sw/config/souk-single-pipeline.yaml'

def set_output_freq(r, f, output='psb'):
    if output == 'psb':
        r.output.use_psb()
        r.set_tone(0, f + r.adc_clk_hz / 2.) # for consistency of setpoint relative to DAC mixer
    elif output == 'lut':
        r.output.use_lut()
        r.gen_lut.set_output_freq(0, f, r.adc_clk_hz, 0.25)
    elif output == 'cordic':
        r.output.use_cordic()
        for i in range(r.gen_cordic.n_generators):
            r.gen_cordic.set_output_freq(i, f, r.adc_clk_hz)
        r.gen_cordic.reset_phase()
    else:
        raise ValueError(f"I don't understand output type {output}")

def scan_bin(r, n, p=50, b=4, n_chans=4096, output='cordic'):
    """
    params:
      r: SoukMkidReadout Instance
      n: PFB bin to center on
      p: Number of frequency points to plot
      b: Number of PFB bins to sweep over
      n_chans: Number of channels in oversampled PFB
      output: 'cordic', 'lut', or 'psb'. Determines how tone is generated
    """
    df = r.adc_clk_hz / n_chans
    print(f'Using ADC clk {r.adc_clk_hz} Hz')
    print(f'Bin separation is {df} Hz')
    freqs = np.linspace((n-b//2)*df, (n+b//2)*df, p)
    d = np.zeros([b, p])
    for fn, freq in enumerate(freqs):
        print(f"Sweeping tone {fn+1} of {p} ({freq:.3f} Hz)", end=' ')
        set_output_freq(r, freq, output=output)
        x = np.fft.fftshift(r.autocorr.get_new_spectra(0, True)[0])
        binstart = n_chans // 2 + n - b//2
        binstop  = n_chans // 2 + n - b//2 + b
        print(f"(Maximum power found in bin {x.argmax()}, getting data from bins {binstart}-{binstop})")
        for i in range(b):
            d[i,fn] = x[n_chans // 2 + n - b//2 + i]
    return d

def plot_scan(r, n, p, b, normalize=True, n_chans=4096, output='cordic'):
    d = scan_bin(r, n, p, b, n_chans=n_chans, output=output)
    if normalize:
        d /= d.max()
    for i in range(b):
        plt.plot(10*np.log10(d[i]), label=i)
    plt.legend()
    plt.show()

def main(host, configfile, output):
    r = souk_mkid_readout.SoukMkidReadout(host, configfile=configfile)
    r.program()
    r.initialize()
    n_chans = r.autocorr.n_chans
    r.input.enable_loopback()
    r.pfb.set_fftshift(0xffffffff)
    r.autocorr.set_acc_len(1000)
    r.sync.arm_sync()
    r.sync.sw_sync()
    overflow_before = r.pfb.get_overflow_count()
    plot_scan(r, 100, 200, 6, n_chans=n_chans, output=output)
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

    parser.add_argument("-o", "--output", type=str, default="cordic",
        help = "Type of generator to use. 'cordic', 'lut', or 'psb'"
    )

    args = parser.parse_args()

    if args.output not in ["cordic", "lut", "psb"]:
        raise ValueError("--output must be cordic, lut, or psb")

    main(args.host, args.configfile, args.output)
