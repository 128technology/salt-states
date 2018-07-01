## Reactor state for the DHCP monitor service
##
## This is not necessary for any deployments using 3.2.1 or newer
## It is maintained for legacy purposes
##
{%- set router_name = data['data']['router_name'] %}
{%- set leases = data['data']['leases'] %}
{%- set delete = data['data']['delete'] %}
add branch router to config:
  local.t128_sdwan.update_adjacencies:
    - tgt: '128t_role:conductor'
    - tgt_type: grain
    - arg:
      - {{ router_name }}
      - {{ leases }}
      - {{ delete }}
