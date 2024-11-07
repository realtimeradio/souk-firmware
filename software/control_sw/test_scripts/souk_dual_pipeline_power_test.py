#! /usr/bin/env python

"""
An example script schowing how to configure the RFSoC 4x2
readout system to output arbitrary tones using a
polyphase synthesizer
"""
import argparse
import numpy as np
from souk_mkid_readout import SoukMkidReadout

DEFAULT_FPG = "../../../firmware/src/souk_dual_pipeline_krm/outputs/souk_dual_pipeline_krm.fpg"
DEFAULT_NTONES = 2000

def main(host, fpgfile, ntones):
    """
    Configure RFSoC 4x2 ``host`` with ``fpgfile``.
    Output ``ntones`` different tones via the PSB,
    with all FFT shifts set to max power
    """
    print(f"Connecting to board {host}")
    print(f"Instantiating pipeline 0")
    p0 = SoukMkidReadout(host, pipeline_id=0)
    print(f"Programming {fpgfile}")
    p0.program(fpgfile)
    print(f"Instantiating pipeline 1")
    p1 = SoukMkidReadout(host, fpgfile=fpgfile, pipeline_id=1)

    pipelines = [p0, p1]

    # Put everything in a known starting state
    for p in pipelines:
        print(f"Initializing {p.hostname}:{p.pipeline_id}")
        p.initialize()

    for p in pipelines:
        print(f"Configuring tones for {p.hostname}:{p.pipeline_id}")
        # Configure the output to be based on the polphase synth
        p.output.use_psb()

        # Load tones
        freqs = np.linspace(0,2000e6,ntones) + np.random.uniform(0,100e3,ntones)
        phases = np.random.uniform(-np.pi, np.pi, ntones)
        # If tones are too close together there is a risk that two
        # will end up in the same polphase synth bin, which the firmware
        # doesn't currently support. But don't worry about this for power checking purposes
        p.set_multi_tone(freqs, phases)

        # Minimize shift schedules for maximum power.
        p.pfb.set_fftshift(0)
        p.psb.set_fftshift(0)

        # Redirect DAC to ADC to max out input power
        p.input.enable_loopback()

        p.sync.arm_sync(wait=False)
        p.sync.sw_sync()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description = "Configure an RFSoC to output arbitrary tones",
        formatter_class = argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--host", type=str, default="10.11.0.133",
        help = "Hostname / IP address of FPGA board to configure",
    )

    parser.add_argument("--fpgfile", type=str, default=DEFAULT_FPG,
        help = ".fpg firmware binary to program",
    )

    parser.add_argument("--ntones", type=int, default=DEFAULT_NTONES,
        help = "Number of random tones to load",
    )

    args = parser.parse_args()
    main(args.host, args.fpgfile, args.ntones)
