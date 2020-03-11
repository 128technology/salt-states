## Send 128T alarms via email - this variant supports HA
##
## Pillar Variables:
##
## Name                         | Type    | Default Value                        | Description
## ---------------------------------------------------------------------------------------------------------------------------
## t128EmailAlertT128Address    | list    | 'localhost'                          | The address to connect to for the 128T API
## t128EmailAlertT128Token      | string  | None                                 | An authentication token to use with the 128T API
## t128EmailAlertMailTemplate   | string  | '/etc/t128-email-alarms-ha.template' | The path to the email jinja2 template
## t128EmailAlertMailHost       | string  | 'localhost'                          | The email server to use for sending alerts
## t128EmailAlertMailPort       | integer | 25                                   | the TCP port to use when connecting to the mail server
## t128EmailAlertMailSecure     | string  | 'false'                              | true/false value for whether to attempt a TLS connection
## t128EmailAlertMailUser       | string  | None                                 | An optional username to use when authenticating to the mail server
## t128EmailAlertMailPass       | string  | None                                 | An optional password to use when authenticating to the mail server
## t128EmailAlertMailFrom       | string  | 't128-email-alarms'                  | The From address to use when sending e-mails
## t128EmailAlertMailRecipients | dict    | None                                 | A dictonary with mapping of router names and recipients. 'default' is used for routers which are mentioned.
## t128EmailAlertMailInterval   | integer | 60                                   | The time in seconds the service will pause to collect additional alarms before
##                              |         |                                      | sending an e-mail.  A value of 0 will cause the service to send each alarm
##                              |         |                                      | in its own e-mail message
##

{% set t128_email_alarms_config_path = '/etc/t128-email-alarms-ha.config' %}
{% set t128_email_alarms_script_path = '/usr/sbin/t128-email-alarms-ha.py' %}

Setup python script for email alerting (HA):
  file.managed:
    - name: {{ t128_email_alarms_script_path }}
    - source: salt://files/t128-email-alarms-ha.py
    - mode: 755

Setup template file for email alerting (HA):
  file.managed:
    - name: /etc/t128-email-alarms-ha.template
    - source: salt://files/t128-email-alarms-ha.template
    - mode: 644


Setup configuration options for email alerting (HA):
  file.managed:
    - name: {{ t128_email_alarms_config_path }}
    - contents: |
        {
            "api_host": "{{ pillar['t128EmailAlertT128Address'] | default('localhost') }}",
            "api_key": "{{ pillar['t128EmailAlertT128Token'] }}",
            "mail_interval": {{ pillar['t128EmailAlertMailInterval'] | default(60) }},
            "mail_from": "{{ pillar['t128EmailAlertMailInterval'] | default('t128-email-alarms') }}",
            "mail_recipients":
        {%- if pillar['t128EmailAlertMailRecipients'] %}
            {{ pillar['t128EmailAlertMailRecipients']|json }}
        {%- else %}
                {"default": "root"}
        {%- endif %},
            "not_send_cleared_alarms": true,
            "send_digest_mails": false,
            "template": "{{ pillar['t128EmailAlertMailTemplate'] | default('/etc/t128-email-alarms-ha.template') }}"
        }


Setup systemd service for email alerting (HA):
  file.managed:
    - name: /etc/systemd/system/t128-email-alarms-ha.service
    - contents: |
        [Unit]
        Description=Service to monitor for 128T alarms on (HA) condcutor and send them via e-mail
        After=128T.service

        [Service]
        ExecStart={{ t128_email_alarms_script_path }} -c {{ t128_email_alarms_config_path }}
        Restart=on-failure
        RestartSec=5

        [Install]
        WantedBy=multi-user.target


Systemd reload services:
  cmd.run:
   - name: systemctl --system daemon-reload
   - onchanges:
     - file: /etc/systemd/system/t128-email-alarms-ha.service

Start and enable email alerting service (HA):
  service.running:
    - name: t128-email-alarms-ha
    - enable: True
    - watch:
      - file: {{ t128_email_alarms_config_path }}
