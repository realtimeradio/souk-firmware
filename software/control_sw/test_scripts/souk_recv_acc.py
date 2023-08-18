#!/usr/bin/env python3

import argparse
import time
import logging
import socket
import struct
import numpy as np

DESTPORT = 10000

# Todo: parameterize or read from board
EXPECTED_DATA_REAL = np.arange(0,4096,2)*2 # *2 is because TVGs have 17 fractional bits but acc input has 18
EXPECTED_DATA_IMAG = np.zeros(2048)*2

def decode_packet(p):
    """
    Return a dictionary of packet payloads.

    Format is (names are dictionary keys):
        uint64 accumulation_index # increments by 1 with each new accumulation
        uint32 error flag # 1 if there was a read error, likely because this code is too slow for the selected integration length
        uint32 packet_index # Index of this packet within a single accumulation
        int32  data[channels, real/imag] # Data payload
    """
    acc_index, error_flag, pkt_index = struct.unpack('>QII', p[0:16])
    d = np.frombuffer(p[16:], dtype='<i4')
    return {'accumulation_index': acc_index, 'error_flag': error_flag, 'packet_index': pkt_index, 'data': d}
    

def main(args):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', args.destport))
    t0 = time.time()
    err_cnt = 0
    vld_cnt = 0
    loop_cnt = 0
    times = []
    while True:
        p = sock.recv(8192)
        if p is not None:
            d = decode_packet(p)
            if args.print:
                print(d)
            if d['error_flag']:
                err_cnt += 1
            if args.acc_len is not None:
                nchans_per_pkt = len(d['data'])//2
                start_chan = d['packet_index'] * nchans_per_pkt
                exp_r = EXPECTED_DATA_REAL[start_chan : start_chan + nchans_per_pkt] * args.acc_len
                exp_i = EXPECTED_DATA_IMAG[start_chan : start_chan + nchans_per_pkt] * args.acc_len
                ok = np.all(d['data'][0::2] == exp_r)
                ok = ok and np.all(d['data'][1::2] == exp_i)
                if not ok:
                    vld_cnt += 1
                    print('Validation Error!')
                    print('Received [real]:', d['data'][0::2])
                    print('Expected [real]:', exp_r)
                    print('Received [imag]:', d['data'][1::2])
                    print('Expected [imag]:', exp_i)

        loop_cnt += 1
        if loop_cnt == args.nloop:
            break
    t1 = time.time()
    print(f'Number of reads: {loop_cnt}')
    print(f'Number of too slow reads: {err_cnt}')
    if args.acc_len is not None:
        print(f'Number of validation errors : {vld_cnt}')
    else:
        print('Did not validate data because acc_len was not provided')
    sock.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description = "Receive accumulations transmitted from an RFSoC",
        formatter_class = argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--nloop", type=int, default=0,
        help = "If >0, only read this many accumulations before breaking",
    )

    parser.add_argument("--destport", type=int, default=DESTPORT,
        help = "Default destination UDP port",
    )
    
    parser.add_argument("--print", action='store_true',
        help = "Print packet contents",
    )

    parser.add_argument("--acc_len", type=int, default=None,
        help = "If provided, verify that the received data is compatible with "
        "this accumulation length. The transmissing board should be in test mode: "
        " `pfbtvg.write_freq_ramp(); pfbtvg.tvg_enable()` with every second "
        " channel selected: `chanselect.set_channel_outmap(range(0, 4096, 2))`"
    )

    args = parser.parse_args()
    main(args)

