## Linux Networking Configuration
## Interface Configurations, Routing Metrics, and Routes
##
## Pillar Variables:
##
## Name                  | Type   | Default Value | Description
## ----------------------------------------------------------------------------------------------------
## configured_interfaces | list   | None          | Details about the interfaces to configure in Linux
## node_ip               | string | None          | Required when using direct_ha in an interface.  We will assume the two HA peers are in a /30.
##
## interface variables description:
##
## Name          | Type    | Default Value | Description
## ----------------------------------------------------------------------------------------------------------
## name          | string  | None          | The name of the interface to manage
## unmanaged     | boolean | False         | If set, we will not attempt to create an ifcg file
## type          | string  | 'eth'         | The interface type.  Valid values are eth, vlan, bridge, and lte
## vlan          | integer | None          | Optional vlan number
## nm_controlled | string  | 'yes'         | Whether the interface should be controlled by NetworkManager
## proto         | string  | 'none'        | The bootproto to use for the interface (dhcp or none)
## address       | string  | None          | Optional IP address for the interface
## prefix        | integer | None          | Optional prefix for the interface
## gateway       | string  | None          | Optional gateway for the interface
## defroute      | string  | 'no'          | Whether to set a default route out this interface
## metric        | integer | None          | Optional metric for the default route out this interface
## zone          | string  | None          | Optional firewalld zone to place the interface in
## apn_name      | string  | None          | The APN to use, valid only when type='lte'
## peerdns       | string  | 'no'          | Whether to allow peerdns, only valid when type='lte'
## direct_ha     | boolean | None          | If set this interface is part of 
## dns           | list    | None          | Optional list of DNS servers to set on interface
## routes        | list    | None          | Optional list of static routes for an interface
##
## route variables:
##
## Name    | Type    | Default Value | Description
## --------------------------------------------------------------------------------
## network | string  | None          | Network address for the static route
## prefix  | integer | None          | Optional prefix for the static route
## gateway | string  | None          | Optional gateway to use for the static route
## metric  | integer | None          | Optional metric to use for the static route
##
## Pillar example:
##
## configured_interfaces:
##   - name: lo:0
##     proto: none
##     address: '169.254.255.255'
##     prefix: 32
##     defroute: no
##     dns:
##       - 8.8.8.8
##       - 8.8.4.4
##   - name: enp0s20f0
##     proto: none
##     address: '172.19.160.164'
##     prefix: 29
##     gateway: '172.19.160.161'
##     defroute: yes
##     metric: 250
##   - name: enp0s20f1
##     proto: none
##     defroute: no
##   - name: enp0s20f2
##     proto: none
##     defroute: no
##   - name: enp0s20f3
##     proto: none
##     defroute: no
##   - name: kni20
##     unmanaged: True
##     routes:
##       - name: 'Default'
##         network: '0.0.0.0'
##         prefix: 0
##         gateway: '169.254.1.1'
##         metric: 200
##

## Set Direct HA Teamed Interface to use for Network Teaming
{%- set direct_ha_team = 'team128' %}
{%- set direct_ha_vlan = '128' %}

{%- set configured_interfaces = pillar.get('configured_interfaces') %}
Set management interface metric:
  file.managed:
    - name: /etc/NetworkManager/conf.d/default-metrics.conf
    - contents: |
{%- for interface in configured_interfaces %}
{%- if interface.direct_ha is defined and interface.metric is defined %}
        [connection-{{ direct_ha_team }}]
        match-device={{ direct_ha_team }}
        ipv4.route-metric={{ interface.metric }}
{%- elif interface.metric is defined %}
        [connection-{{ interface.name }}]
        match-device={{ interface.name }}
        ipv4.route-metric={{ interface.metric }}
{%- endif %}
{%- endfor %}

Restart Network Manager for Default Routing Metrics:
  service.running:
    - name: NetworkManager
    - watch:
      - file: /etc/NetworkManager/conf.d/default-metrics.conf

{%- for interface in configured_interfaces %}
{%- if interface.direct_ha is defined %}
## No support for interface type "TeamPort" in network.managed.  Manual file manipulation required
ifcfg for {{ interface.name }}:
  file.managed:
    - name: /etc/sysconfig/network-scripts/ifcfg-{{ interface.name }}
    - contents: |
        DEVICE={{ interface.name }}
        NAME={{ interface.name }}
        ONBOOT=yes
        BOOTPROTO=none
        TYPE=TeamPort
        TEAM_MASTER={{ direct_ha_team }}
        TEAM_PORT_CONFIG='{"prio": {{ 5000 - loop.index0 }}}'  
