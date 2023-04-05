#!/usr/bin/env python

import numpy as np
from matplotlib import pyplot as plt

NFFT = 4
OS_FACTOR = 2
PLOT_RANGE = NFFT
NFREQ_TRIAL = 32*NFFT*OS_FACTOR

PI = np.pi

def plot_pfb(ntaps, window_func, offset=0):
    
    trange = np.linspace(-ntaps/2., ntaps/2., ntaps*NFFT)
    sinc = np.sinc(trange)
    window = window_func(ntaps*NFFT)
    coeffs = sinc * window

    sweep_freq = np.linspace(-NFFT//2, NFFT//2, NFREQ_TRIAL) # fraction of pfb bin
    resp_plot = np.zeros([NFFT*OS_FACTOR, NFREQ_TRIAL])
    for fn, f in enumerate(sweep_freq):
        d_r = np.cos(np.linspace(0, 2*PI*f*ntaps, NFFT*ntaps))
        d_i = np.sin(np.linspace(0, 2*PI*f*ntaps, NFFT*ntaps))
        d = d_r + 1j*d_i
        windowed_data = d*coeffs
        windowed_sum = np.zeros(NFFT*OS_FACTOR, dtype=complex)
        for t in range(ntaps//OS_FACTOR):
            windowed_sum += windowed_data[t*OS_FACTOR*NFFT:(t+1)*OS_FACTOR*NFFT]
        resp = np.abs(np.fft.fftshift(np.fft.fft(windowed_sum)))**2
        for b in range(NFFT*OS_FACTOR):
            resp_plot[b,fn] = resp[b]
    resp_db = 10*np.log10(resp_plot)
    resp_db -= np.max(resp_db)
    #for i in range(PLOT_RANGE):
    #    resp_db[i] -= np.max(resp_db[i])
    
    plt.subplot(1,2,1)
    for b in range(NFFT*OS_FACTOR):
        plt.plot(sweep_freq, resp_db[b], label='bin %d, %d taps' % (b,ntaps))
    plt.xlim(-PLOT_RANGE//2, PLOT_RANGE//2)
    plt.ylim(-120, 3)
    
    plt.subplot(1,2,2)
    for b in range(NFFT*OS_FACTOR):
        plt.plot(sweep_freq, resp_db[b], label='bin %d, %d taps' % (b,ntaps))
    plt.xlim(0,1)
    plt.ylim(-7, 3)

for wf in [np.hanning]:
    plt.figure()
    for taps in [8]:#np.arange(4,16+4,4):
        plot_pfb(taps, wf)
    
    plt.subplot(1,2,1)
    plt.legend()
    plt.subplot(1,2,2)
    plt.legend()
plt.show()

