## Sets up the Troubleshooting Tool for Conductor Services
## When Conductor Traffic is non-SVR and migrated to a sub-optimal path, there is no way to migrate back
## Just run /usr/local/bin/ConductorConnectionBounce.sh to force a conductor disconnect/reconnect
## Request to put in product:  https://128technology.atlassian.net/browse/I95-19295
##
## This state requires no pillar variables
##

Install Conductor Connection Bounce Script:
  file.managed:
    - name: /usr/local/bin/ConductorConnectionBounce.sh
    - source: salt://files/ConductorConnectionBounce.sh
    - mode: 744
    - user: root
    - group: root
