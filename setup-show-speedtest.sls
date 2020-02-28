# Install t128-show-speedtest

speedtest-cli:
  file.managed:
    - user: root
    - group: root
    - mode: 755
    - name: /usr/bin/speedtest-cli
    - source: salt://files/speedtest-cli
