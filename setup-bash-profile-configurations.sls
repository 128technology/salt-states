## Salt State Responsible for setting up bash profiles for the root and t128 users
## These profiles do the following:
## - Set a command history size of 20000
## - Instruct the command history to ignore/erase duplicate entries
## - Set the command history to include a timestamp
## - Instruct command history to ignore potentially dangerous commands such as reboot and poweroff
##
## This state requires no pillar variables
##

# Manage root bash_profile settings
root bash profile:
  file.managed:
    - name: /root/.bash_profile
    - source: salt://files/root_bash_profile
    - user: root
    - group: root
    - mode: 644

# Manage t128 bash_profile settings
t128 bash profile:
  file.managed:
    - name: /home/t128/.bash_profile
    - source: salt://files/t128_bash_profile
    - user: t128
    - group: t128
    - mode: 644
