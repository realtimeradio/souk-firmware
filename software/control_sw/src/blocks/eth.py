import time

from .block import Block
from cosmic_f.error_levels import *

class Eth(Block):
    """
    Instantiate a control interface for a 100 GbE block.

    :param host: CasperFpga interface for host.
    :type host: casperfpga.CasperFpga

    :param name: Name of block in Simulink hierarchy.
    :type name: str

    :param logger: Logger instance to which log messages should be emitted.
    :type logger: logging.Logger
    """
    _CORE_NAME = 'onehundred_gbe' #: 100G core name in simulink
    def __init__(self, host, name, logger=None):
        super(Eth, self).__init__(host, name, logger)
        self._get_eth_core()

    def _get_eth_core(self):
        """
        Associate the CasperFpga GbE object associated with this block's Ethernet
        interface with ``self.core``. Sets the ``core`` attribute to None
        if the core can't be found.
        """
        try:
            self.core = self.host.gbes["%s_%s" % (self.name, self._CORE_NAME)]
        except:
            self.core = None
        if self.core is None:
            self._warning("Couldn't find Ethernet core. Will retry later")

    def get_eth_core_details(self, read_arp=False):
        """
        Get Ethernet core parameters, returned as a dictionary of strings.

        :param read_arp: If True, read the ARP table.
        :type read_arp: Bool

        :return: Dictionary of status keys, with each holding a string value.

        """
        x = self.core.get_gbe_core_details(read_arp=read_arp)
        xstr = {}
        for k, v in x.items():
            xstr[k] = str(v)
        return xstr

    def add_arp_entry(self, ip, mac):
        """
        Set a single arp entry.

        :param ip: The IP address matching the given MAC in dotted-quad
            string notation. Eg. '10.10.10.1'.
        :type ip: str

        :param mac: The MAC address to be loaded to the ARP cache.
        :type mac: int
        """
        if self.core is None:
            self._get_eth_core()
        if self.core is None:
            raise RuntimeError("Couldn't get Ethernet CasperFpga object")
        self.core.set_single_arp_entry(ip, mac)

    def get_status(self):
        """
        Get status and error flag dictionaries.
        See also: ``status_reset``.

        Status keys:

            - tx_of : Count of TX buffer overflow events.
            - tx_full : Count of TX buffer full events.
            - tx_vld : Count of 512-bit words marked as valid for transmission.
            - tx_ctr: Count of transmission End-of-Frames marked valid.

        :return: (status_dict, flags_dict) tuple. `status_dict` is a dictionary of
            status key-value pairs. flags_dict is
            a dictionary with all, or a sub-set, of the keys in `status_dict`. The values
            held in this dictionary are as defined in `error_levels.py` and indicate
            that values in the status dictionary are outside normal ranges.

        """
        stats = {}
        flags = {}

        stats['tx_of'  ] = self.read_uint(self._CORE_NAME + '_gmac_reg_tx_overflow_count')
        stats['tx_full'] = self.read_uint(self._CORE_NAME + '_gmac_reg_tx_almost_full_count')
        stats['tx_vld' ] = self.read_uint(self._CORE_NAME + '_txvldctr')
        stats['tx_ctr' ] = self.read_uint(self._CORE_NAME + '_txctr')
        if stats['tx_of'] > 0:
            flags['tx_of'] = FENG_ERROR
        if stats['tx_full'] > 0:
            flags['tx_full'] = FENG_WARNING
        if stats['tx_ctr'] == 0:
            flags['tx_ctr'] = FENG_WARNING
        if stats['tx_vld'] == 0:
            flags['tx_vld'] = FENG_WARNING
        return stats, flags
        
    def status_reset(self):
        """
        Reset all status counters.
        """
        self.change_reg_bits('ctrl', 0, 18)
        self.change_reg_bits('ctrl', 1, 18)
        self.change_reg_bits('ctrl', 0, 18)

    def reset(self):
        """
        Disable, then reset the 40 GbE core. It must be enabled with
        ``enable_tx`` before traffic will be transmitted.
        """
        # stop traffic before reset
        self.disable_tx()
        # toggle reset
        self.change_reg_bits('ctrl', 0, 0)
        self.change_reg_bits('ctrl', 1, 0)
        self.change_reg_bits('ctrl', 0, 0)

    def get_packet_rate(self):
        """
        Get the approximate packet rate, in packets-per-second.

        :return pps: Approximate number of packets sent in the last second.
        :rtype pps: int
        """
        v, _ = self.get_status()
        c0 = v['tx_ctr']
        time.sleep(1)
        v, _ = self.get_status()
        c1 = v['tx_ctr']
        return c1 - c0

    def enable_tx(self):
        """
        Enable Ethernet transmission.
        """
        self.change_reg_bits('ctrl', 1, 1)

    def disable_tx(self):
        """
        Disable Ethernet transmission.
        """
        self.change_reg_bits('ctrl', 0, 1)
    
    def tx_enabled(self):
        """
        Ethernet transmission enabled.
        """
        return self.get_reg_bits('ctrl', 1)

    def initialize(self, read_only=False):
        """
        Initialize the block.
        See also: ``configure_source``, which sets transmission source attributes.

        :param read_only: If False, reset error counters and disable and reset
            core. If True, do nothing.
        :type read_only: bool
        """
        if read_only:
            return
        else:
            self.disable_tx()
            self.reset()
            self.status_reset()

    def configure_source(self, mac, ip, port):
        """
        Configure the Ethernet interface source address parameters.

        :param ip: IP address of the interface, in dotted-quad
            string notation. Eg. '10.10.10.1'
        :type ip: str

        :param mac: MAC address of the interface.
        :type mac: int

        :param port: UDP source port for packets sent from the interface.
        :type port: int
        """
        # see config_10gbe_core in katcp_wrapper
        if self.core is None:
            self._get_eth_core()
        if self.core is None:
            raise RuntimeError("Couldn't get Ethernet CasperFpga object")
        self.core.configure_core(mac, ip, port, subnet_mask='255.255.254.0')
