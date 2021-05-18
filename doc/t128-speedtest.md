# t128-speedtest

This application allows to run speedtest measurements across a network of 128T/SSR routers and to collect the results in order to display maximum bandwidth values on the conductor.

There are two parts:

* t128-speedtest-runner is executed on every 128T/SSR router, which has interfaces that should be tested.
* t128-speedtest-collector is executed on the conductor after all runners are finished to collect the test results and to update the router descriptions.

It is recommended to schedule the execution of these scripts by cron. Therefore, crontabs should be managed through salt states.

## Configuration
### Network Namespaces
For every interface that should be tested by Ookla Speedtest the 128T router needs to have a dedicated KNI host interface and a network namespace, which allows inidividual routing of the `speedtest` instances. These instances run on the router's Linux OS and - without network namespaces - would share the same (default) route. The [kni namespace scripts](https://docs.128technology.com/docs/plugin_kni_namespace_scripts) are automatically installed based on the `test-interfaces` as defined in the salt pillar below. 

Additionally, there has to be a tenant and services per test interface. The service routes for each service needs a "Service Agent" next-hop towards the test interface (wanX, lteX, etc.)

### 128T Router Configuration
As described above there are configuration entities needed per test interface:

* a tenant which identifies the speedtest instance
* a corresponding service with an appropriate service-address (e.g. `0.0.0.0/0`)
* a service-route to route the speedtest traffic via the test interface
* a service to match DNS traffic over the test interface
* a service-route for DNS traffic

This is a sample config snippet for testing the wan1 interface:

```
config

    authority
	
        service  speedtest-wan1
            name                     speedtest-wan1

            address                  0.0.0.0/0
 
             access-policy            speed-wan1
                source  speed-wan1
            exit
            share-service-routes     false
        exit
        
        service  speedtest-wan1-dns
            name                     speedtest-wan1-dns
            application-type         dns-proxy
            transport                udp
                protocol    udp

                port-range  53
                    start-port  53
                    end-port    53
                exit
            exit
            address                  169.254.127.126/32
 
             access-policy            speed-wan1
                source  speed-wan1
            exit
            share-service-routes     false
        exit

        router  sample-branch-router1
            name  sample-branch-router1

            node  node1
                name              node1

                device-interface  speed-wan1
                    name               speed-wan1
                    type               host
                    network-namespace  speed-wan1

                    network-interface  speed-wan1
                        name               speed-wan1
                        default-route      true
                        tenant             speed-wan1

                        management-vector
                            name      speed-wan1
                            priority  123
                        exit

                        address            169.254.123.1
                            ip-address     169.254.123.1
                            prefix-length  30
                            gateway        169.254.123.2
                        exit
                    exit
                exit
            exit
            
            dns-config  static
                mode     static
                address  8.8.8.8
            exit

            service-route  speedtest-wan1
                name          speedtest-wan1
                service-name  speedtest-wan1

                next-hop      node1 wan1
                    node-name  node1
                    interface  wan1
                exit
            exit
            
            service-route  speedtest-wan1-dns
                name          speedtest-wan1-dns
                service-name  speedtest-wan1-dns

                next-hop      node1 wan1
                    node-name  node1
                    interface  wan1
                    target-address  8.8.8.8
                exit
            exit
            
        exit
    exit
exit
```

### Salt Pillar
The global test interface configuration is done by salt pillars as shown below:

```
$ sudo mkdir /srv/pillar
$ sudo vi /srv/pillar/top.sls
base:
  '*':
    - speedtest
$ sudo vi /srv/pillar/speedtest.sls
test-interfaces:
  ookla:
    - wan1
    - lte1
  snmp:
    - mpls1
# start hour and minute for the runner cronjob (times are typically in UTC)
schedule-hour-runner: 23
schedule-minute-runner: 0
max-delay: 14400   # 4 hours
```

## Installation

According to the design of the t128-speedtest application there are two salt state files to address the two roles:

* For the routers: `setup-speedtest-runner.sls`
* For the conductor: `setup-speedtest-collector.sls`

In case of an HA conductor the salt state shall be installed on the **primary** node only.

There are two ways to trigger the .sls files - either manually on each node (using `salt-call` or `t128-salt` on the conductor) or managing the salt states through the global salt file: `/srv/salt/top.sls`:

### Manual Trigger
This can be performed on the conductor (salt master):

```
$ sudo t128-salt '*router*' state.apply setup-speedtest-runner
$ sudo t128-salt '*conductor*' state.apply setup-speedtest-collector
```
or (on the target host):

```
$ sudo salt-call state.apply setup-speedtest-runner
$ sudo salt-call state.apply setup-speedtest-collector
```

The global salt file automates the installation of the speedtest on new routers, which is the **preferred method**.

## Build .pyz Files
The .pyz files are [compressed python archives](https://docs.python.org/3/library/zipapp.html) (similar to .jar files in the Java universe) which allow to execute the main python script inside the archive, but at the same time split up modules into separate files/folders.

The source code at [salt-states/files/speedtest](https://github.com/128technology/salt-states/blob/master/files/speedtest) comes with a shell script `create_pyz.bash` that create the two archives from the sources files.

```
$ cd salt-states/files/speedtest
$ bash create_pyz.bash
```

Done.
