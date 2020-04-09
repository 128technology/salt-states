# Install t128-show-speedtest

speedtest repo:
  file.managed:
    - user: root
    - group: root
    - mode: 644
    - name: /etc/yum.repos.d/bintray-ookla-rhel.repo
    - source: https://bintray.com/ookla/rhel/rpm
    - skip_verify: True

speedtest:
  pkg:
    - installed
