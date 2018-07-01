## Salt State File responsible for handling DHCP Server
## Currently the 128T router doesn't contain this capability in product
## This will provide all necessary functions to allow for interaction
## With Linux dhcpd and KNI Bridged Interfaces
##
## Pillar Variables
##
## Name                  | Type   | Default Value | Description
## ----------------------------------------------------------------------------------------------------
## configured_interfaces | list   | None          | Details about the interfaces to configure in Linux
##
## interface variables description:
##
## Name          | Type    | Default value | Description
## ------------------------------------------------------------------------------------------------------------
## name          | string  | None          | The name of the target-interface in the kni bridge
## dhcp_listener | string  | None          | IP address to use for the DHCP server process
## dhcp_mask     | integer | None          | Prefix used for the subnet
## dhcp_bridge   | list    | None          | Optional list of Linux interfaces to attach to the bridge
## dhcp_router   | string  | None          | The address offered by the DHCP server as the router on this subnet
## dhcp_range1   | string  | None          | The start of the DHCP lease range for this subnet
## dhcp_range2   | string  | None          | The end of the DHCP lease range for this subnet
##
## Pillar example:
##
## configured_interfaces:
##   - name: eth1
##     dhcp_router:    '192.168.1.1'
##     dhcp_listener:  '192.168.1.254'
##     dhcp_range1:    '192.168.1.100'
##     dhcp_range2:    '192.168.1.200'
##     dhcp_mask:      '24'
##   - name: eth2
##     dhcp_router:    '192.168.2.1'
##     dhcp_listener:  '192.168.2.254'
##     dhcp_range1:    '192.168.2.100'
##     dhcp_range2:    '192.168.2.200'
##     dhcp_mask:      '24'
##     dhcp_bridge:
##       - eth3
##       - eth4
##
## These variables should be combined into the same configured_interfaces dictionary 
## used with the setup-linux-networking state
##

{%- set configured_interfaces = pillar.get('configured_interfaces') %}
{%- if (configured_interfaces is defined) and configured_interfaces %}
Setup DHCP Listener firewalld zone:
  firewalld.present:
    - name: DHCPD
    - services:
      - dhcp

Set DHCP Variables to be picked up by init scripts:
  file.managed:
    - name: /etc/sysconfig/128T-dhcp-server-setup-vars
    - user: root
    - group: root
    - mode: 644
    - contents: |
    {%- for interface in configured_interfaces %}
    {%- if interface.dhcp_listener is defined and interface.dhcp_mask is defined %}
        DHCP_LISTENER_{{ interface.name }}={{ interface.dhcp_listener }}
        DHCP_MASK_{{ interface.name }}={{ interface.dhcp_mask }}
      {%- if (interface.dhcp_bridge is defined) and interface.dhcp_bridge  %}
        {%- for bridge_int in interface.dhcp_bridge %}
        BRIDGE_INTERFACES_{{ interface.name }}[{{ loop.index0 }}]={{ bridge_int }}
        {%- endfor %}
      {%- endif %}
    {%- endif %}
    {%- endfor %}

{%- for interface in configured_interfaces %} 
{%- if interface.dhcp_listener is defined and interface.dhcp_mask is defined %}
Setup DHCP Init Files for target interface {{ interface.name }}:
  file.managed:
    - name: /etc/128technology/plugins/network-scripts/bridged/{{ interface.name }}/init
    - source: salt://files/kni_bridged_dhcp.init
    - user: root
    - group: root
    - mode: 744
    - makedirs: True
{%- endif %}
{%- endfor %}

Configure DHCPD Configuration File:
  pkg.installed:
    - name: dhcp
  file.managed:
    - name: /etc/dhcp/dhcpd.conf
    - user: root
    - group: root
    - mode: 644
    - contents: |
        #
        # DHCP Server Configuration file.
        #   see /usr/share/doc/dhcp*/dhcpd.conf.example
        #   see dhcpd.conf(5) man page
        #

        #Global Options
        default-lease-time 300;
        max-lease-time 300;
        option domain-name-servers 8.8.8.8, 8.8.4.4;

{%- for interface in configured_interfaces %}
{%- if interface.dhcp_listener is defined and interface.dhcp_mask is defined
 and interface.dhcp_router is defined
 and interface.dhcp_range1 is defined and interface.dhcp_range2 is defined %}
        subnet {{ salt['network_functions.get_network_address'](interface.dhcp_listener,interface.dhcp_mask) }} netmask {{ salt['network_functions.cidr_to_ipv4_netmask'](interface.dhcp_mask) }} {
          range dynamic-bootp {{ interface.dhcp_range1 }} {{ interface.dhcp_range2 }};
          option routers {{ interface.dhcp_router }};
        }
{%- endif %}
{%- endfor %}
{%- endif %}
