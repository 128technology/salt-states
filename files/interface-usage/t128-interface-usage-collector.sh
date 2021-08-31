#!/bin/sh

dir="/var/lib/128technology"
# remove bucket files older than 90 days
find "$dir" -maxdepth 1 -name t128-interface-usage-buckets*.json -ctime +90 -delete

script=/srv/salt/files/t128-interface-usage.pyz
# start new statistics capture - ensure buckets are reset every month
options="--buckets-file $dir/t128-interface-usage-buckets-$(date '+%Y%m').json"

# optionally, ignore interfaces and/or routers
#options="$options --blacklisted-routers my-conductor"
#options="$options --blacklisted-interfaces ha_sync,ha_fabric"

$script $options
