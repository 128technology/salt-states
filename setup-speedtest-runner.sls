{% set t128_speedtest_runner_path = '/usr/sbin/t128-speedtest-runner.pyz' %}
{% set test_interfaces = pillar.get('test-interfaces', {}) %}
{% set schedule_hour_runner = pillar.get('schedule-hour-runner', 23) %}
{% set schedule_minute_runner = pillar.get('schedule-minute-runner', 0) %}
{% set max_delay = pillar.get('max-delay', 0) %}
{% set default_nameservers = ('8.8.8.8', '8.8.4.4') %}

speedtest tool:
  file.managed:
    - user: root
    - group: root
    - mode: 755
    - name: /usr/bin/speedtest
    - source: salt://files/speedtest/speedtest

speedtest runner script:
  file.managed:
    - user: root
    - group: root
    - mode: 755
    - name: {{ t128_speedtest_runner_path }}
    - source: salt://files/speedtest/t128-speedtest-runner.pyz

speedtest runner cronjob:
  file.managed:
    - name: /etc/cron.d/t128-speedtest-runner
    - contents:
        - '{{schedule_minute_runner}} {{schedule_hour_runner}} * * *   root {{ t128_speedtest_runner_path }} --max-delay {{max_delay}}{% for module, interfaces in test_interfaces.items() %}{% for interface in interfaces %} --test {{module}}:{{interface}}{% endfor %}{% endfor %}'

t128-kni-namespace-scripts:
  pkg:
    - installed

{% for interface, details in test_interfaces.get('ookla', {}).items() %}
{% set namespace = 'speed-' ~ interface %}
{% set nameservers = details.get('dns-servers', []) %}
{% if not nameservers %}{% set nameservers = pillar.get('dns-servers', []) %}{% endif %}
{% if not nameservers %}{% set nameservers = default_nameservers %}{% endif %}
create namespace directory for {{interface}}:
  file.directory:
    - name: '/etc/netns/{{ namespace }}'
    - user: root
    - group: root
    - makedirs: True
create namespace resolv.conf for {{interface}}:
  file.managed:
    - name: '/etc/netns/{{ namespace }}/resolv.conf'
    - user: root
    - group: root
    - contents:
{% for nameserver in nameservers %}
      - nameserver {{ nameserver }}
{% endfor %}

create speedtest namespace directory for {{interface}}:
  {% set base_dir = '/etc/128technology/plugins/network-scripts/host/' ~ namespace %}
  file.directory:
    - name: {{ base_dir }}
    - user: root
    - group: root
{% for script in ('init', 'reinit', 'startup', 'shutdown') %}
create speedtest namespace script {{script}} for {{interface}}:
  file.symlink:
    - name: '{{ base_dir }}/{{ script }}'
    - target: /etc/128technology/plugins/network-scripts/default/kni_namespace/{{ script }}
{% endfor %}
{% endfor %}
