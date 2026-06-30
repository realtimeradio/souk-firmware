#! /usr/bin/env python

import argparse
import time
import numpy as np
import matplotlib.pyplot as plt
import souk_mkid_readout
from souk_mkid_readout.helpers import cplx2uint

HOST        = "10.11.0.37"
CONFIGFILE  = "/data/souk-firmware/software/control_sw/config/souk-single-pipeline-krm.yaml"
PIPELINE_ID = 0
PROGRAM     = True

F0_HZ       = 1.200e9            # a bin centre (offset 0)
AMP         = 1.0                # tone scale
HALFSPAN_HZ = 150e3               # stay inside one ~600 kHz RX bin
N_POINTS    = 51                 # sweep points
SETTLE      = 3                  # snapshots discarded after each swap

def main(host, config):

    if PROGRAM:
        #cannot program via localmemtransport directly, set local=False
        r = souk_mkid_readout.SoukMkidReadout(host, configfile=config,
                                          pipeline_id=PIPELINE_ID, local=False)
        r.program(); r.initialize()
    
    r.pfb.set_fftshift(0b111111111111)
    r.psb.set_fftshift(0b0)
    r.psbscale.set_scale(1.0)
    
    r.output.use_psb()
    r.input.enable_loopback()
    
    mx  = r.mixer
    r.sync.sw_sync(mrst=True)
    sync_skew = mx.read_uint('pipeline_latency')
    print(f'Mixer reports RX vs TX delay {sync_skew} FPGA clocks')
    #mm  = np.frombuffer(mx.host.transport.axil_mm, dtype='<u4')
    FFT_RBW = r.adc_clk_hz * mx._upstream_oversample_factor / mx._n_upstream_chans
    
    print(f"adc_clk_hz                  = {r.adc_clk_hz/1e9:.4f} GHz")
    print(f"channel rate (FFT_RBW)      = {FFT_RBW/1e3:.1f} kHz")
    print(f"FFT frame                   = {1e6/FFT_RBW:.4f} us")
    
    
    def write_freq(lo_name, chan, buf, freq_off_hz, amp=1., slot=0):
        """update only PHASE_INC + RI_STEP (two 32-bit stores)."""
        #wa = _word_addr(lo_name, chan, buf)
        phase = freq_off_hz / FFT_RBW * 2 * np.pi
        mx.set_phase_step(chan, phase=phase, phase_offset=0.0, los=[lo_name], next_buf=buf, slot=slot)
        mx.set_amplitude_scale(chan, amp, los=[lo_name], next_buf=buf, slot=slot)
    
    
    # initialise all buffers with amplitude dependent on slot
    for i in range(mx.n_slots):
        mx.set_current_buffer(0)
        amp = AMP * (i % 2) #  Every other slot has 0 amp
        tone_to_lo = r.set_multi_tone_vacc([F0_HZ], [0.0], [amp], los=['rx', 'tx'], min_tone_separation=6, slot=i)
        mx.set_current_buffer(1)
        tone_to_lo = r.set_multi_tone_vacc([F0_HZ], [0.0], [amp], los=['rx', 'tx'], min_tone_separation=6, slot=i)
        mx.set_current_buffer(0)
    mx.set_acc_len(1024)
    mx.set_slot_auto_mode()
    mx.set_dwell_accs(5)
    r.sync.sw_sync(mrst=True)
    lo = tone_to_lo[0]
    print('LO:', lo)
    acc = r.accumulators[0]
    acc.set_snapshot_chan(lo)
    acc.set_burst_chan(lo)
    acc.set_burst_mode(True)

    print('Getting new burst in auto mode')
    plt.figure()
    plt.subplot(2,1,1)
    d = acc.get_new_burst()
    d /= np.max(np.abs(d))
    print(np.abs(d)[0:15])
    plt.plot(np.abs(d)[0:100])
    print('Getting new burst in manual mode')
    mx.set_slot_manual_mode()
    mx.set_manual_slot(0)
    acc_cnt = acc.get_acc_cnt()
    acc._trigger_burst()
    for i in range(20):
        slot = i % mx.n_slots
        print(f'Setting slot to {slot}')
        mx.set_manual_slot(slot)
        time.sleep(0.2)
    while(acc.get_acc_cnt() == acc_cnt):
        time.sleep(0.2)
    d, _, _, _ = acc._read_bram(get_tt=False)
    plt.subplot(2,1,2)
    plt.plot(np.abs(d))

    # Get a few non burst mode samples and associated tt/buffer ids
    acc.set_burst_mode(False)
    mx.set_slot_auto_mode()
    mx.set_acc_len(1024*1024) # Long enough to read all the registers over katcp
    r.sync.sw_sync(mrst=True) # Needed after acc len change
    told = 0
    for i in range(25):
        d, gpio_counts, t, buf_id, slot_id = acc.get_new_spectra(get_tt=True, get_buf_id=True)
        dt = t - told
        print(f'dt: {dt}, t: {t}, buffer ID: {buf_id}, slot ID: {slot_id}, data[0]: {d[0]}')
        told = t

    plt.show()
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description = "A script to sweep a CW tone over a PSB bin and show response with and without syncs",
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
