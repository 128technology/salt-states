## Set Timezone of System
## Default to America/New_York
##
## Pillar variables
##
## Name     | Type   | Default Value      | Description
## --------------------------------------------------------------------------------
## timezone | string | 'America/New_York' | The correctly formatted timezone to use
##

Set OS Timezone:
  timezone.system:
    - name: {{ salt['pillar.get']("timezone", "America/New_York") }}
    - utc: True
