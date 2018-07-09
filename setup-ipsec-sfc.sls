## Setup IPSec Service Function Chaining
##
## Pillar Variables:
##
## Name           | Type   | Default Value | Description
## ----------------------------------------------------------------------------------------------------
## ipsec_settings | list   | None          | Details about the interfaces to configure in Linux
##
## ipsec_settings variables:
##
## Name            | Type   | Default Value  | Description
## ----------------------------------------------------------------------------------------------------
## ipsec_namespace | string | '128t-ipsec'   | The name of the namespace for IPSec SFC
## kni_interface   | string | 'sfc-ipsec'    | The name of the KNI interface used for IPSec traffic
## kni_address     | string | '169.254.31.2' | The IP address of the Linux side of the KNI interface
##
{%- set kni_interface_default = 'sfc-ipsec' %}
{%- set kni_address_default = '169.254.31.2' %}
{%- set ipsec_namespace_default = '128t-ipsec' %}
{%- set ipsec_settings = pillar.get('ipsec_settings') %}
Setup ipsec variables:
  file.managed:
    - name: /etc/sysconfig/128T-ipsec
    - mode: 644
    - contents: |
        IPSEC_NAMESPACE={{ ipsec_settings.ipsec_namespace | default(ipsec_namespace_default) }}

Install IPSec packages:
  pkg.installed:
    - name: libreswan

Setup 128t-ipsec service:
  file.managed:
    - name: /etc/systemd/system/128t-ipsec.service
    - source: salt://files/128t-ipsec.service

Setup 128t updown script:
  file.managed:
    - name: /usr/libexec/updown_128t.sh
    - source: salt://files/updown_128t.sh
    - mode: 755

Setup ipsec KNI init script:
  file.managed:
    - name: /etc/128technology/plugins/network-scripts/host/{{ ipsec_settings.kni_interface | default(kni_interface_default) }}/init
    - source: salt://files/ipsec-init
    - mode: 744
    - makedirs: True

Setup ipsec KNI shutdown script:
  file.managed:
    - name: /etc/128technology/plugins/network-scripts/host/{{ ipsec_settings.kni_interface | default(kni_interface_default) }}/shutdown
    - mode: 744
    - makedirs: True
    - source: salt://files/ipsec-shutdown

# We set a grain so that we can easily reference this address later
# Note: This is the LINUX address NOT the 128T address
Set grain for t128_ipsec_local_address:
  grains.present:
    - name: t128_ipsec_local_address
    - value: {{ ipsec_settings.kni_address | default(kni_address_default) }}
