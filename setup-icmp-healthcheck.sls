# Sets up script and cronjob to periodically check for available
# conductor/internet connection and restart 128T/reboot in case of issues

{% set t128_icmp_healthcheck_path = '/usr/sbin/t128-icmp-healthcheck.py' %}

t128-icmp-healthcheck-crontab:
  file.managed:
    - name: /etc/cron.d/t128-icmp-healthcheck
    - contents:
        - '*/5 * * * * root {{ t128_icmp_healthcheck_path }}'

t128-icmp-healthcheck-script:
  file.managed:
    - name: {{ t128_icmp_healthcheck_path }}
    - mode: 755
    - source: salt://files/t128-icmp-healthcheck.py
