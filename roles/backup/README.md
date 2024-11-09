
# Backup Role

Backups switches startup-configuration - `startup.yaml` and servers networking configuration - `/etc/network/intefaces` files to the `config` folder under the demo inventory on the ansible server (`oob-mgmt-server` in in AIR):
  - [EVPN Symetric](/inventories/evpn_symmetric/config)
  - [EVPN Centralized](/inventories/evpn_symmetric/config) 
  - [EVPN L2 Only](/inventories/evpn_symmetric/config) 
  - [EVPN Multihoming](/inventories/evpn_symmetric/config) 
 

Variable | Choices/Defaults | Type
--- | --- | ---
backup.path|__Default:__<br>"../inventories/{{ fabric_name }}/config/{{ inventory_hostname }}"|String
backup_switch.files|__Default:__<br>backup_switch.files:<br>  - "/etc/nvue.d/startup.yaml" |List of Strings
backup_host.files|__Default:__<br>backup_host.files:<br>  - "/etc/network/interfaces"  |List of Strings

## Example 

```
backup:
  path: "../inventories/{{ fabric_name }}/config/{{ inventory_hostname }}" 
backup_switch:
  files:
    - "/etc/nvue.d/startup.yaml" #single startup-config file
backup_host:
  files:
    - "/etc/network/interfaces"
```
This role also backups the ansible vars of all devices and stores them into a yaml file in `/ansible_vars` folder of each device.

Variable | Choices/Defaults | Type
--- | --- | ---
user_vars|"{{ to_nice_yaml( width=50, explicit_start=True, explicit_end=True) }}"| Yaml
backup.path|__Default:__<br>"{{ ( '../inventories/' + fabric_name + '/config/' + inventory_hostname ) + '/ansible_vars' }}"| String

Note: The `config` folder in this repository contains all the configurtion files and ansible vars for your reference.