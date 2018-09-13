{%- set squid_default_namespace = 't128-squid' %}
{%- set squid_default_interface = 'squid' %}
Install packages required for content filtering:
  pkg.installed: 
    - pkgs:
      - squid
      - squidGuard
      - lighttpd

Setup namespace variable:
  file.managed:
    - name: /etc/sysconfig/128T-squid-content-filter
      contents: |
        SQUID_NAMESPACE={{ pillar['squid-namespace'] | default(squid_default_namespace) }}

Setup squid config file:
  file.managed:
    - name: /etc/squid/squid.conf
      user: root
      group: squid
      source: salt://files/squid.conf
 
Setup SquidGuard configuration:
  file.managed:
    - name: /etc/squid/squidGuard.conf
      user: root
      group: squid
      source: salt://files/squidGuard.conf

Setup lighttpd configuration:
  file.managed:
    - name: /etc/lighttpd/lighttpd.conf
      source: salt://files/lighttpd.conf

Setup squid KNI init script:
  file.managed:
    - name: /etc/128technology/plugins/network-scripts/host/{{ pillar['squid-interface'] | default(squid_default_interface) }}/init
      source: salt://files/squid-content-filter-init
      mode: 744
      makedirs: True

Setup 128t-squid service:
  file.managed:
    - name: /etc/systemd/system/128t-squid-content-filter.service
      source: salt://files/128t-squid-content-filter.service

Setup 128t-lighttpd service:
  file.managed:
    - name: /etc/systemd/system/128t-lighttpd-content-filter.service
      source: salt://files/128t-lighttpd-content-filter.service

Setup lighttpd block page:
  file.managed:
    - name: /var/www/lighttpd/block.html
      source: salt://files/block.html

Setup blocked-domains:
  file.managed:
    - name: /var/squidGuard/blacklists/blocked-domains
      makedirs: True
      user: squid
      group: squid
{%- if pillar.get('squid_blocked_domains') %}
      contents_pillar: squid_blocked_domains
{%- else %}
      contents: ''
      contents_newline: False
{%- endif %}

Setup blocked-urls:
  file.managed:
    - name: /var/squidGuard/blacklists/blocked-urls
      makedirs: True
      user: squid
      group: squid
{%- if pillar.get('squid_blocked_urls') %}
      contents_pillar: squid_blocked_urls
{%- else %}
      contents: ''
      contents_newline: False
{%- endif %}

Setup blocked-regex:
  file.managed:
    - name: /var/squidGuard/blacklists/blocked-regex
      makedirs: True
      user: squid
      group: squid
{%- if pillar.get('squid_blocked_regex') %}
      contents_pillar: squid_blocked_regex
{%- else %}
      contents: ''
      contents_newline: False
{%- endif %}

Recreate squid database:
  cmd.run:
    - name: /usr/bin/squidGuard -b -d -C all
      onchanges:
      - file: /var/squidGuard/blacklists/blocked-domains
      - file: /var/squidGuard/blacklists/blocked-urls
      - file: /var/squidGuard/blacklists/blocked-regex

Set ownership of SquidGuard databases:
  cmd.run:
    - name: /usr/bin/chown -R squid:squid /var/squidGuard/blacklists
      onchanges:
      - cmd: Recreate squid database

{%- if salt['service.status']('128t-squid-content-filter') %}
# Only do this if we detected the service is already running
Restarting squid to pickup changes:
  service.running:
    - name: 128t-squid-content-filter
      watch:
      - cmd: Recreate squid database
{%- endif %}
