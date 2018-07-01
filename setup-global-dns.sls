## Makes DNS Settings Global instead of on a per interface basis
##
## Pillar Variables
##
## Name | Type                             | Default Value | Description
## ------------------------------------------------------------------------------
## dns1 | String (valid IP address format) | '8.8.8.8'     | Primary DNS server
## dns2 | String (valid IP address format) | '8.8.4.4'     | Secondary DNS server
##

Global DNS Settings File in Network Manager:
{%- set dns1 = pillar.get('dns1') %}
{%- set dns2 = pillar.get('dns2') %}

{%- set defaultdns1 = '8.8.8.8' %}
{%- set defaultdns2 = '8.8.4.4' %}

###
{%- if (dns1 is not none) and not (dns1 | is_ip) %}
  {%- do salt.log.warning("Pillar value dns1 is not an IP address - defined as "+dns1+" - Using value "+defaultdns2+" instead") %}
{%- endif %}
{%- if (dns2 is not none) and not (dns2 | is_ip) %}
  {%- do salt.log.warning("Pillar value dns2 is not an IP address - defined as "+dns2+" - Using value "+defaultdns2+" instead") %}
{%- endif %}

  file.managed:
    - name: /etc/NetworkManager/conf.d/global-dns.conf
    - user: root
    - group: root
    - mode: 644
    - contents: |
        [global-dns]
        enable=yes

        [global-dns-domain-*]
        
        {%- if (dns1 | is_ip) and (dns2 | is_ip) %}
        servers={{ dns1 }},{{ dns2 }}
        {%- else %}
        servers={{ defaultdns1 }},{{ defaultdns2 }}
        {%- endif %}

Restart Network Manager after Global DNS Settings Changed:
  service.running:
    - name: NetworkManager
    - watch:
      - file: /etc/NetworkManager/conf.d/global-dns.conf
