## Configure Firewalld Zone for inbound access for 128T related protocols
## contains all ports and protocols that can be used for management, monitoring, HA, etc.
##
## This state requires no pillar variables

## 128T communication is needed for inbound to the conductor and between HA Peers
Setup 128T communication service:
  firewalld.service:
    - name: '128t-comms'
    - ports:
      - 930/tcp

## Salt Master is needed for inbound to the conductor
Setup Salt Master service:
  firewalld.service:
    - name: 'salt-master'
    - ports:
      - 4505/tcp
      - 4506/tcp

## Zookeeper is needed between HA Peers.  Should eventually use just port 930, but additional ports needed for now
Setup Zookeeper service:
  firewalld.service:
    - name: 'zookeeper'
    - ports:
      - 2222/tcp
      - 2223/tcp  

## NetConf is needed for direct NetConf calls.  Often used by Robot and other test suites
Setup NetConf service:
  firewalld.service:
    - name: netconf
    - ports:
      - 830/tcp

Setup 128T firewalld zone:
  firewalld.present:
    - name: t128
    - services:
      - https
      - ssh
      - 128t-comms
      - salt-master
      - netconf
      - zookeeper

  ## Need to run this manually until we migrate to Salt 2018.3.0 which can configure this in firewalld.present
  cmd.run:
    - name: 'firewall-cmd --zone=t128 --set-target=DROP --permanent'
