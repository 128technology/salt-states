## Sets up the DHCP monitoring service which notifies the conductor of new DHCP
## leases or changes in DHCP address leases
##
## This is not necessary for any deployments using 3.2.1 or newer
## It is maintained for legacy purposes
##
## This state requires no pillar variables
##

install dependencies for dhcp monitor:
  pkg.installed:
    - pkgs:
      - python-inotify

Place dhcp monitor python script:
  file.managed:
    - name: /usr/sbin/t128-dhcp-monitor
    - source: salt://files/t128-dhcp-monitor
    - mode: 744
    - user: root
    - group: root

Place dhcp monitor service:
  file.managed:
    - name: /etc/systemd/system/t128-dhcp-monitor.service
    - source: salt://files/t128-dhcp-monitor.service

Start dhcp monitor service:
  service.running:
    - name: t128-dhcp-monitor
    - enable: True
