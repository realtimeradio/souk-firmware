#!/usr/bin/env python

"""
Experimenting with Polyphase Synthesizer Implementation.

See Harris++ 2013; "Digital Receivers and Transmitters Using
Polyphase Filter Banks for Wireless Communications"
"""

import numpy as np
from matplotlib import pyplot as plt
from numpy.fft import fft, ifft, fftshift

NFFT = 2**10
NTAPS = 8
OS_FACTOR = 2
PLOT_RANGE = NFFT
NFREQ_TRIAL = 32*NFFT*OS_FACTOR

PI = np.pi

def get_coeffs(ntaps, nfft, window_func=np.hanning):
    trange = np.linspace(-ntaps/2., ntaps/2., ntaps*nfft)
    sinc = np.sinc(trange)
    window = window_func(ntaps*nfft)
    coeffs = sinc * window
    return coeffs

t = np.arange(NTAPS*NTAPS)*0.2
input_spec  = np.zeros([NTAPS*NTAPS, NFFT], dtype=complex)
input_spec[:,1] = np.exp(2*np.pi * 1j * t/(NTAPS))
input_spec[:,NFFT//4] = np.exp(2*np.pi * 1j * t/(NTAPS))

tseries = fft(input_spec, axis=1)
tseries = tseries[:,::-1] # Flip here instead of using IFFT
tseries = tseries.flatten()

tout = np.zeros(NTAPS * NFFT, dtype=complex)

coeffs = get_coeffs(NTAPS, NFFT)
for i in range(NTAPS):
    v = tseries[i*NFFT:i*NFFT + NTAPS*NFFT] * coeffs
    for t in range(NTAPS):
        tout[i*NFFT:(i+1)*NFFT] += v[t*NFFT:(t+1)*NFFT][::-1]

output_spec_filt = np.abs(fftshift(fft(tout*get_coeffs(1,NTAPS*NFFT))))**2
output_spec_nofilt = np.abs(fftshift(fft(tseries[0:NTAPS*NFFT]*get_coeffs(1,NTAPS*NFFT))))**2
#plt.figure()
#plt.plot(coeffs)
#plt.figure()
plt.subplot(3,1,1)
plt.plot(tseries.real)
plt.plot(tseries.imag)
plt.xlim(0,3*NFFT)
plt.subplot(3,1,2)
plt.plot(tout.real)
plt.plot(tout.imag)
plt.xlim(0,3*NFFT)
plt.subplot(3,1,3)
plt.plot(10*np.log10(output_spec_filt), 'b')
plt.plot(10*np.log10(output_spec_nofilt)[::-1], 'r')
plt.show()

