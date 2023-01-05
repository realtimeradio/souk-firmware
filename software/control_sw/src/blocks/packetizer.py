import numpy as np
import struct

from .block import Block

MAX_PACKET_SIZE_BYTES = 8192

def _ip_to_int(ip):
    """
    convert an IP string (eg '10.11.10.1') to a 32-bit binary
    string, suitable for writing to an FPGA register.
    """
    octets = list(map(int, ip.split('.')))
    ip_int = (octets[0] << 24) + (octets[1] << 16) + (octets[2] << 8) + octets[3]
    return ip_int

def _int_to_ip(ip):
    """
    convert an IP integer (eg 0x0a0a0a01) to an
    IP string (eg '10.10.10.1')
    """
    sl = [] # list of parts to be joined with dots
    for i in range(4):
        sl += ["%d" % ((ip >> (8*(3-i))) & 0xff)]
    return '.'.join(sl)

class Packetizer(Block):
    """
    The packetizer block allows dynamic definition of
    packet sizes and contents.
    In firmware, it is a simple block which allows
    insertion of header entries  and EOFs at any point in the
    incoming data stream.
    It is up to the user to configure this block such that it
    behaves in a reasonable manner -- i.e.

       - Output data rate does not overflow the downstream Ethernet core
       - Packets have a reasonable size
       - EOFs and headers are correctly placed.

    :param host: CasperFpga interface for host.
    :type host: casperfpga.CasperFpga

    :param name: Name of block in Simulink hierarchy.
    :type name: str

    :param logger: Logger instance to which log messages should be emitted.
    :type logger: logging.Logger

    :param n_chans: Number of frequency channels in the correlation output.
    :type n_chans: int

    :param n_ants: Number of dual-polarization inputs streams in the system.
    :type n_ants: int

    :param sample_rate_mhz: ADC sample rate in MHz. Used for data rate checks.
    :type sample_rate_mhz: float

    :param sample_width: Sample width in bytes (e.g. 4+4 bit complex = 1)
    :type sample_width: int

    :param word_width: Ethernet interface word width, in bytes
    :type word_width: int

    :param line_rate_gbps: Link speed in gigabits per seconds.
    :type line_rate_gbps: float

    :param n_time_packet: Number of time samples per packet
    :type n_time_packet: int

    :param granularity: The number of words per packetizer data block.
    :type granularity: int
    """
    def __init__(self, host, name, n_chans=4096, n_ants=4, sample_rate_mhz=200.0,
            sample_width=1, word_width=64, line_rate_gbps=100., n_time_packet=16,
            granularity=32, logger=None):
        super(Packetizer, self).__init__(host, name, logger)
        NPOL = 2
        self.n_chans = n_chans
        self.n_ants = n_ants
        self.sample_rate_mhz = sample_rate_mhz
        self.sample_width = sample_width
        self.word_width = word_width
        self.line_rate_gbps = line_rate_gbps
        self.n_total_words = NPOL * sample_width * n_chans * n_ants * n_time_packet // word_width
        self.n_words_per_chan = NPOL * self.sample_width * n_time_packet // self.word_width
        self.full_data_rate_gbps = 8*self.sample_width * self.n_ants * self.sample_rate_mhz*1e6 / 1.0e9
        self.granularity = granularity
        self.n_slots = self.n_total_words // granularity

    def _populate_headers(self, headers):
        """
        Populate the voltage mode packetizer header fields.

        :param headers: A list of header dictionaries to populate
        :type headers: list

        Entry `i` of the `headers` list is written to packetizer header BRAM index `i`.
        This represents the control word associated with the `i`th data sample block
        after a sync pulse. Each data block is self.granularity words.

        Each `headers` entry should be a dictionary with the following fields:
          - `first`: Boolean, indicating this sample block is the first in a packet.
          - `valid`: Boolean, indicating this sample block contains valid data.
          - `last`: Boolean, indicating this is the last valid sample block in a packet.
          - `is_8_bit`: Boolean, indicating this packet contains 8-bit data.
          - `is_time_fastest`: Boolean, indicating this packet has a payload in
            channel [slowest] x time x polarization [fastest] order.
          - `n_chans`: Integer, indicating the number of channels in this data block's packet.
          - `chan`: Integer, indicating the first channel present in this data block.
          - `feng_id`: Integer, indicating the F-Engine ID of this block's data.
            This is usually always `self.feng_id`, but may vary if one board is spoofing
            traffic from multiple boards.
          - `dest_ip` : String, the destination IP of this data block (eg "10.10.10.100")
          - `dest_port` : integer, the destination UDP port of this data block.
        """

        h_bytestr = b''
        ip_bytestr = b''
        port_bytestr = b''
        for hn, h in enumerate(headers):
            header_word = (int(h['last']) << 58) \
                        + (int(h['valid']) << 57) \
                        + (int(h['first']) << 56) \
                        + (int(h['is_8_bit']) << 49) \
                        + (int(h['is_time_fastest']) << 48) \
                        + ((h['n_chans'] & 0xffff) << 32) \
                        + ((h['chan'] & 0xffff) << 16) \
                        + ((h['feng_id'] & 0xffff) << 0)
            h_bytestr += struct.pack('>Q', header_word)
            ip_bytestr += struct.pack('>I', _ip_to_int(h['dest_ip']))
            port_bytestr += struct.pack('>I', h['dest_port'])

        self.write('ips', ip_bytestr)
        self.write('header', h_bytestr)
        self.write('ports', port_bytestr)

    def _read_headers(self, n_words=None):
        """
        Get the header entries from one of this board's packetizers.

        :return: headers
        :rtype: list

        Entry `i` of the `headers` list represents the contents of header BRAM index `i`.
        This represents the control word associated with the `i`th data sample block
        after a sync pulse. Each data block is self.granularity words.

        Each `headers` entry should be a dictionary with the following fields:
          - `first`: Boolean, indicating this sample block is the first in a packet.
          - `valid`: Boolean, indicating this sample block contains valid data.
          - `last`: Boolean, indicating this is the last valid sample block in a packet.
          - `is_8_bit`: Boolean, indicating this packet contains 8-bit data.
          - `is_time_fastest`: Boolean, indicating this packet has a payload in
            channel [slowest] x time x polarization [fastest] order.
          - `n_chans`: Integer, indicating the number of channels in this data block's packet.
          - `chans`: list of ints, indicating the channels present in this data block.
          - `feng_id`: Integer, indicating the F-Engine ID of this block's data.
            This is usually always `self.feng_id`, but may vary if one board is spoofing
            traffic from multiple boards.
          - `dest_ip` : String, the destination IP of this data block (eg "10.10.10.100")
          - `dest_port` : Integer, the destination IP of this data block
        """

        if n_words is None:
            n_words = self.n_total_words // self.granularity
        hs_raw = self.read('header', 8*n_words)
        ips_raw = self.read('ips', 4*n_words)
        ports_raw = self.read('ports', 4*n_words)
        hs = struct.unpack('>%dQ' % n_words, hs_raw)
        ips = struct.unpack('>%dI' % n_words, ips_raw)
        ports = struct.unpack('>%dI' % n_words, ports_raw)

        headers = []
        for dn, d in enumerate(hs):
            headers += [{}]
            headers[-1]['feng_id'] = (d >> 0) & 0xffff
            headers[-1]['chans'] = (d >> 16) & 0xffff
            headers[-1]['n_chans'] = (d >> 32) & 0xffff
            headers[-1]['is_time_fastest'] = bool((d >> 48) & 1)
            headers[-1]['is_8_bit'] = bool((d >> 49) & 1)
            headers[-1]['first'] = bool((d >> 56) & 1)
            headers[-1]['valid'] = bool((d >> 57) & 1)
            headers[-1]['last'] = bool((d >> 58) & 1)
            headers[-1]['dest_ip'] = _int_to_ip(ips[dn])
            headers[-1]['dest_port'] = ports[dn]
        return headers

    def get_packet_info(self, n_pkt_chans, n_chan_send, n_ant_send, occupation=0.985, chan_block_size=4):
        """
        Get the packet boundaries for packets containing a given number of
        frequency channels.
        
        :param n_pkt_chans: The number of channels per packet.
        :type n_pkt_chans: int

        :param n_chan_send: The number of channels to send per input
        :type n_chan_send: int

        :param n_ant_send: The number of antennas to send
        :type n_ant_send: int

        :param occupation: The maximum allowed throughput capacity of the underlying link.
            The calculation does not include application or protocol overhead,
            so must necessarily be < 1.
        :type occupation: float

        :param chan_block_size: The granularity with which we can start packets.
            I.e., packets must start on an n*`chan_block` boundary.
        :type chan_block_size: int

        :return: packet_starts, packet_payloads, word_indices, antchan_indices

            ``packet_starts`` : list of ints
                The word indexes where packets start -- i.e., where headers should be
                written.
                For example, a value [0, 1024, 2048, ...] indicates that headers
                should be written into underlying brams at addresses 0, 1024, etc.
            ``packet_payloads`` : list of range()
                The range of indices where this packet's payload falls. Eg:
                [range(1,257), range(1025,1281), range(2049,2305), ... etc]
                These indices should be marked valid, and the last given an EOF.
            ``word_indices`` : list of range()
                The range of input word indices this packet will send. Eg:
                [range(1,129), range(1025,1153), range(2049,2177), ... etc].
                Data to be sent should be places in these ranges. Data words outside
                these ranges won't be sent anywhere.
            ``antchan_indices`` : list of range()
                The range of input antchan indices this packet will send. Eg:
                [range(1,129), range(1025,1153), range(2049,2177), ... etc].
                Data to be sent should be places in these antchan ranges.
                Data words outside these ranges won't be sent anywhere.
        """

        # In this packetizer, we arrange output data as:
        # n_chans // 32 x IFs [2] x 50% duty cycle x chans [32] x n_time_packet x pol [2]
        assert occupation < 1, "Link occupation must be < 1"
        pkt_size = n_pkt_chans * self.n_words_per_chan * self.word_width
        assert pkt_size <= MAX_PACKET_SIZE_BYTES, "Can't send packets > %d bytes!" % MAX_PACKET_SIZE_BYTES

        # Figure out what fraction of channels we can fit on the link
        self._info("Full data rate is %.2f Gbps" % self.full_data_rate_gbps)
        req_gbps = self.full_data_rate_gbps / self.n_ants / self.n_chans * n_chan_send * n_ant_send

        self._info("Trying to send %d ants and %d chans (%.2f Gbps)" % (n_ant_send, n_chan_send, req_gbps))
        assert req_gbps <= occupation * self.line_rate_gbps, "Too much data!"

        # How many slots do we need to send the required data
        assert n_chan_send <= self.n_chans
        assert n_ant_send <= self.n_ants
        assert n_chan_send % n_pkt_chans == 0, "Number of channels to send is not integer number of packets"
        req_packets = n_ant_send * n_chan_send // n_pkt_chans
        self._info("Sending %d antenna-channels as %d packets" % (n_chan_send*n_ant_send, req_packets))
        req_words = n_chan_send * n_ant_send * self.n_words_per_chan
        assert (n_chan_send * self.n_words_per_chan) % self.granularity == 0
        req_slots = req_words // self.granularity
        assert req_slots % req_packets == 0
        req_slots_per_pkt = req_slots // req_packets
        self._info("Sending %d words in %d slots" % (req_words, req_slots))
        spare_slots = self.n_slots - req_slots
        self._info("%d spare slots available" % spare_slots)
        assert spare_slots >= req_packets

        # Divvy up the spare slots as evenly as we can
        spare_slots_per_pkt = spare_slots // req_packets
        self._info("%d spare slots per packet" % spare_slots_per_pkt)
        # Need at least two words of spare space for EOF, and then a cycle of invalid data (irrational 100GbE core requirement)
        assert spare_slots_per_pkt > 0, "Need at least one spare slot per packet!"
        assert spare_slots_per_pkt*self.granularity >= 2, "Need at least two spare words per packet"
        total_slots_used = req_slots + (req_packets * spare_slots_per_pkt)
        self._info("%d used slots for data and spacing" % total_slots_used)
        assert total_slots_used <= self.n_slots

        # Now we know where the slots are, figure out what channels / inputs they
        # would naturally be associated with, if data comes from the upstream reorder in
        # input x channel x time order.
        # It's then up to the user to put inputs / channels in these slots.
        starts = []
        payloads = []
        indices = []
        antchans = []
        for i in range(n_ant_send):
            packets_per_ant = n_chan_send // n_pkt_chans
            for c in range(packets_per_ant):
                packet_num = i*packets_per_ant + c
                slot_num = packet_num * (req_slots_per_pkt + spare_slots_per_pkt)
                slot_start = slot_num
                slot_stop = slot_start + req_slots_per_pkt
                word_start = slot_start * self.n_words_per_chan
                word_stop = slot_stop * self.n_words_per_chan
                antchan_start = n_ant_send * word_start // self.n_words_per_chan
                antchan_stop = n_ant_send * word_stop // self.n_words_per_chan
                starts += [slot_num]
                payloads += [range(slot_start, slot_stop)]
                indices += [range(word_start, word_stop)]
                antchans += [range(antchan_start, antchan_stop)]

        return starts, payloads, indices, antchans
        
    def write_config(self, packet_starts, packet_payloads, channel_indices,
            antenna_ids, dest_ips, dest_ports, nchans_per_packet, enable=None):
        """
        Write the packetizer configuration BRAMs with appropriate entries.

        :param packet_starts:
            Word-indices which are the first entry of a packet and should
            be populated with headers (see `get_packet_info()`)
        :type packet_starts: list of int

        :param packet_payloads:
            Word-indices which are data payloads, and should be marked as
            valid (see `get_packet_info()`)
        :type packet_payloads: list of range()s

        :param channel_indices:
            Header entries for the channel field of each packet to be sent
        :type channel_indices: list of ints

        :param antenna_ids:
            Header entries for the antenna field (feng_id) of each packet to be sent
        :type ant_indices: list of ints

        :param dest_ips: list of str
            IP addresses for each packet to be sent. If an IP is '0.0.0.0',
            the corresponding packet will be marked invalid.
        :type dest_ips:

        :param dest_ports:
            UDP destination ports for each packet to be sent.
        :type dest_ports: list of int

        :param nchans_per_packet: Number of frequency channels per packet sent.
        :type nchans_per_packet: list of int

        :param enable: List of booleans to enable each packet. If None, all
            packets are assumed valid.
        :type enable: list of bool

        All parameters should have identical lengths.
        """
        n_packets = len(packet_starts)

        def check_length(x, expected_len, name):
            if len(x) != expected_len:
                self._error("%s list length %d for %d packets" % (name, len(x), expected_len))
                raise RuntimeError

        if enable is None:
            enable = [True] * n_packets

        check_length(packet_payloads, n_packets, 'packet_payloads')
        check_length(channel_indices, n_packets, 'channel_indices')
        check_length(antenna_ids, n_packets, 'antenna IDs')
        check_length(dest_ips, n_packets, 'dest ips')
        check_length(dest_ports, n_packets, 'dest_ports')
        check_length(nchans_per_packet, n_packets, 'chans_per_packet')

        # generate template headers for all invalid data
        headers = []
        for i in range(self.n_slots):
            headers += [{
                'first': False,
                'valid': False,
                'last': False,
                'is_8_bit': True,
                'is_time_fastest': True,
                'n_chans': 0,
                'chan': 0,
                'feng_id': 0,
                'dest_ip': '0.0.0.0',
                'dest_port': 0,
                }]

        for p in range(n_packets):
            b = packet_starts[p]
            headers[b]['first'] = (enable[p] and dest_ips[p] != '0.0.0.0')
            for j in packet_payloads[p]:
                headers[j]['valid'] = (enable[p] and dest_ips[p] != '0.0.0.0')
                headers[j]['n_chans'] = nchans_per_packet[p]
                headers[j]['chan'] = channel_indices[p]
                headers[j]['feng_id'] = antenna_ids[p]
                headers[j]['dest_ip'] = dest_ips[p]
                headers[j]['dest_port'] = dest_ports[p]
            headers[packet_payloads[p][-1]]['last'] = (enable[p] and dest_ips[p] != '0.0.0.0')

        self._populate_headers(headers)
