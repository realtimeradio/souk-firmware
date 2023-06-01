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
NSPEC = 32
TEST_BIN=10

PI = np.pi

def get_coeffs(ntaps, nfft, window_func=np.hanning):
    trange = np.linspace(-ntaps/2., ntaps/2., ntaps*nfft)
    sinc = np.sinc(trange)
    window = window_func(ntaps*nfft)
    coeffs = sinc * window
    return coeffs

t = np.arange(NSPEC*NTAPS)
f1 = 0.4
input_spec  = np.zeros([NSPEC*NTAPS, NFFT], dtype=complex)
#input_spec[:,1] = np.exp(2*np.pi * 1j * t0/(NTAPS))
input_spec[:,TEST_BIN] = np.exp(2*np.pi * 1j * f1*t)

tseries = fft(input_spec, axis=1)
# Not flipping here will flip the + and - frequencies
#tseries = tseries[:,::-1] # Flip here instead of using IFFT
tseries = tseries.flatten()

tout = np.zeros([NSPEC*NTAPS//2, NFFT], dtype=complex)

coeffs = get_coeffs(NTAPS, NFFT)
for i in range(NSPEC*NTAPS//2):
    v = tseries[i*NFFT:i*NFFT + NTAPS*NFFT] * coeffs
    for t in range(NTAPS):
        tout[i] += v[t*NFFT:(t+1)*NFFT]

tout = tout[:,::-1] # Reverse blocks of NFFT samples (flips frequency direction)
tout = tout.flatten()

output_spec_filt = np.abs(fftshift(fft(tout*get_coeffs(1,NSPEC*NTAPS*NFFT//2))))**2
output_spec_nofilt = np.abs(fftshift(fft(tseries[0:NSPEC*NTAPS*NFFT//2]*get_coeffs(1,NSPEC*NTAPS*NFFT//2))))**2
output_spec_filt /= np.max(output_spec_filt)
output_spec_nofilt /= np.max(output_spec_nofilt)
#plt.figure()
#plt.plot(coeffs)
#plt.figure()
plt.subplot(4,1,1)
plt.plot(tseries.real)
plt.plot(tseries.imag)
plt.xlim(0,3*NFFT)
plt.subplot(4,1,2)
plt.plot(tout.real)
plt.plot(tout.imag)
plt.xlim(0,3*NFFT)
plt.subplot(4,1,3)
plt.plot(10*np.log10(output_spec_nofilt)[::-1], 'r')
plt.plot(10*np.log10(output_spec_filt), 'b')
plt.subplot(4,1,4)
plt.plot(10*np.log10(output_spec_filt), 'b')
plt.xlim((NFFT*NTAPS*NSPEC//4 + (TEST_BIN-3)*NSPEC//2*NTAPS, NFFT*NTAPS*NSPEC//4 + (TEST_BIN+3)*NSPEC//2*NTAPS))
plt.ylim(-100,10)
plt.show()

