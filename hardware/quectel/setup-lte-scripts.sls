# Activate LTE monitoring for routers with Quectel EC25/EG25
# and enabled LTE and Stellaneo access
/etc/cron.d/t128-fix-lte:
  file.managed:
    - contents:
        - '*/5 * * * * root /usr/sbin/t128-fix-lte.py --quiet'

{% for script in 't128-fix-lte', 't128-get-ccid' %}
/usr/sbin/{{ script }}.py:
  file.managed:
    - mode: 755
    - source: salt://hardware/quectel/files/{{ script }}.py
{% endfor %}
