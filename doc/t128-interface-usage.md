# t128-interface-usage

This application provides a web application to inspect the interface usages (aggregated received/sent bytes) for all routers in a Session Smart Routing deployment.

The application consists of three parts:

* a python script called `t128-interface-usage.pyz` that collects interface statistics and creates a json file with aggregated data. A shell script called `t128-interface-usage-collector.sh` helps to pass the correct parameters to the pyz script.
* a cronjob that triggers this script regularly.
* a dynamic webpage that loads the generated json file, shows the data in a tabular view and provides filtering.

## Installation
First, copy the web application files:

```
$ cd /srv/salt/files/interface-usage/
$ sudo cp -a webapp/ /var/www/128technology/t128-interface-usage/
```

To create a menu entry in the 128T UI the following file has to be added (insert your conductor's FQDN or IP address):

```
$ sudo mkdir -p /etc/128technology/thirdparty/ui-links
$ echo '{ "name": "Interface Usage", "url": "https://<conductor fqdn or ip address>/t128-interface-usage/" }' | \
sudo tee /etc/128technology/thirdparty/ui-links/t128-interface-usage.json > /dev/null
```

Finally, a cronjob like this has to be created:

```$ sudo crontab -e
# call the collector script hourly
0 * * * *		/srv/salt/files/interface-usage/t128-interface-usage-collector.sh
```


## Configuration

By default there is no configuration needed. The `t128-interface-usage-collector.sh` script allows to customize the stats collection process:

```
$ sudo vi /srv/salt/files/interface-usage/t128-interface-usage-collector.sh
...
script=/srv/salt/files/t128-interface-usage.pyz
# start new statistics capture - ensure buckets are reset every month
options=--buckets-file t128-interface-usage-buckets-$(date '+%Y%m').json

$script $options
```

For example if you want to ignore some routers (e.g. "my-conductor") the following parameter can be used:

```
options="$options --blacklisted-routers my-conductor"
```

The same can be done to ignore interfaces **globally**:

```
options="$options --blacklisted-interfaces ha_sync,ha_fabric"
```

The `--base-interfaces` parameter ensures that a particular list of interfaces is always shown in the tabular view and allows to provide a specific order of interfaces, e.g.:

```
options="$options --base-interfaces WAN1,WAN2,LTE1,LAN1"
```

**Note: List elements (routers and interfaces) have to be separated by commas.**

## Build .pyz File (only needed for development)
The .pyz file is a [compressed python archive](https://docs.python.org/3/library/zipapp.html) (similar to .jar files in the Java universe) which allows it to execute the main python script inside the archive, but at the same time split up modules into separate files/folders (aka modules).

The source code at [salt-states/files/interface-usage](https://github.com/128technology/salt-states/blob/master/files/interface-usage) comes with a script `create_pyz.oy` that creates the archives based on the source files.

```
$ cd salt-states/files/interface-usage
$ ./create_pyz.py
```

Done.
