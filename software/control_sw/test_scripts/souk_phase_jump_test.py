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
    
    ## now make the faster interface
    #r = souk_mkid_readout.SoukMkidReadout(HOST, configfile=CONFIG,
    #                                      pipeline_id=PIPELINE_ID, local=True)
    
    
    
    r.pfb.set_fftshift(0b111111111111)
    r.psb.set_fftshift(0b0)
    r.psbscale.set_scale(1.0)
    
    r.output.use_psb()
    r.input.enable_loopback()
    r.sync.sw_sync(mrst=True)        # v7.10: one-time reset+start (arm_sync no longer needed for sw_sync)
    
    mx  = r.mixer
    sync_skew = mx.read_uint('pipeline_latency')
    print(f'Mixer reports RX vs TX delay {sync_skew} FPGA clocks')
    #mm  = np.frombuffer(mx.host.transport.axil_mm, dtype='<u4')
    FFT_RBW = r.adc_clk_hz * mx._upstream_oversample_factor / mx._n_upstream_chans
    
    print(f"adc_clk_hz                  = {r.adc_clk_hz/1e9:.4f} GHz")
    print(f"channel rate (FFT_RBW)      = {FFT_RBW/1e3:.1f} kHz")
    print(f"FFT frame                   = {1e6/FFT_RBW:.4f} us")
    
    
    # do direct 32-bit control-buffer writers (avoids the r.mixer.write SIGBUS)
    def _word_addr(lo_name, chan, buf):
        p = chan % mx._n_parallel_chans
        s = chan // mx._n_parallel_chans
        base = mx.host.transport._get_device_address(f'{mx.prefix}{lo_name}_lo{p}_control')
        return (base + 4 * mx._CONTROL_N_WORDS * (buf * mx._n_serial_chans + s)) // 4
    
    def write_row(lo_name, chan, buf, freq_off_hz, amp, phase_off_rad=0.0):
        """Write the full 4-word (128-bit) control row as four 32-bit stores."""
        wa = _word_addr(lo_name, chan, buf)
        phase = freq_off_hz / FFT_RBW * 2 * np.pi
        pi_i, po_i = mx._format_phase_step(np.array([phase]), np.array([phase_off_rad]))
        ri = int(cplx2uint(np.cos(phase) + 1j * np.sin(phase), mx._n_ri_step_bits))
        mm[wa + mx._PHASE_INC_WORD_OFFSET]    = np.int32(int(pi_i[0])).view('<u4')
        mm[wa + mx._RI_STEP_WORD_OFFSET]      = np.uint32(ri)
        mm[wa + mx._PHASE_OFFSET_WORD_OFFSET] = np.int32(int(po_i[0])).view('<u4')
        mm[wa + mx._SCALE_WORD_OFFSET]        = np.uint32(int(mx._format_amp_scale(amp)))
    
    def write_freq(lo_name, chan, buf, freq_off_hz):
        """update only PHASE_INC + RI_STEP (two 32-bit stores)."""
        #wa = _word_addr(lo_name, chan, buf)
        phase = freq_off_hz / FFT_RBW * 2 * np.pi
        mx.set_phase_step(chan, phase=phase, phase_offset=0.0, los=[lo_name], next_buf=buf)
        #print(f'Setting phase step to {phase} radians')
        #pi_i, _ = mx._format_phase_step(np.array([phase]), np.array([0.0]))
        #ri = int(cplx2uint(np.cos(phase) + 1j * np.sin(phase), mx._n_ri_step_bits))
        #mm[wa + mx._PHASE_INC_WORD_OFFSET] = np.int32(int(pi_i[0])).view('<u4')
        #mm[wa + mx._RI_STEP_WORD_OFFSET]   = np.uint32(ri)
    
    
    # initialise BOTH buffers
    tone_to_lo = r.set_multi_tone_vacc([F0_HZ], [0.0], [AMP], los=['rx', 'tx'], min_tone_separation=6)
    lo = tone_to_lo[0]
    base_bin, base_off = r._get_closest_pfb_bin(F0_HZ)
    bin_center_hz = F0_HZ - base_off
    for buf in (0, 1):                       # full rows: correct values, valid SCALE in both buffers
        mx.set_amplitude_scale(lo, AMP, los=['rx', 'tx'], next_buf=buf)
        #write_row('rx', lo, buf, base_off, AMP)
        #write_row('tx', lo, buf, base_off, AMP)
    mx.set_current_buffer(0)
    
    acc = r.accumulators[0]
    print('LO:', lo)
    acc.set_snapshot_chan(lo)
    
    def get_tone_phase():
        for _ in range(SETTLE):
            acc.get_new_snapshot()
        z = np.asarray(acc.get_new_snapshot(), dtype=np.complex128)
        m = z.mean()
        return np.angle(m), np.abs(m)
    
    
    # sweep the tone across one bin, ping-ponging the buffers, with different post-swap sync modes.
    #
    # v7.10 timed-sync: the post-swap sync is now r.sync.sw_sync(mrst=...) - no arm_sync needed
    
    #So test three cases:
    #   - no sync           : never re-reference after the swap (old "off" behaviour)
    #   - sync, mrst=False  : re-reference RX/TX only 
    #   - sync, mrst=True   : reset + sync 
    freqs = F0_HZ + np.linspace(-HALFSPAN_HZ, HALFSPAN_HZ, N_POINTS)
    sync_modes = [
        ("no sync",         None),
        ("sync, mrst=False", lambda: r.sync.sw_sync(mrst=False)),
        ("sync, mrst=True",  lambda: r.sync.sw_sync(mrst=True)),
    ]
    results = {}
    for label, do_sync in sync_modes:
        ph = np.zeros(N_POINTS); mag = np.zeros(N_POINTS)
        for i, f in enumerate(freqs):
            lo_off = float(f) - bin_center_hz
            inactive = 1 - r.mixer.get_current_buffer()
            write_freq('rx', lo, inactive, lo_off)
            write_freq('tx', lo, inactive, lo_off)
            r.mixer.set_current_buffer(inactive)
            if do_sync is not None:
                do_sync()
            ph[i], mag[i] = get_tone_phase()
            if i>0:
                diff = ph[i] - ph[i-1]
                print(f'phase diff: {diff}')
        uph = np.unwrap(ph)
        slope = np.polyfit(freqs - freqs.mean(), uph, 1)[0]      # rad/Hz
        delay = -slope / (2 * np.pi)
        results[label] = (uph, mag)
        print(f"{label:16s} -> fitted group delay = {delay*1e9:10.1f} ns "
              f"= {delay*FFT_RBW:7.2f} FFT frames = {delay*r.adc_clk_hz:10.0f} ADC samples")
    
    
    # plot and save
    fig, (axp, axm) = plt.subplots(2, 1, sharex=True, figsize=(10, 6))
    #for label, c in [("no sync", 'C3'), ("sync, mrst=False", 'C0'), ("sync, mrst=True", 'C2')]:
    for label, do_sync in sync_modes:
        uph, mag = results[label]
        axp.plot((freqs - F0_HZ)/1e3, uph, '.-', label=label) #color=c, label=label)
        axm.plot((freqs - F0_HZ)/1e3, mag, '.-') #, color=c)
    axp.set_ylabel("unwrapped phase [rad]"); axp.legend()
    axm.set_ylabel("|snapshot mean|"); axm.set_xlabel("tone offset from F0 [kHz]")
    fig.suptitle("v7.10 LO retune via control-buffer swap: phase reference vs post-swap sync (mrst on/off)")
    plt.tight_layout(); fig.savefig("buffer_swap_phase.png")


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
