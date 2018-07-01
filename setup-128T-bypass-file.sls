## Setup file to bypass hardware validation check
##
## This state requires no pillar variables
##

Setup 128T bypass file:
  file.touch:
    - name: /etc/128technology/128tok_startup_bypass
    - makedirs: True
