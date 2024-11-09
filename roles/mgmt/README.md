# Servers Role

Configures Ubuntu servers with the following settings:
 - Chrony service for NTP 
 - Uplink interface (bond) with:
   - Access VLAN
   - IP address 
   - Default-gateway 
 - iperf for traffic generation between servers (if needed for NetQ testing etc.)

## Example 

```
devices:
  server01:
    bond:
      vlan: 10
      ip: 10.1.10.101/24
      route:
        dest: 10.0.0.0/8
        nexthop: 10.1.10.1
```

