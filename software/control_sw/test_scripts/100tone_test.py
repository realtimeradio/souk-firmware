import os
import time
from numpy import *; from matplotlib.pyplot import *; ion()

import souk_mkid_readout

s=souk_mkid_readout.SoukMkidReadout('rfsoc4x2',configfile='/home/jackh/src/souk-firmware/software/control_sw/config/souk-single-pipeline-4x2.yaml')

if not s.fpga.is_programmed():
    s.program()
    s.initialize()
s.fpga.print_status()

DAC_SAMPLE_RATE = 4915.2e6
DAC_INTERPOLATION= 2
LUT_FREQUENCY_RESOLUTION = (DAC_SAMPLE_RATE / DAC_INTERPOLATION) /  s.gen_lut.n_samples

target_frequency = 200e6
actual_frequency =  round(target_frequency / LUT_FREQUENCY_RESOLUTION) * LUT_FREQUENCY_RESOLUTION

#MIXFREQ=0 #version <= 4.1.1.2
MIXFREQ = DAC_SAMPLE_RATE/DAC_INTERPOLATION/2 #version > 5.0.0.0

def setfreqlut(r,target_frequency):
    print('set')
    r.output.use_lut()
    actual_frequency=round((target_frequency - MIXFREQ) / LUT_FREQUENCY_RESOLUTION) * LUT_FREQUENCY_RESOLUTION
    r.gen_lut.set_output_freq(0,
                               actual_frequency,
                               sample_rate_mhz=s.adc_clk_mhz,
                               amplitude=1)
    return actual_frequency+MIXFREQ

def setfreqcordic(r,freq_hz,cordic_id=-1):
    print('set')
    r.output.use_cordic()
    r.gen_cordic.set_output_freq(cordic_id,
                                  (freq_hz-MIXFREQ),
                                  sample_rate_mhz=s.adc_clk_mhz)
def setfreqpsb(r,freq_hz,phase=0):
    print(f'Setting freq {freq_hz} Hz; phase {phase} rads')
    freq_hz=np.atleast_1d(freq_hz)
    phase=np.atleast_1d(phase)
    n_tones=len(freq_hz)
    
    r.output.use_psb()
    
    r.reset_psb_outputs()
    
    #for i,(f,p) in enumerate(zip(freq_hz,phase)):
    #    print(f'writing freq {f} Hz; phase {p} rads')
    #    r.set_tone(i, f, p)
    r.set_multi_tone(freq_hz, phase)
    shift_stages = int(np.ceil(np.log2(n_tones)))
    shift_schedule = 2**(shift_stages) - 1
    for synth in [r.psb, r.psboffset]:
        synth.set_fftshift(shift_schedule)



gens   = (setfreqlut,setfreqcordic,setfreqpsb)
gnames = ('LUT','CORDIC','PSB')
gcols  = ('b','g','r')

#test single tone on all generators:
cf = 1e9 - 100000

#look at same tone in PSB with 99 other other tones placed elsewhere
freqs     = linspace(690e6,990e6,100)+random.uniform(0,300e6/10/100,100)
freqs[0]  = cf
phases    = random.uniform(0,2*pi,100)
phases[0] = 0

freqs = [
9.99900000e+08,6.93058287e+08,6.96112082e+08,6.99273884e+08,
7.02237639e+08,7.05192786e+08,7.08221145e+08,7.11441328e+08,
7.14243050e+08,7.17294751e+08,7.20519189e+08,7.23399324e+08,
7.26631520e+08,7.29669269e+08,7.32530898e+08,7.35485911e+08,
7.38545389e+08,7.41664330e+08,7.44568581e+08,7.47841474e+08,
7.50733963e+08,7.53913187e+08,7.56937931e+08,7.59879475e+08,
7.62936500e+08,7.65864218e+08,7.68830168e+08,7.72009424e+08,
7.74860311e+08,7.78089857e+08,7.81153285e+08,7.84012337e+08,
7.87089210e+08,7.90241529e+08,7.93161346e+08,7.96326346e+08,
7.99327961e+08,8.02401701e+08,8.05421450e+08,8.08302282e+08,
8.11266873e+08,8.14453245e+08,8.17384315e+08,8.20506556e+08,
8.23423951e+08,8.26406274e+08,8.29573077e+08,8.32436605e+08,
8.35466775e+08,8.38633887e+08,8.41574071e+08,8.44793320e+08,
8.47634961e+08,8.50777836e+08,8.53922116e+08,8.56939501e+08,
8.59792850e+08,8.62804954e+08,8.65957574e+08,8.68993922e+08,
8.71920083e+08,8.75128346e+08,8.78069852e+08,8.81104637e+08,
8.84029829e+08,8.87252591e+08,8.90130091e+08,8.93084905e+08,
8.96333133e+08,8.99171776e+08,9.02211086e+08,9.05265993e+08,
9.08456370e+08,9.11387661e+08,9.14335085e+08,9.17551270e+08,
9.20408560e+08,9.23414016e+08,9.26520268e+08,9.29404105e+08,
9.32524624e+08,9.35534879e+08,9.38528286e+08,9.41621806e+08,
9.44724726e+08,9.47663281e+08,9.50857660e+08,9.53682544e+08,
9.56855552e+08,9.59831966e+08,9.62912019e+08,9.65907071e+08,
9.69081714e+08,9.71846111e+08,9.74956401e+08,9.78003273e+08,
9.80931245e+08,9.84081773e+08,9.86974162e+08,9.90009778e+08,]
phases = [
0.        ,6.21165313,5.48000458,0.72956727,2.69463194,3.33455923,
2.05413642,3.27254499,5.9285811 ,2.32277006,0.47682532,4.37094234,
4.63267842,4.68078141,4.49714147,4.83534574,5.2798568 ,2.60341022,
0.91019679,2.53099361,0.5247626 ,4.50066432,4.87238543,4.25887024,
0.78675161,5.21923515,4.3071818 ,3.73431102,3.74242781,2.1496777 ,
3.21107019,2.77108889,2.41086946,1.11051664,2.07146958,3.13175374,
3.64313542,2.05649205,1.44319689,3.18617238,1.92728196,3.40503775,
4.98021048,5.2718603 ,3.51922439,4.7539988 ,4.54425737,0.70318671,
0.22458168,5.70361004,4.30830774,5.62366213,4.38938443,2.15044543,
4.1744337 ,4.40181276,5.68258112,1.16275723,4.99730536,4.93041331,
5.13148872,3.98012234,1.50533767,5.1409984 ,3.51681306,6.08106289,
3.43041858,1.41095762,1.40022115,1.36441097,3.73831878,0.58467452,
0.07152654,1.90559493,6.14832656,0.62889316,1.63535723,1.78327228,
0.43739774,4.22173019,0.9249671 ,0.03920513,1.39548066,2.26966209,
5.36888664,5.88930835,4.64816574,4.46594529,2.34733642,3.53586586,
5.60109505,5.45722142,1.57585   ,0.04527775,3.05592403,0.30028423,
3.32746693,6.2642229 ,1.86163142,3.34038676]

t0 = time.time()
setfreqpsb(s,freqs,phases)
t1 = time.time()
print(t1-t0)
s.sync.arm_sync(wait=False)
s.sync.sw_sync()
exit()

