# cl_support_ansible

This playbook is meant to create and gather cl-supports on every target switch running Cumulus Linux.

To use this playbook, there are two methods. Both playbooks do the same thing, just in two different consumable formats. They will create a cl-support on the target node, then use the `copy` module to copy the cl-support into the local directory where the playbook resides.

## Update `hosts` file

The `hosts` file is generic and needs to be updated to reflect the correct hostnames of all switches in production.

## Standalone

`clsupport-standalone.yml` can be run as a standalone playbook without any other dependencies.

To run this playbook:

```
$ ansible-playbook clsupport-standalone.yml
```

### Roles

`clsupport-playbook.yml` uses roles defined in the `roles` directory so that these plays can be incorporated into other playbooks.

To run this playbook:

```
$ ansible-playbook clsupport-playbook.yml
```