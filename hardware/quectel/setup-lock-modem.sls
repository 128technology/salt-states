# Install a modem lock service

{% set t128_lock_modem_path = '/usr/sbin/t128-lock-modem.py' %}


t128-lock-modem-script:
  file.managed:
    - name: {{ t128_lock_modem_path }}
    - user: root
    - group: root
    - mode: 755
    - source: salt://hardware/quectel/files/t128-lock-modem.py

systemd-reload-lock-modem-service:
  cmd.run:
   - name: systemctl --system daemon-reload
   - onchanges:
     - file: lock-modem-service

lock-modem-service:
  file.managed:
    - user: root
    - group: root
    - name: /usr/lib/systemd/system/t128-lock-modem.service
    - contents: |
       [Unit]
       Description=A service to lock an UMTS/LTE modem for one hour

       [Service]
       ExecStart={{ t128_lock_modem_path }} 3600
