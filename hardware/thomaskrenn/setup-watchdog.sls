# Install a watchdog on well-known hardware platforms

# Check whether running kernel is supported
{% if grains['kernelrelease'] in ('3.10.0-862.14.4.el7.x86_64', '3.10.0-1062.4.1.el7.x86_64') %}

    # Thomas Krenn LES compact 4L v1
    {% if grains['productname'] == 'YL-J3160L4' %}
        {%- set watchdog_driver = 'it87_wdt' %}

        /etc/modprobe.d/{{ watchdog_driver }}.conf:
          file.managed:
            - user: root
            - group: root
            - mode: 644
            - contents: options {{ watchdog_driver }} nogameport=1
    {% endif %}

    # Thomas Krenn LES compact 4L v2
    {% if grains['productname'] == 'NU941' %}
        {%- set watchdog_driver = 'f71808e_wdt' %}
    {% endif %}

    # All supported platforms
    {% if grains['productname'] in ('YL-J3160L4', 'NU941') %}
        /lib/modules/{{ grains['kernelrelease'] }}/kernel/drivers/watchdog/{{ watchdog_driver }}.ko.xz:
          file.managed:
            - user: root
            - group: root
            - mode: 644
            - source: salt://hardware/thomaskrenn/files/{{ grains['kernelrelease'] }}/{{ watchdog_driver }}.ko.xz

        /etc/modules-load.d/watchdog-modules.conf:
          file.managed:
            - user: root
            - group: root
            - mode: 644
            - contents: {{ watchdog_driver }}

        load_watchdog_kmod:
          kmod.present:
            - name: {{ watchdog_driver }}

        systemd-reload-watchdog:
          cmd.run:
            - name: systemctl --system daemon-reload
            - onchanges:
              - file: watchdog_invoker.override
              - file: watchdog_multi.override

        watchdog_invoker.override:
          file.managed:
            - user: root
            - group: root
            - makedirs: True
            - name: /etc/systemd/system/watchdog_invoker.service.d/override.conf
            - contents:
              - '[Service]'
              - ExecStartPre=/usr/bin/ln -sf watchdog /dev/watchdog0

        watchdog_invoker:
          service.running:
            - enable: True
            - full_restart: True
            - watch:
              - file: /lib/modules/{{ grains['kernelrelease'] }}/kernel/drivers/watchdog/{{ watchdog_driver }}.ko.xz

        watchdog:
          service.disabled: []

        watchdog_multi.override:
          file.managed:
            - user: root
            - group: root
            - makedirs: True
            - name: /etc/systemd/system/watchdog_multi@.service.d/override.conf
            - contents:
              - '[Service]'
              - Restart=always
    {% endif %}
{% endif %}
