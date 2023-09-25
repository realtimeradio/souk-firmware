#!/usr/bin/env python3

import argparse
import time
import logging
import numpy as np
from matplotlib import pyplot as plt

ADC_ID = 1 # ADC with a small LO shift to maintain low-end of band
ZOOM_ACC_LEN = 128
ZOOM_FFT_SHIFT = 0b110110110110
FFT_SHIFT = 0xefef
DEFAULT_CONFIGFILE = '/home/leechj/souk-firmware/software/control_sw/config/souk-single-pipeline-rx.yaml'
DEFAULT_HOST = '10.11.11.11'
DEFAULT_COARSE_ACC_LEN = 2**15
DEFAULT_FINE_ACC_LEN = 128

def main(args):
    from souk_mkid_readout import SoukMkidReadout
    r = SoukMkidReadout(args.host, configfile=args.configfile)

    if args.initialize:
        r.program()
        r.initialize()
        r.pfb.set_fftshift(FFT_SHIFT)
        r.zoomfft.set_fftshift(ZOOM_FFT_SHIFT)

    ct = args.coarse_acc_len * r.autocorr.n_chans / 2. / r.adc_clk_hz # divide-by-2 because oversampled
    ft = args.fine_acc_len * r.zoomacc.n_chans * r.autocorr.n_chans / 2. / r.adc_clk_hz
    print("Accumulating %d coarse spectra (%.2f s)" % (args.coarse_acc_len, ct))
    print("Accumulating %d fine spectra (%.2f s)" % (args.fine_acc_len, ft))
    r.autocorr.set_acc_len(args.coarse_acc_len)
    r.zoomacc.set_acc_len(args.fine_acc_len)
    r.sync.arm_sync(wait=False)
    r.sync.sw_sync()

    r.fpga.write_int('adc_chan_sel', ADC_ID)

    r.zoomacc.set_acc_len(ZOOM_ACC_LEN)
    freqs = r.autocorr.get_freqs(r.adc_clk_hz, r.rfdc.get_lo(r.adc_clk_hz, 0, ADC_ID))

    if args.zoom_chan is not None:
        nplot = 2
    else:
        nplot = 1

    d = r.autocorr.get_new_spectra()[0]
    d = 10*np.log10(d)
    plt.subplot(nplot, 1, 1)
    if args.plot_chan:
        plt.plot(d, '-o')
        plt.xlabel('Frequency Channel')
    else:
        plt.plot(np.fft.fftshift(freqs) / 1e6, np.fft.fftshift(d), '-o')
        plt.xlabel('Frequency [MHz]')
    plt.ylabel('Power [dBFS]')

    if args.zoom_chan is not None:
        if args.zoom_chan < 0:
            # Find highest chan
            zoom_chan = np.argmax(d)
        else:
            zoom_chan = args.zoom_chan
        coarse_center = freqs[zoom_chan]
        print("Zooming on bin %d with center frequency %d Hz" % (zoom_chan, coarse_center))
        freqs_fine = np.fft.fftfreq(r.zoomacc.n_chans, d=1./(r.adc_clk_hz/(r.autocorr.n_chans/2.))) + coarse_center
        r.zoomfft.set_channel(zoom_chan)
        r.sync.arm_sync(wait=False)
        r.sync.sw_sync()
        dfine = r.zoomacc.get_new_spectra() # Flush a spectra
        dfine = r.zoomacc.get_new_spectra()
        dfine = 10*np.log10(dfine)
        plt.subplot(nplot, 1, 2)
        plt.plot(np.fft.fftshift(freqs_fine) / 1e6, np.fft.fftshift(dfine))
        plt.xlabel('Frequency [MHz]')
        plt.ylabel('Power [dB arb ref.]')

    plt.show()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description = "Configure an RFSoC to transmit accumulations",
        formatter_class = argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--host", type=str, default=DEFAULT_HOST,
        help = "IP address of hostname of FPGA board",
    )

    parser.add_argument("--configfile", type=str, default=DEFAULT_CONFIGFILE,
        help = "Configuration file specifying firmware and clock rate",
    )

    parser.add_argument("-i", "--initialize", action="store_true",
        help = "If set, program and initialize the FPGA. This is only necesarry once after a power cycle",
    )

    parser.add_argument("-c", "--plot_chan", action="store_true",
        help = "If set, plot X-axis as channel index, not frequency",
    )

    parser.add_argument("--coarse_acc_len", type=int, default=DEFAULT_COARSE_ACC_LEN, 
        help = "Number of coarse spectra to accumulate",
    )

    parser.add_argument("--fine_acc_len", type=int, default=DEFAULT_FINE_ACC_LEN, 
        help = "Number of fine spectra to accumulate",
    )

    parser.add_argument("-z", "--zoom_chan", type=int, default=None,
        help = "If set, zoom in on this channel. Use -1 to zoom on on the coarse channel with highest power",
    )

    args = parser.parse_args()
    main(args)

