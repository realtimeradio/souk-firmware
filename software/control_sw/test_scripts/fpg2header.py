#!/usr/bin/env python3

import argparse

def gen_header(infile, outfile):
    with open(infile, 'r', errors='ignore') as ifh:
        with open(outfile, 'w') as ofh:
            while(True):
                line = ifh.readline()
                if line.startswith('?quit'):
                    break
                elif line.startswith('?register'):
                    _, name, addr, size = line.split('\t') # addr and size are already strings eg '0xbeef'
                    name = name.upper()
                    addr = addr.strip()
                    size = size.strip()
                    ofh.write(f'#define FPGA_REG_{name}_ADDR {addr}\n')
                    ofh.write(f'#define FPGA_REG_{name}_SIZE {size}\n')
                else:
                    continue

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description = "Write a C header file defining register addresses",
        formatter_class = argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--fpgfile", type=str,
        help = ".fpg file to read as input.",
    )

    parser.add_argument("--hfile", type=str,
        help = ".h file to write",
    )
    
    args = parser.parse_args()
    gen_header(args.fpgfile, args.hfile)