## Probably a better way to do this is setting up another sls file to be called, but this works for now
ifcfg for {{ direct_ha_team }} for {{ interface.name }}:
  {%- set node_ip = pillar.get('node_ip') %}
  {%- set last_octet = ( node_ip.split('.')[3] | int ) %}
  file.managed:
    - name: /etc/sysconfig/network-scripts/ifcfg-{{ direct_ha_team }}
    - contents: |
        DEVICE={{ direct_ha_team  }}
        NAME={{ direct_ha_team }}
        ONBOOT=yes
        BOOTPROTO=none
        TYPE=Team
        IPADDR={{ node_ip }}
        PREFIX=30
        {%- if last_octet is even %}
        GATEWAY={{ node_ip | regex_replace('(^.*\.).*$', '\\1') }}{{ last_octet | int - 1 }}
        {%- else %}
        GATEWAY={{ node_ip | regex_replace('(^.*\.).*$', '\\1') }}{{ last_octet | int + 1 }}
        {%- endif %}
        TEAM_CONFIG='{"runner": {"name": "activebackup", "min_ports": 0}, "link_watch": {"name": "ethtool"}}'
        ZONE=trusted
ifcfg for {{ direct_ha_team }}.{{ direct_ha_vlan }} for {{ interface.name }}:
  file.managed:
    - name: /etc/sysconfig/network-scripts/ifcfg-{{ direct_ha_team }}.{{ direct_ha_vlan }}
    - contents: |
        DEVICE={{ direct_ha_team  }}.{{ direct_ha_vlan }}
        NAME={{ direct_ha_team }}.{{direct_ha_vlan }}
        ONBOOT=yes
        BOOTPROTO=none
        VLAN=yes
{%- elif interface.unmanaged is not defined %}
{%- if not (salt['file.search']('/etc/sysconfig/network-scripts/ifcfg-' + interface.name,'^NM_CONTROLLED=no$',ignore_if_missing=True) or salt['file.search']('/etc/sysconfig/network-scripts/ifcfg-' + interface.name,'^NM_CONTROLLED="no"$',ignore_if_missing=True)) %}
ifcfg for {{ interface.name }}:
  ## No support for interface type lte in network.managed.  Manual file manipulation required
  {%- if interface.type is defined and interface.type == 'lte' %}
  file.managed:
    - name: /etc/sysconfig/network-scripts/ifcfg-{{ interface.name }}
    - contents: |  
        DEVICE={{ interface.name }}
        NAME={{ interface.name }}
        ONBOOT=yes
        BOOTPROTO={{ interface.proto or "none" }}
        TYPE=lte
        {%- if interface.apn_name is defined %}
        APN_NAME={{ interface.apn_name }}
        {%- endif %}
        {%- if interface.address is defined %}
        IPADDR={{ interface.address }}
        {%- endif %}
        {%- if interface.prefix is defined %}
        PREFIX={{ interface.prefix }}
        {%- endif %}
        {%- if interface.gateway is defined %}
        GATEWAY={{ interface.gateway }}
        {%- endif %}
        {%- if interface.defroute is defined %}
        DEFROUTE={{ interface.defroute }}
        {%- endif %}
        {%- if interface.peerdns is defined %}
        PEERDNS={{ interface.peerdns }}
        {%- else %}
        PEERDNS=no
        {%- endif %}
  {%- else %}
  network.managed:
    - name: {{ interface.name }}
    - enabled: True
  {%- if interface.type is defined %}
    - type: {{ interface.type }}
  {%- elif interface.vlan is defined %}
    - type: vlan
  {%- else %}
    - type: eth
  {%- endif %}
  {%- if interface.nm_controlled is defined %}
    - nm_controlled: {{ interface.nm_controlled }}
  {%- else %}
    - nm_controlled: yes
  {%- endif %}
    - nickname: {{ interface.name }}
  {%- if interface.proto is defined %}
    - proto: {{ interface.proto }}
  {%- else %}
    - proto: none
  {%- endif %}
  {%- if interface.vlan is defined %}
    - vlan: {{ interface.vlan }}
  {%- endif %}
  {%- if interface.address is defined %}
    - ipaddr: {{ interface.address }}
  {%- endif %}
  {%- if interface.prefix is defined %}
    - prefix: {{ interface.prefix }}
  {%- endif %}
  {%- if interface.gateway is defined %}
    - gateway: {{ interface.gateway }}
  {%- endif %}
  {%- if interface.defroute is defined %}
    - defroute: {{ interface.defroute }}
  {%- else %}
    - defroute: no
  {%- endif %}
  {%- if interface.dns is defined %}
    - dns: {{ interface.dns }}
  {%- endif %}
  {%- if interface.zone is defined %}
    - zone: {{ interface.zone }}
  {%- endif %}
  {%- endif %}
{%- endif %}
{%- endif %}
{%- endfor %}

{%- for interface in configured_interfaces %}
{%- if interface.routes is defined %}
routes for {{ interface.name }}:
  file.managed:
    - name: /etc/sysconfig/network-scripts/route-{{ interface.name }}
    - contents: |
    {%- for route in interface.routes %}
    {%- if route.name %}
        # {{route.name}}
    {%- endif %}
        {{route.network}}{% if route.prefix is defined %}/{{route.prefix}}{% endif %}{% if route.gateway is defined %} via {{route.gateway}}{% endif %} dev {{ interface.name }}{% if route.metric is defined %} metric {{ route.metric }}{% endif %}
    {%- endfor %}
{%- endif %}
{%- endfor %}

