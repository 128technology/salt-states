# -*- coding: utf-8 -*-
'''
:maintainer: Lane Shields (lshields@128technology.com)
'''

from __future__ import absolute_import
import logging
import os
import jinja2
import jinja2.exceptions

# Import salt libs
import salt.utils
from salt._compat import ipaddress

LOG = logging.getLogger(__name__)

__virtualname__ = 'network_functions'

def __virtual__():
  return True

def cidr_to_ipv4_netmask(cidr_bits):
    '''
    Returns an IPv4 netmask
    '''
    try:
        cidr_bits = int(cidr_bits)
        if not 1 <= cidr_bits <= 32:
            return ''
    except ValueError:
        return ''

    netmask = ''
    for idx in range(4):
        if idx:
            netmask += '.'
        if cidr_bits >= 8:
            netmask += '255'
            cidr_bits -= 8
        else:
            netmask += '{0:d}'.format(256 - (2 ** (8 - cidr_bits)))
            cidr_bits = 0
    return netmask

def get_network_address(ipaddr, netmask):
    '''
    Return the address of the network
    '''
    net = ipaddress.ip_network('{0}/{1}'.format(ipaddr, netmask), strict=False)
    return str(net.network_address)

def get_address_as_decimal(addr):
    '''
    Return the decimal representation of an IP address

    This function is primarily used to generate a unique mark to identify traffic
    for a particular IPSec tunnel using the remote address.
    '''
    return int(ipaddress.ip_address(addr))
