#!/usr/bin/env python

import numpy as np
from matplotlib import pyplot as plt


OS_FACTOR = 2 # only works for 2
NFFT = 1024
NFINE_SAMPLE = 1024
NTAP = 16
SAMPLE_RATE_MHZ = 1024.
TEST_TONE_MHZ = 4.1
COARSE_CHAN_PLOT = np.arange(3*OS_FACTOR,6*OS_FACTOR)

PI = np.pi

def do_window(ntaps, nfft, d, window_func=np.hanning, os_factor=1, reorder=False):
    
    trange = np.linspace(-ntaps/2., ntaps/2., ntaps*nfft)
    sinc = np.sinc(trange)
    window = window_func(ntaps*nfft)
    coeffs = sinc * window

    wd = d * coeffs # windowed data
    wd = wd.reshape([ntaps, nfft])
    assert os_factor == 2, 'the below only works for 2x oversampling'
    wd_even = wd[0::2, :].sum(axis=0)
    wd_odd  = wd[1::2, :].sum(axis=0)
    if reorder:
        wd_full = np.concatenate([wd_even, wd_odd])
    else:
        wd_full = np.concatenate([wd_odd, wd_even])
    return wd_full

def do_ospfb(ntaps, nfft, d, window_func=np.hanning, os_factor=1):
    wd = do_window(ntaps, nfft, d, window_func, os_factor)
    spec = np.fft.fft(wd)
    return spec
    #sum_even = np.zeros(nfft, dtype=complex)
    #sum_odd  = np.zeros(nfft, dtype=complex)
    #sum_full = np.zeros(nfft * 2, dtype=complex)
    #for t in range(ntaps//2):
    #    sum_even += wd[2*t*nfft:(2*t+1)*nfft]
    #    sum_odd  += wd[(2*t+1)*nfft:(2*t+1+1)*nfft]
    #sum_full[0:nfft] = sum_even[:]
    #sum_full[nfft:] = sum_odd[:]
    #spec = np.fft.fft(sum_full)
    #return spec

trange = np.arange(NFFT*(NFINE_SAMPLE + NTAP)) * 1./(SAMPLE_RATE_MHZ * 1e6)
cw_in = np.exp(1j * 2 * PI * (TEST_TONE_MHZ * 1e6) * trange)
coarse_chan_d = np.zeros([OS_FACTOR*NFFT, NFINE_SAMPLE], dtype=complex)
#plt.figure()
for i in range(NFINE_SAMPLE):
    d = cw_in[i*NFFT:(i + NTAP) * NFFT]
    wd = do_window(NTAP, NFFT, d, os_factor=OS_FACTOR, reorder=(i%2==0))
    out = np.fft.fft(wd)
    coarse_chan_d[:,i] = out
    #if i<5:
    #    plt.plot(np.angle(wd), label=i)
#plt.legend()

fine_chan = np.fft.fft(coarse_chan_d, axis=1)

nchan_plot = len(COARSE_CHAN_PLOT)
print(f'Test tone: {TEST_TONE_MHZ:.2f} MHz (Sample rate {SAMPLE_RATE_MHZ} MHz, chan spacing {SAMPLE_RATE_MHZ/NFFT/2} MHz')
plt.figure()
for cn, c in enumerate(COARSE_CHAN_PLOT):
    #plt.subplot(2, 1, 1)
    spec = np.abs(fine_chan[c])**2
    bin_max = spec.argmax()
    peak = 10*np.log10(spec.max())
    print(f'Coarse chan {c}: Max power in bin {bin_max} ({peak:.2f} dB)')
    plt.semilogy(np.fft.fftshift(spec), label=f'Coarse chan {c}')
    plt.legend()
    #plt.subplot(2,1,2)
    #plt.plot(np.angle(coarse_chan_d[c]), label=f'Coarse chan {c}')
    #plt.legend()

plt.show()

