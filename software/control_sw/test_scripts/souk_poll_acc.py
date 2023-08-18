#!/usr/bin/env python3

import argparse
import time
import logging
import socket
import struct
import numpy as np

FPGFILE = '/home/casper/git/souk-firmware/firmware/src/souk_single_pipeline_4x2/outputs/souk_single_pipeline_4x2.fpg'
ACCNUM = 0
WAIT_FOR_IP_ADDR = True
DESTPORT = 10000

def get_bram_addresses(acc):
    addrs = []
    nbytes = acc._n_serial_chans * np.dtype(acc._dtype).itemsize
    if acc._is_complex:
        nbytes *= 2
    for i in range(acc._n_parallel_chans):
        ramname = f'{acc.prefix}dout{i}'
        addrs += [acc.host.transport._get_device_address(ramname)]
    for i in range(1,acc._n_parallel_chans):
        assert addrs[i] == addrs[i-1] + nbytes
    return addrs, nbytes

def fast_read_bram(acc, addrs, nbytes):
    """
    Read RAM containing accumulated spectra.
    
    :return: time, data, error.
        time: integer timestamp of accumulation
        data: Array of complex valued data, in int32 format. Array
              dimensions are [FREQUENCY CHANNEL].
        error: True if there was an accumulation counter change during reading.
               False otherwise
    :rtype: int, numpy.array, bool
    """
    nbranch = len(addrs)
    base_addr = addrs[0]
    dout = np.zeros(acc.n_chans * 2, dtype='>i4')
    start_acc_cnt = acc.get_acc_cnt()
    for i, addr in enumerate(addrs):
        raw = acc.host.transport.axil_mm[addr:addr + nbytes]
        dout[i::nbranch] = np.frombuffer(raw, dtype='>i4')
    stop_acc_cnt = acc.get_acc_cnt()
    if start_acc_cnt != stop_acc_cnt:
        acc.logger.warning('Accumulation counter changed while reading data!')
        return start_acc_cnt, dout, True
    return start_acc_cnt, dout, False

def wait_non_zero_ip(acc, poll_time_s=1):
    loop_cnt = 0
    while True:
        ip = acc.get_dest_ip()
        if ip == '0.0.0.0':
            time.sleep(poll_time_s)
            ip = acc.get_dest_ip()
        else:
            if loop_cnt > 0: # Don't print anything if we haven't waited for an IP change
                print('Got non-zero IP: %s' % ip)
            break
        loop_cnt += 1
    return ip


def format_packets(t, d, error=False, pkt_nbyte=1024):
    """
    Return a list of packet binary payloads.

    Format is:
        uint64 accumulation_index # increments by 1 with each new accumulation
        uint32 error flag # 1 if there was a read error, likely because this code is too slow for the selected integration length
        uint32 packet_index # Index of this packet within a single accumulation
        int32[channels, real/imag] # Data payload

    All entries are big-endian, except data payload which is little-endian
    """
    payload_bytes = d.tobytes()
    payload_nbyte = len(payload_bytes)
    assert payload_nbyte % pkt_nbyte == 0
    npkt = payload_nbyte // pkt_nbyte
    packets = []
    header = struct.pack('>QI', t, int(error))
    for i in range(npkt):
        packets += [header + struct.pack('>I', i) + payload_bytes[i*pkt_nbyte:(i+1)*pkt_nbyte]]
    return packets
    

def main(args):
    from souk_mkid_readout import SoukMkidReadout
    r = SoukMkidReadout('localhost', fpgfile=args.fpgfile, local=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    acc = r.accumulators[ACCNUM]
    addrs, nbytes = get_bram_addresses(acc)
    acc._wait_for_acc(0.00005)
    t0 = time.time()
    ip = None
    err_cnt = 0
    loop_cnt = 0
    times = []
    while True:
        if args.wait_for_ip:
            ip = wait_non_zero_ip(acc)
        acc._wait_for_acc(0.00005)
        tt0 = time.time()
        t, d, err = fast_read_bram(acc, addrs, nbytes)
        if ip is not None:
            for p in format_packets(t, d, error=err):
                sock.sendto(p, (ip, args.destport))
        if err:
            err_cnt += 1
        tt1 = time.time()
        times += [tt1 - tt0]
        loop_cnt += 1
        if loop_cnt == args.nloop:
            break
    t1 = time.time()
    avg_read_ms = np.mean(times)*1000
    max_read_ms = np.max(times)*1000
    avg_loop_ms = (t1-t0)/loop_cnt * 1000
    print(f'Average read time: {avg_read_ms:.2f} ms')
    print(f'Max read time: {max_read_ms:.2f} ms')
    print(f'Average loop time: {avg_loop_ms:.2f} ms')
    print(f'Number of reads: {loop_cnt}')
    print(f'Number of too slow reads: {err_cnt}')
    sock.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description = "Configure an RFSoC to transmit accumulations",
        formatter_class = argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--fpgfile", type=str, default=FPGFILE,
        help = "Configuration .fpg file with which to obtain register addresses",
    )

    parser.add_argument("--wait_for_ip", action="store_true",
        help = "If set, do nothing unless the IP address register is non-zero"
    )

    parser.add_argument("--nloop", type=int, default=0,
        help = "If >0, only read this many accumulations before breaking",
    )

    parser.add_argument("--destport", type=int, default=DESTPORT,
        help = "Default destination UDP port",
    )

    args = parser.parse_args()
    main(args)

