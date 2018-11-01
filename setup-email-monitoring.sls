#Ensure npm is intalled for email alerting
# This file is only on the Engineering repo, this needs to be done manually for now

Setup nodejs file for email alerting:
  file.managed:
    - name: /root/t128-email-alarms/t128-email-alarms.js
    - source: salt://files/t128-email-alarms.js
    - makedirs: True

Setup configuration options for email alerting:
  file.managed:
    - name: /root/t128-email-alarms/config.js
    - contents: |
        exports.t128Address = '{{ pillar['t128EmailAlertT128Address'] | default('localhost') }}'
        exports.authToken   = '{{ pillar['t128EmailAlertT128Token'] }}'
        
        exports.mailHost    = '{{ pillar['t128EmailAlertMailHost'] | default('localhost') }}'
        exports.mailPort    = {{ pillar['t128EmailAlertMailPort'] | default(25) }}
        exports.mailSecure  = {{ pillar['t128EmailAlertMailSecure'] | default('false') }}
        {%- if pillar.t128EmailAlertMailUser is defined %}
        exports.mailUser    = '{{ pillar['t128EmailAlertMailUser'] }}'
        {%- endif %}
        {%- if pillar.t128EmailAlertMailPass is defined %}
        exports.mailPass    = '{{ pillar['t128EmailAlertMailPass'] }}'
        {%- endif %}
        exports.mailFrom    = '{{ pillar['t128EmailAlertMailFrom'] }}'
        exports.mailTo      = '{{ pillar['t128EmailAlertMailTo'] }}'
        exports.mailSubject = '{{ pillar['t128EmailAlertMailSubject'] | default('128T Alarms') }}'
        
        exports.mailInterval = {{ pillar['t128EmailAlertMailInterval'] | default('60000') }}
        
        // If this is set to ALWAYS_SEND_ALL we will send all alarms from the interval
        // even if they were cleared before the interval ended
        // If this is set to SEND_CLEAR_INTERVAL we will only send an e-mail when there was an alarm
        // which did not clear during the interval, but we will include all alarms and clears
        // If this is set to NO_CLEAR_INTERVAL we will never send alarms which cleared during the
        // active interval
        exports.sendBehaviorEnum = '{{ pillar['t128EmailAlertSendBehavior'] | default('NO_CLEAR_INTERVAL') }}'

Install npm packages required for email alerting:
  npm.installed:
    - dir: /root/t128-email-alarms
    - pkgs:
      - eventsource
      - nodemailer

Setup systemd service for email alerting:
  file.managed:
    - name: /etc/systemd/system/t128-email-alarms.service
    - source: salt://files/t128-email-alarms.service

Start and enable email alerting service:
  service.running:
    - name: t128-email-alarms
    - enable: True
    - watch:
      - file: /root/t128-email-alarms/config.js
