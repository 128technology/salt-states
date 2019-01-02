## Send 128T alarms via email
## *** NOTE: Ensure npm is intalled for email alerting
## *** A package version compatible with 128T is currently only available on the Engineering repo
## *** This needs to be installed manually for now
##
## Pillar Variables:
##
## Name                       | Type    | Default Value       | Description
## ----------------------------------------------------------------------------------------------------
## t128EmailAlertT128Address  | list    | 'localhost'         | The address to connect to for the 128T API
## t128EmailAlertT128Token    | string  | None                | An authentication token to use with the 128T API
## t128EmailAlertMailHost     | string  | 'localhost'         | The email server to use for sending alerts
## t128EmailAlertMailPort     | integer | 25                  | the TCP port to use when connecting to the mail server
## t128EmailAlertMailSecure   | string  | 'false'             | true/false value for whether to attempt a TLS connection
## t128EmailAlertMailUser     | string  | None                | An optional username to use when authenticating to the mail server
## t128EmailAlertMailPass     | string  | None                | An optional password to use when authenticating to the mail server
## t128EmailAlertMailFrom     | string  | None                | The From address to use when sending e-mails
## t128EmailAlertMailTo       | string  | None                | The To address to use when sending e-mails
## t128EmailSubject           | string  | '128T Alarms'       | The subject line to use for e-mails that contain multiple alarms
## t128EmailAlertMailInterval | integer | 60000               | The time in ms the service will pause to collect additional alarms before
##                            |         |                     | sending an e-mail.  A value of 0 will cause the service to send each alarm
##                            |         |                     | in its own e-mail message
## t128EmailAlertSendBehavior | ENUM    | 'NO_CLEAR_INTERVAL' | Specifies changes in behavior when using ain interval.  Enumeration
##                            |         |                     | detailed below
## t128EmailAlertRouterFilter | list    | [] (empty list)     | When there are names in the list, only include alarms which are from a
##                            |         |                     | router that matches one of these names
##
## t128EmailAlertSendBehavior enumeration:
##
## Option              | Description
## -------------------------------------------------------------------------------------------------------------------------
## ALWAYS_SEND_ALL     | Ensure all alarms observed are sent through e-mail, even if all alarms in the interval were cleared
## SEND_CLEAR_INTERVAL | Only send an e-mail if there were alarms that didn't clear during the interval, but in that case include
##                     | all alarms and clears in the e-mail
## NO_CLEAR_INTERVAL   | Never include alarms which receive a clear during the interval in e-mail alerts
##

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
        // Filter alarms to only include routers in this array (empty means don't filter
        {%- if pillar.t128EmailAlertRouterFilter is defined %}
        exports.routerFilter = [{% for router in pillar.t128EmailAlertRouterFilter %}'{{ router }}'{% if not loop.last%},{% endif %}{% endfor %}]
        {%- else %}
        exports.routerFilter = []
        {%- endif %}


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
