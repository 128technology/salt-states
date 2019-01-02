# 128T Salt States #
This repo contains salt states and modules that can be used along with the 128T Automated provizioner for full Zero Touch Provisioning of new 128T rotuers.  These states can alo be used to automate specific Linux functions on existing 128T routers.

## Installation ##
The salt module relies on specific libraries in order to communicate with the conductor via Netconf.  These must be installed as shown below.
```
cd ~
yum -y install git python-ncclient
git clone https://github.com/128technology/python-netconf-utilities.git
pip install python-netconf-utilities/
pip install yinsolidated
```

Specific documentation for the salt state can be found at the beginning of each individual state file.
