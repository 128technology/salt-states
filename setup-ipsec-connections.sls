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
          keyexchange={{ tunnel.keyexchange | default('ike') }}
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
