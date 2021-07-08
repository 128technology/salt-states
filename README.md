# 128T Salt States #
This repo contains salt states and modules that can be used along with the 128T Automated provizioner for full Zero Touch Provisioning of new 128T rotuers.  These states can also be used to automate specific Linux functions on existing 128T routers.

## Installation ##
These states should be installed on a 128T Conductor in the /srv/salt directory.  The existing top.sls and dummy.sls files should be preserved, along with any other custom states that may have been created.
```
cd /srv
mv salt/*.sls .
\rm -rf salt
git clone https://github.com/128technology/salt-states.git salt
mv *.sls salt
```

The t128_netconf_utilities salt module relies on specific libraries in order to communicate with the conductor via Netconf.  These must be installed as shown below.
```
cd ~
yum -y install git python-ncclient
git clone https://github.com/128technology/python-netconf-utilities.git
pip install python-netconf-utilities/
pip install yinsolidated
```

## Module Documentation ##
Some sample modules are included in this library to help manage your 128T deployment.  Here is some light documentation for the modules.

### t128_config_template ###
This execution module is provided as sample code for leveraging the Netconf API and Jinja templating to push templated configuration to the conductor.  This module uses the salt pillar infrastructure as a database of values to use when filling out templates.

#### Template Configuration ####
Templates should be placed in `/srv/salt/config_templates` and have the extension `.jinja`.  The contents of this file should represent the textual configuration that is to be pushed with variables paramaterized as Jinja variables.  For example we will use these contents for a file named `sample.jinja` located in that directory:
```
config
    authority
        router        {{ name }}
            name                 {{ name }}
            inter-node-security  internal

            node                 {{ name }}
                name              {{ name }}
                role              combo

                device-interface  test
                    name               test
                    type               ethernet
                    pci-address        0000:00:00.0

                    network-interface  test
                        name     test

                        address  {{ router.address }}
                            ip-address     {{ router.address }}
                            prefix-length  {{ router.prefix }}
                        exit
                    exit
                exit
            exit
        exit
    exit
exit
```
This template will depend on these variables:
* name
* router.address
* router.prefix

All Jinja variables names pulled from pillar should start with `router.` except `name`.

#### Router data as pillar ####
The router name provided to the module will be used as the index to lookup within pillar.  All this should correspond to a pillar object that contains all variables used in the template.  For example, setting up a file `/srv/pillar/routers.sls` with the following contents:
```
test1:
  address: 192.168.1.1
  prefix: 24
test2:
  address: 192.168.2.1
  prefix: 24
```
Would provide data for two potential routers to render the above template.  Do not forget to assign the pillar data to the conductor's minion by configuring the `/srv/pillar/top.sls` file with something that looks similar to the following:
```
base:
  'conductor':
  - router
```
Substitute the appropriate conductor minion id for `conductor`.

#### Using the module ####
Once there is a config template and pillar data available, the module is ready to be used.  The following functions can be used to add or delete a router from the conductor.

##### Adding a Router #####
The syntax to add a router is: `salt-call t128_config_template.add_router <template_name> <router_name>`.  These are the two options:
* __template_name__ - The name of the template to render.  This is the filename of the template found in the `/srv/salt/config_templates` directory minus the `.jinja` extension
* __router_name__ - The name of the router to use in rendering the template.  This is the key that will be used to look for router data in the conductor's salt pillar.

For example, to add one of the routers following the example above, use: **salt-call t128_config_template.add_router sample test1**

#### Deleting a router ####
The syntax to delete a router is: `salt-call t128_config_template.delete_router <router_name>`.  The only option for this is:
* __router_ name__ - The name of the router to delete from the config.  The module will pull the configuration and parse it looking for elements to delete related to the router.

For example, to delete one of the routers following the example above, use: **salt-call t128_config_tepmlate.delete_rotuer test1**

**Note:** many of the actions needed in the delete configuration are typically no longer necessary due to config generation.  But we will leave the code for legacy purposes.

### t128_users ###
Both an execution module and state module are provided for managing local user accounts for the 128T.  

#### Execution Module ####
The execution module leverages the local GraphQL API to query, add, delete, and modify users.  This can be initiated from the conductor with the following syntax: `t128-salt <asset id> t128_users.<module function> [<function arguments>]`.  Here are the various functions provided along with their arguments:

* **get_users** - This function will return a dictionary of the 128T users configured on the router along with all configured options (minus the password).  This function takes no arguments.  If there is any issue retrieving the data, the function will return `False`.
* **add_user** - This function will create a user with any provided arguments. If the user already exists, or if there are any other issues adding the user, this function will return `False`.  It will return `True` if the function succeeded.  The possible function arguments are:
    * **name** - This is the username of the user to be added.  This argument is required.
    * **password=*password*** - The user's password.  This is passed as a keyword argument.  This argument is required.  At the moment, this only accepts an unhashed password value.
    * **role=*role*** - The user's role.  This is passed as a keyword argument.  The system expects either `admin` or `user`.  The system allows this to be passed as a list.  If a string is passed, it will be converted to a list.  If this option is not present the value of `user` will be used.
    * **enabled=*enabled*** - Whether the account should be enabled or disabled.  A boolean value must be passed.  If this option is not present the value of `True` will be used.
    * **fullName=*Full Name*** - The full name of the user.  This value is optional.
* **modify_user** - This function will modify an existing user with any provided arguments.  If the user does not exist, or if there are any other issues, this function will return `False`.  It will return `True` if the operation succeeded.  This function will accept any of the options provided with the **add_user** function.  The `name` value is required.  Only keyword arguments passed will be changed.
* **delete_user** - This function will delete an existing user.  The only option supported is the `name` of the user.  This function will return `False` if the user did not exist or if there was an issue deleting the user.  It will return `True` if it was successful

#### State Module ####
The state module is intended to function in a similar manner to the standard salt `user` state module.  The following will show specific usage examples for the state functions.

##### t128_users.present #####
Ensure that the named user is present with the specified properties.  This state takes the same options as the **add_user** execution module function.
```
test1:
  t128_users.present:
  - password: 128tRoutes

Ensure user test2 exists with these options:
  t128_users.present:
  - name: test2
  - password: 128tRoutes123
  - enabled: false
  - fullName: Test User2
```

##### t128_users.absent #####
Ensure that the named user is absent from the system.
```
Delete user test1:
  t128_users.absent:
  - name: test1
```

##### t128_users.manage_usder_list #####
This function is intended to manage a predetermined list of user, such as from pillar.  It will ensure the supplied list of users exists on the system and will delete unexpected users.  This state supports two options:
* **users** - A list of dicts of users, each containing the desired user properties.  This option is required.
* **do_not_delete** - A list of usernames to omit from consideration for deletion, should they not be in the **users** list.  This list will default to only containing the `admin` user if not supplied.

This state will ensure all users (except `admin`) are deleted from the system:
```
Delete all users:
  t128_users.manage_user_list:
  - users:
```
And this state will Ensure the presence of only `admin` and the users found in the router's pillar under the variable `t128_users`:
```
Manage User List:
  t128_users.manage_user_list:
  - users: {{ pillar['t128_users'] }}
```
An example of pillar data to use with that state would be:
```
t128_users:
- name: test1
  password: 128tRoutes
- name: test2
  password: 128tRoutes
  enabled: false
- name: test3
  password: 128tRoutes
  enabled: true
  role: admin
- name: test4
  password: 128tRoutes
  role: admin
  fullName: Test User 4
- name: test5
  password: 128tRoutes
  role: user
  fullName: Test User 5
```

## State file documentation ##
Specific documentation for the salt state can be found at the beginning of each individual state file.
