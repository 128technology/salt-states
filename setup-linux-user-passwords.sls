## Set Linux Accounts to passwords defined hashes.
## Hashes are generated via the command python -c "import crypt; print crypt.crypt('myPasswordHere', '\$6\$SALTsalt')"
##
## Pillar variables
##
## Name         | Type   | Default Value | Description
## -------------------------------------------------------------------------------------
## root_pw_hash | String | None          | The hashed value to use for the root password
## t128_pw_hash | String | None          | The hashed value to use for the t128 password
##

## TO DO - Look into verifying a valid hash is provided

Linux_root_password_hash_check:
{%- set root_pw = pillar.get('root_pw_hash') %}
{%- set current_root = salt['shadow.info']('root').passwd %}
{%- if root_pw  %}
  {%- if root_pw == current_root %}
  test.configurable_test_state:
    - name: shadow.set_password
    - changes: False
    - result: True
    - comment: "root password Already Set to Configured Hash"  
  {%- else %}
  module.run:
      - name: shadow.set_password
      - m_name: root
      - password: {{ root_pw }}
  {%- endif %}
{%- else %}
  {%- do salt.log.warning("Salt pillar value root_pw_hash is not defined or is an invalid password hash") %}
  test.configurable_test_state:
    - name: shadow.set_password
    - changes: False
    - result: False
    - comment: "Pillar root_pw_hash is not set"
{%- endif %}

Set_Linux_t128_password_hash_from_pillar:
{%- set t128_pw = pillar.get('t128_pw_hash') %}
{%- set current_t128 = salt['shadow.info']('t128').passwd %}
{%- if t128_pw  %}
  {%- if t128_pw == current_t128 %}
  test.configurable_test_state:
    - name: shadow.set_password
    - changes: False
    - result: True
    - comment: "t128 password already set to configured hash"
  {%- else %}
  module.run:
    - name: shadow.set_password
    - m_name: t128
    - password: {{ pillar.get('t128_pw_hash') }}
  {%- endif %}
{%- else %}
  {%- do salt.log.warning("Salt pillar value t128_pw_hash is not defined or is an invalid password hash") %}
  test.configurable_test_state:
    - name: shadow.set_password
    - changes: False
    - result: False
    - comment: "Pillar t128_pw_hash is not set"
{%- endif %}
