## Salt state responsible for setting node IP and restarting salt
## With the node-ip grain set, automated Provisioner on the Conductor knows to begin installation
##
## Pillar Variables
##
## Name    | Type                             | Default Value | Description
## -----------------------------------------------------------------------------------------------------------------------
## node_ip | String (valid IP address format) | '127.0.0.1'   | The value to set for the node_ip grain used by the 128T AP
##

# Set grain based on pillar configuration or default to 127.0.0.1
Set grain to kick off 128T install:
  {%- set node_ip  = pillar.get('node_ip') %}
  {%- set default_node_ip = '127.0.0.1' %}
  grains.present:
    - name: node-ip
    {%- if (node_ip is not none) and not (node_ip | is_ip) %}
      {%- do salt.log.warning("Pillar value node_ip is not an IP address - defined as "+node_ip+" - Using value "+default_node_ip+" instead") %}
    {%- endif %}
    {%- if (node_ip | is_ip) %}
    - value: {{ node_ip }}
    {%- else %}
    - value: {{ default_node_ip }}
    {%- endif %}

Restart salt-minion to kick off installation:
  cmd.run:
    - name: 'salt-call --local service.restart salt-minion'
    - bg: True
    - onchanges:
      - grains: Set grain to kick off 128T install
