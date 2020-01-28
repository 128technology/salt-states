# Install a safety_net service

systemd-reload-safety-net-service:
  cmd.run:
   - name: systemctl --system daemon-reload
   - onchanges:
     - file: safety-net-service

safety-net-service:
  file.managed:
    - user: root
    - group: root
    - name: /usr/lib/systemd/system/safety_net.service
    - contents: |
       [Unit]
       Description=A service to reboot its host automatically one hour after start.

       [Service]
       ExecStart=/bin/sh -c 'sleep 3600; /usr/sbin/reboot'
