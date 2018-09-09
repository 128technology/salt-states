#!/bin/bash

function valid_ip()
{
    local  ip=$1
    local  stat=1

    if [[ $ip =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
        OIFS=$IFS
        IFS='.'
        ip=($ip)
        IFS=$OIFS
        [[ ${ip[0]} -le 255 && ${ip[1]} -le 255 \
            && ${ip[2]} -le 255 && ${ip[3]} -le 255 ]]
        stat=$?
    fi
    return $stat
}

# If we have any FQDNs, we should make sure DNS works first test for non-valid IPs in left or right
FQDNS_PRESENT=false
VPN_ENDPOINTS=($(grep -E "left=|right=" /etc/ipsec.d/*.conf | cut -d '=' -f 2))
for ENDPOINT in "${VPN_ENDPOINTS[@]}"
do
  if !(valid_ip $ENDPOINT); then
    printf "%s" "$ENDPOINT"
    FQDNS_PRESENT=true
    break
  fi
done

# If we find an FQDN, we wan't to loop until DNS works
if [ "$FQDNS_PRESENT" = true ]; then
  until ip netns exec $IPSEC_NAMESPACE /bin/nslookup 128technology.com >> /tmp/sfc-ipsec-a 2>&1
  do
    date >> /tmp/sfc-ipsec-a
    sleep 1
  done
fi
