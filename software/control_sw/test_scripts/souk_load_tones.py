#! /usr/bin/env python

"""
An example script schowing how to configure the RFSoC 4x2
readout system to output arbitrary tones using a
polyphase synthesizer
"""
import argparse
import numpy as np
from souk_mkid_readout import SoukMkidReadout

def main(host, configfile, freqs_hz, randomphase=False):
    """
    Configure RFSoC 4x2 ``host`` with configuration
    described by ``configfile``. Then load the polyphase
    synthesizer with tones at frequencies listed in ``freqs_hz``.
    If ``randomphase``, apply random phases to each tone.
    """
    print(f"Connecting to board {host}")
    r = SoukMkidReadout(host, configfile=configfile)

    # Put everything in a known starting state
    r.program()
    r.initialize()

    # Configure the output to be based on the polphase synth
    r.output.use_psb()

    ## Could internally loopback in order to use r.input.plot_adc*()
    # r.input.enable_loopback()

    # Load tones
    n_tones = len(freqs_hz)
    if randomphase:
        phases = np.random.uniform(-np.pi, np.pi, n_tones)
    else:
        phases = np.zeros(n_tones)
    # If tones are too close together there is a risk that two
    # will end up in the same polphase synth bin, which the firmware
    # doesn't currently support.
    min_tone_separation_hz = r.adc_clk_hz / r.psb_chanselect.n_chans_out / 2
    freqs_hz = np.array(freqs_hz)
    for i in range(n_tones):
        f = freqs_hz[i]
        p = phases[i]
        print(f"Loading freq {f} Hz with phase {p} radians in slot {i}")
        if f < 0:
            print(f"Skipping frequency {f} Hz which is negative")
            continue
        if f > r.adc_clk_hz:
            print(f"Skipping frequency {f} Hz which is outside the first nyquist zone")
            continue
        # Figure out if there might be a problem with tones too close
        offsets_hz = np.abs(freqs_hz - f)
        if n_tones > 1:
            closest_offset_hz = min(offsets_hz[offsets_hz>0])
            if closest_offset_hz < min_tone_separation_hz:
                print(f"Warning: Frequency {f} Hz is only {closest_offset_hz}<{min_tone_separation_hz} from its neighbour")
        r.set_tone(i, f, phase_offset_rads=p)
    # Set the Polyphase Synthesizer shift schedule. I.e., scale the
    # PSB FFT so that it cannot overflow, based on the number of input tones
    shift_stages = int(np.ceil(np.log2(n_tones)))
    shift_schedule = 2**(shift_stages) - 1
    print(f"Setting output FFT schedule to {shift_schedule:x}")
    r.psb.set_fftshift(shift_schedule)
    
    # Now the tones are loaded, reset all the phase accumulators
    print("Resetting phase accumulators")
    r.sync.arm_sync()
    r.sync.sw_sync() # Not necessary if there is a PPS connected

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description = "Configure an RFSoC to output arbitrary tones",
        formatter_class = argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("host", type=str, default='rfsoc4x2',
        help = "Hostname / IP address of FPGA board to configure",
    )

    parser.add_argument("configfile", type=str, default='my_config.yaml',
        help = "Configuration YAML file with which to configure",
    )

    parser.add_argument("freqs", type=str, default='13.6,14.8',
        help = "Comma-separated set of frequencies to output, in Hz"
    )

    parser.add_argument("--randomphase", action="store_true",
        help = "If set, randomize phases of transmitted tones"
    )
    args = parser.parse_args()
    freqs = list(map(float, args.freqs.split(',')))
    main(args.host, args.configfile, freqs, args.randomphase)
