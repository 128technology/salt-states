## Configure Firewalld Viritual Zone for Customer Support Access
## 
## Pillar Variables:
##
## Name               | Type       | Default Value | Description
## --------------------------------------------------------------------------------------------------------
## customer_name      | String     | None          | The customers name to use as the firewall zone name
## firewalld_customer | dictionary | None          | Details of the traffic to allow inbound detailed below
##
## firewalld_customer dictionary description:
##
## Name     | Type | Default Value    | Description
## ----------------------------------------------------------------------------------
## services | list | ['https', 'ssh'] | The list of services to allow inbound
## sources  | list | None             | The list of source addresses to allow inbound
##
## Example pillar data:
##
## customer_name: SampleCustomer
## firewalld_customer:
##   sources:
##     - 1.1.1.1/32
##     - 1.1.1.2/32

{% if pillar.firewalld_customer is defined and pillar.customer_name is defined %}
Setup Customer firewalld zone:
  firewalld.present:
    - name: {{ salt['pillar.get']("customer_name") }}
    {% if (pillar.firewalld_customer.services is defined) and pillar.firewalld_customer.services %}
    - services: {{ salt['pillar.get']("firewalld_customer:services") }}
    {% else %}
    - services:  
      - https
      - ssh
    {% endif %}
    {% if (pillar.firewalld_customer.sources is defined) and pillar.firewalld_customer.sources %}
    - sources: {{ salt['pillar.get']("firewalld_customer:sources") }}
    {% endif %}
{% endif %}
