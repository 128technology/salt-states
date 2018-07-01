## Configure Firewalld Virtual Zone for 128T Support Access
## contains all 128T public IPs and internal IPs for host-service
## 
## This state will allow SSH access into Linux from the 128T corporate network
## It will also ensure firewalld does not block access from the 128T
## internal kni254 interface used for host-services
##
## This state requires no pillar variables
##

Setup 128T Support firewalld zone:
  firewalld.present:
    - name: t128support
    - services:
      - https
      - ssh
    - sources:
      - 50.226.118.115/32
      - 50.235.163.250/32
      - 50.235.163.251/32
      - 50.235.163.252/32
      - 50.235.163.253/32
      - 50.235.163.254/32
      - 169.254.127.126/32
      - 169.254.255.129/32
      - 172.85.50.34/32
      - 172.85.41.102/32
    - block_icmp:
      - echo-request
  ## Need to run this manually until we migrate to Salt 2018.3.0 which can configure this in firewalld.present
  cmd.run:
    - name: 'firewall-cmd --zone=t128support --add-icmp-block-inversion --permanent'
