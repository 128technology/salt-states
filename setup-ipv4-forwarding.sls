## For some situations, IP Forwarding may be required for outside-128T functionality
## Example 1:  Port-Forwarding via Linux
## Example 2:  Traffic forwarding in HA Pairs when 1 unit has 128T Disabled
##
## This state requires no pillar variables

# Enable IP Forwarding to ensure the HA nodes can route to conductor through eachother
Enable IPv4 Forwarding:
  sysctl:
    - name: net.ipv4.ip_forward
    - present
    - value: 1
