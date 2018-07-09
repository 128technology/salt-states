## Setup IPSec Service Function Chaining
##
## Pillar Variables:
##
## Name       | Type                 | Default Value | Description
## ----------------------------------------------------------------------------------------------------
## ipsec_vpns | list of dictionaries | None          | Details about each IPSec VPN
##
## ipsec_vpns is a dictionary of one or more VPN connections.  The keys in this dictionary are the
## names for the VPN, which should match the 128T device-interface name
##
## Name        | Type    | Default Value | Description
## ----------------------------------------------------------------------------------------------------
## authby      | string  | 'secret'      | The type of authentication used for the tunnel.  Only 'secret' is currently supported
## ike         | string  | None          | The encryption/authentication algorithm to use for phase1
## ikev2       | string  | 'insist'      | Whether or not to offer IKEv2 on this tunnel
## phase2      | string  | 'esp'         | The type of SA to establish
## phase2alg   | string  | None          | Specifies the algorithms that will be offered/accepted for a phase2 negotiation
## ikelifetime | string  | '1h'          | How long the keying channel of a connection should last before being renegotiated
## salifetime  | string  | '8h'          | How long a particular instance of a connection should last, from successful negotiation to expiry
## compress    | string  | 'no'          | Whether IPComp compression of content is proposed on the connection
## pfs         | string  | 'no'          | Whether Perfect Forward Secrecy of keys is desired on the connection
## dpddelay    | string  | None          | Optionally set the delay between keepalives sent for this connection
## dpdtimeout  | string  | None          | Optionally set the timeout we will use to declare the peer dead if we have not seen any traffic
## dpdaction   | string  | None          | The action to take when a peer is declared dead.  Suggested use when enabling DPD is 'restart'
## leftsubnet  | string  | '0.0.0.0/0'   | The local CIDR range to route from the VTI to the KNI
## leftid      | string  | None          | Optional value for the local side to use to identify itself for authentication
## right       | string  | None          | The IP address or FQDN of the remote end of the tunnel
## rightsubnet | string  | '0.0.0.0/0'   | The remote CIDR range to route from the KNI to the VTI
## metric      | integer | None          | Optional value to use as a routing metric when a VPN has multiple tunnels
## psk         | string  | None          | The pre-shared key value to use for this connection
##
## Pillar example:
##
## ipsec_vpns:
##   zscaler:
##     - right: was1-vpn.zscalerbeta.net
##       ike: aes128-sha1;MODP1024
##       ikelifetime: 120m
##       salifetime: 30m
##       phase2alg: null-md5;MODP1024
##       psk: XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
##       leftid: 162.198.132.64
##       metric: 100
##     - right: sunnyvale1-vpn.zscalerbeta.net
##       ike: aes128-sha1;MODP1024
##       ikelifetime: 120m
##       salifetime: 30m
##       phase2alg: null-md5;MODP1024
##       psk: XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
##       leftid: 162.198.132.64
##       metric: 200
##
{%- set ipsec_vpns = pillar.get('ipsec_vpns') %}
{%- for vpn, tunnels in ipsec_vpns.iteritems() %}
Create configuration file for VPN {{ vpn }}:
  file.managed:
    - name: /etc/ipsec.d/{{ vpn }}.conf
    - user: root
    - group: root
    - mode: 600
    - contents: |
        {%- for tunnel in tunnels %}
        {%- if tunnel.right | is_ip %}
          {%- set mark=salt['network_functions.get_address_as_decimal'](tunnel.right) %}
        {%- else %}
          {%- set resolved_address=salt['dnsutil.A'](tunnel.right)[0] %}
          {%- set mark=salt['network_functions.get_address_as_decimal'](resolved_address) %}
        {%- endif %}
        conn {{ vpn }}-tunnel{{ loop.index }}
          authby={{ tunnel.authby | default('secret') }}
          auto=up
          ike={{ tunnel.ike }}
          ikev2={{ tunnel.ikev2 | default('insist') }}
          phase2={{ tunnel.phase2 | default('esp') }}
          phase2alg={{ tunnel.phase2alg }}
          keyexchange=ike
          ikelifetime={{ tunnel.ikelifetime | default('1h') }}
          salifetime={{ tunnel.salifetime | default('8h') }}
          compress={{ tunnel.compress | default('no') }}
          pfs={{ tunnel.pfs | default('no') }}
        {%- if tunnel.get('dpddelay') %}
          dpddelay={{ tunnel1.dpddelay }}
        {%- endif %}
        {%- if tunnel.get('dpdtimeout') %}
          dpdtimeout={{ tunnel.dpdtimeout }}
        {%- endif %}
        {%- if tunnel.get('dpdaction') %}
          dpdaction={{ tunnel.dpdaction }}
        {%- endif %}
          left={{ salt['grains.get']('t128_ipsec_local_address') }}
          leftsubnet={{ tunnel.leftsubnet | default('0.0.0.0/0') }}
        {%- if tunnel.get('leftid') %}
          leftid={{ tunnel.leftid }}
        {%- endif %}
          right={{ tunnel.right }}
          rightsubnet={{ tunnel.rightsubnet | default('0.0.0.0/0') }}
          mark={{ mark }}/0xffffffff
          vti-interface=vti{{ mark }}
          vti-shared=no
          vti-routing=yes
          leftupdown="/usr/libexec/updown_128t.sh --route y --kni {{ vpn }}"
        {%- if tunnel.get('metric') %}
          metric={{ tunnel.metric }}
        {%- endif %}
        {%- endfor %}

Create secrets file for {{ vpn }}:
  file.managed:
    - name: /etc/ipsec.d/{{ vpn }}.secrets
    - user: root
    - group: root
    - mode: 600
    - contents: |
        {%- for tunnel in tunnels %}
        {{ tunnel.leftid | default(salt['grains.get']('t128_ipsec_local_address')) }} {{ tunnel.right }} : PSK "{{ tunnel.psk }}"
        {%- endfor %}

Setup init script for {{ vpn }}:
  file.managed:
    - name: /etc/128technology/plugins/network-scripts/host/{{ vpn }}/init
    - source: salt://files/ipsec-connection-init
    - mode: 744
    - makedirs: True
{%- endfor %}
