{% set t128_speedtest_collector_path = '/usr/sbin/t128-speedtest-collector.pyz' %}
{% set schedule_hour_runner = pillar.get('schedule-hour-runner', 23) %}
{% set schedule_minute_runner = pillar.get('schedule-minute-runner', 0) %}
{% set max_delay = pillar.get('max-delay', 0) %}
{% set max_testtime = pillar.get('max-test-time', 300) %}
{% set max_wait = max_delay + max_testtime %}

{% set max_wait_hours = (max_wait / 3600)|int %}
{% set max_wait_minutes = ((max_wait % 3600) / 60)|int %}
{% set max_wait_minutes_carryover = ((schedule_minute_runner + max_wait_minutes) / 60)|int %}
{% set schedule_hour_collector = ((schedule_hour_runner + max_wait_hours + max_wait_minutes_carryover) % 24)|int %}
{% set schedule_minute_collector = ((schedule_minute_runner + max_wait_minutes) % 60)|int %}

speedtest collector script:
  file.managed:
    - user: root
    - group: root
    - mode: 755
    - name: {{ t128_speedtest_collector_path }}
    - source: salt://files/speedtest/t128-speedtest-collector.pyz

speedtest collector cronjob:
  file.managed:
    - name: /etc/cron.d/t128-speedtest-collector
    - contents:
        - '{{ schedule_hour_collector }} {{ schedule_minute_collector }} * * *   root {{ t128_speedtest_collector_path }}'
