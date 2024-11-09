<!-- AIR:tour -->

# NVIDIA DGX H100 BasePOD - Ethernet Fabric Configuration

This environment demonstrates the [NVIDIA DGX™ BasePOD](https://www.nvidia.com/en-us/data-center/dgx-basepod/) with [DGX™ H100](https://www.nvidia.com/en-us/data-center/dgx-h100/) and rail-optimized [ethernet fabric](https://www.nvidia.com/en-us/networking/ethernet-switching/) configuration. 

This is the general reference architecture (RA) diagram of the BasePOD DGX™ H100 with [Spectrum-4](https://nvdam.widen.net/s/pjlcwnrdbn/ethernet-switches-spectrum-4-asic-datasheet-us) [SN5600](https://nvdam.widen.net/s/mmvbnpk8qk/networking-ethernet-switches-sn5000-datasheet-us) ethernet switches.

![](https://gitlab.com/cumulus-consulting/goldenturtle/cumulus_ansible_modules/-/raw/basepod_dgx_h100/images/RA.png)

The BasePOD RA consists of the following elements:
- 2 x SN5600 switches
- 4-16 x DGX H100 nodes
- 5 x Management nodes - 2 x Base Command Manager head nodes (BCM) and 3 x k8s nodes
- 1-12 X Storage appliance
- 2 x SN2201 (IPMI) switches

The purpose of this demo is to show Cumulus Linux switch configuration for E/W and N/S networks over the same switches, so only the SN5600 switches are running Cumulus Linux VX (IPMI and edge as well, but they are not relevant). The nodes in the demo (DGX, BCM, k8s, and storage) are based on Ubuntu 22.04 servers with NICs configured with IP addresses to match the environment and to be able to reach each other. No actual software runs on them. 

The network design of the BasePOD is based on scale-out solutions (e.g., Spectrum-X). But as the BasePOD maximum scale is 16 DGX nodes, we made the needed changes for these scales and can fit into a pair of SN5600 switches for all networks. To provide multi-tenant infrastructure, we use [BGP](https://docs.nvidia.com/networking-ethernet-software/cumulus-linux/Layer-3/Border-Gateway-Protocol-BGP/) and [EVPN](https://docs.nvidia.com/networking-ethernet-software/cumulus-linux/Network-Virtualization/Ethernet-Virtual-Private-Network-EVPN/), and each network type runs within different VRF and set with a different EVPN implementation that we will cover during the demo.

## Networks overview

DGX™ BasePOD H100 consists of four* networks:
- Compute (E/W) - Red.
- Inband-mgmt. and storage (N/S) - Blue.
- Out-of-Band-mgmt. (IPMI/BMC) - Gray.
- Converged - Green.

*As BasePOD is an "island" in the data center, there is an additional network to access the data center (edge network). 

Both E/S and N/S networks share the same two Spectrum-4 SN5600 switches but use different ports for physical separation (RoCE, QoS, buffers, etc.).
To logically divide these networks within the same switches, we use different [VRFs](https://docs.nvidia.com/networking-ethernet-software/cumulus-linux/Layer-3/VRFs/Virtual-Routing-and-Forwarding-VRF/):
- `tenant1` for E/W network. 
- `inband_storage` for N/S network. 

**Note:** Those VRF names are just placeholders for more straightforward representation. Different VRF must be allocated per tenant for multi-tenancy, e.g., `tenant2`, `tenant3`, etc. 

The Out-of-Band (OOB) mgmt. network of the BasePOD is a separate network that is deployed over Spectrum-1 SN2201 switches. But, this network is also connected to the `inband_storage` VRF to be reachable from the data center.

### Compute (GPU) E/W network

BasePOD E/W network is a pure layer 3 network. The links between the Connexct-X7 (CX7) smartNICs (GPU ports on DGX) and the SN5600 switches are router ports. The IP addressing scheme is based on a point-to-point (p2p) (`/31`) IPv4 addresses so that each GPU CX7 NIC will have a different IP subnet within the same supernet, e.g., `10.1.1.0/31`, `10.1.1.2/31`, and so forth.
To enable a multi-tenant infrastructure, we use pure Type 5 EVPN routes – so that the IP-prefix EVPN route provides all the necessary forwarding information with the MAC-extended community. This is done by exporting those prefixes to EVPN. Later, we will see how it's configured on Cumulus Linux OS.

### Inband Mgmt. and storage N/S network

The N/S network requires layer 2 connectivity for DGX management, BCM, k8s, and storage nodes. We use [EVPN Multihoming](https://docs.nvidia.com/networking-ethernet-software/cumulus-linux/Network-Virtualization/Ethernet-Virtual-Private-Network-EVPN/EVPN-Multihoming/) and [Virtual Router Redundancy - VRR](https://docs.nvidia.com/networking-ethernet-software/cumulus-linux/Layer-2/Virtual-Router-Redundancy-VRR/) to eliminate the need for a proprietary [MLAG](https://docs.nvidia.com/networking-ethernet-software/cumulus-linux/Layer-2/Multi-Chassis-Link-Aggregation-MLAG/) deployment. Using this deployment type, the switch interconnect ports (green) are routed underlay ports with ECMP and serve all networks (VRFs) without dedicating them to a specific purpose like MLAG peerlink.

<!-- AIR:page -->
sudo apt-get update
sudo apt-get install python3-pip -y  # Ensure pip is installed
sudo pip3 install netaddr

## Demo devices and IP addressing 

### Devices

Our demo simulates the smallest deplyoment of the BasePOD and consits of the the following devices.

| __Leaf__ | __DGX__ | __BCM__ | __k8s__ | __Storage__ | __IPMI and Edge__ |
| -------- | ------- | ------- | ------- | ----------- | ----------------- |
| leaf01   | dgx01   | bcm01   | k8s01   | storage01   | ipmi01            |
| leaf02   | dgx02   | bcm02   | k8s02   | storage02   | ipmi02            |
|          | dgx03   |         | k8s03   |             | edge01*           |
|          | dgx04   |         |         |             | edge02*           |

*We added additional two switches that simulate the data center edge swtiches. 

### Fabric switches IP addressing (SN5600)

| __Interface__ | __VRF__        | __VLAN__    | __leaf01__        | __leaf02__        |
| ------------- | -------------- | ----------- | ----------------- | ----------------- |
| eth0          | mgmt.          |             | 192.168.200.2/24  | 192.168.200.3/24  |
| lo            | default        |             | 10.10.10.1/32     | 10.10.10.2/32     |
| swp1s0        | tenant1        |             | 10.1.1.1/31       | 10.1.1.3/31       |
| swp1s1        | tenant1        |             | 10.1.1.5/31       | 10.1.1.7/31       |
| swp1s2        | tenant1        |             | 10.1.1.9/31       | 10.1.1.11/31      |
| swp1s3        | tenant1        |             | 10.1.1.13/31      | 10.1.1.15/31      |
| swp2s0        | tenant1        |             | 10.1.1.17/31      | 10.1.1.19/31      |
| swp2s1        | tenant1        |             | 10.1.1.21/31      | 10.1.1.23/31      |
| swp2s2        | tenant1        |             | 10.1.1.25/31      | 10.1.1.27/31      |
| swp2s3        | tenant1        |             | 10.1.1.29/31      | 10.1.1.31/31      |
| swp3s0        | tenant1        |             | 10.1.1.33/31      | 10.1.1.35/31      |
| swp3s1        | tenant1        |             | 10.1.1.37/31      | 10.1.1.39/31      |
| swp3s2        | tenant1        |             | 10.1.1.41/31      | 10.1.1.43/31      |
| swp3s3        | tenant1        |             | 10.1.1.45/31      | 10.1.1.47/31      |
| swp4s0        | tenant1        |             | 10.1.1.49/31      | 10.1.1.51/31      |
| swp4s1        | tenant1        |             | 10.1.1.53/31      | 10.1.1.55/31      |
| swp4s2        | tenant1        |             | 10.1.1.57/31      | 10.1.1.59/31      |
| swp4s3        | tenant1        |             | 10.1.1.61/31      | 10.1.1.63/31      |
| swp29s0       | inband_storage |             | 10.150.0.0/31     | 10.150.0.4/31     |
| swp29s1       | inband_storage |             | 10.150.0.2/31     | 10.150.0.6/31     |
| swp45         | inband_storage |             | 10.140.0.0/31     | 10.140.0.4/31     |
| swp46         | inband_storage |             | 10.140.0.2/31     | 10.140.0.6/31     |
| vlan121       | inband_storage | 121         | 10.130.121.2/24   | 10.130.121.3/24   |
| vlan121-v0    | inband_storage | 121         | 10.130.121.1/24   | 10.130.121.1/24   |
| vlan122       | inband_storage | 122         | 10.130.122.2/24   | 10.130.122.3/24   |
| vlan122-v0    | inband_storage | 122         | 10.130.122.1/24   | 10.130.122.1/24   |
| bond1-9       | inband_storage | 122/All     |                   |                   |


### OOB-Mgmt. (IPMI) and edge switches IP addressing

| __Interface__ | __VRF__  | __VLAN__ | __ipmi01__        | __ipmi02__        | __edge01__        | __edge02__        |
| ------------- | -------- | -------- | ----------------- | ----------------- | ----------------- | ----------------- |
| eth0          | mgmt.    |          | 192.168.200.4/24  | 192.168.200.5/24  | 192.168.200.6/24  | 192.168.200.7/24  |
| lo            | default  |          | 10.100.100.0/32   | 10.100.100.0/32   | 10.200.200.0/32   | 10.200.200.0/32   |
| swp49         | default  |          | 10.150.0.0/31     | 10.150.0.3/31     | 10.140.0.1/31     | 10.140.0.3/31     |
| swp450        | default  |          | 10.150.0.2/31     | 10.150.0.7/31     | 10.140.0.5/31     | 10.140.0.7/31     |

**Note:** These switches are used only for IPMI and data center subnet simulation in the BasePOD fabric. Therefore, their loopback addresses are redistributed into the fabric so they will appear in the routing tables of the SN5600 switches but can't be reachable.

### DGX nodes IP addressing      

| __Interface__ | __dgx01__        | __dgx02__        | __dgx03__         | __dgx04__         |
| ------------- | ---------------- | ---------------- | ----------------- | ----------------- |
| eth0          | 192.168.200.8/24 | 192.168.200.9/24 | 192.168.200.10/24 | 192.168.200.11/24 | 
| eth1          | 10.1.1.0/31      | 10.1.1.16/31     | 10.1.1.32/31      | 10.1.1.48/31      |
| eth2          | 10.1.1.2/31      | 10.1.1.18/31     | 10.1.1.34/31      | 10.1.1.50/31      |
| eth3          | 10.1.1.4/31      | 10.1.1.20/31     | 10.1.1.36/31      | 10.1.1.52/31      |
| eth4          | 10.1.1.6/31      | 10.1.1.22/31     | 10.1.1.38/31      | 10.1.1.54/31      |
| eth5          | 10.1.1.8/31      | 10.1.1.24/31     | 10.1.1.40/31      | 10.1.1.56/31      |
| eth6          | 10.1.1.10/31     | 10.1.1.26/31     | 10.1.1.42/31      | 10.1.1.58/31      |
| eth7          | 10.1.1.12/31     | 10.1.1.28/31     | 10.1.1.44/31      | 10.1.1.60/31      |
| eth8          | 10.1.1.14/31     | 10.1.1.30/31     | 10.1.1.46/31      | 10.1.1.62/31      |
| bond0         | 10.130.122.5/24  | 10.130.122.6/24  | 10.130.122.7/24   | 10.130.122.8/24   |

### BCM head nodes IP addressing  

| __Interface__| __bcm01__         | __bcm02__         |
| ------------ | ----------------- | ----------------- |
| eth0         | 192.168.200.12/24 | 192.168.200.13/24 |
| eth1         | 10.130.121.254/24 | 10.130.121.253/24 |
| eth2         | 10.130.122.254/24 | 10.130.122.253/24 |

### k8s management nodes IP addressing  

| __Hostname__| __k8s01__         | __k8s02__         | __k8s03__         |
| ---------   | ----------------- | ----------------- | ----------------- |
| eth0        | 192.168.200.14/24 | 192.168.200.15/24 | 192.168.200.16/24 |
| bond0       | 10.130.122.23/24  | 10.130.122.24/24  | 10.130.122.25/24  |

### Storage nodes IP addressing  

| __Interface__| __storage01__     | __storage02__     |
| ------------ | ----------------- | ----------------- |
| eth0         | 192.168.200.17/24 | 192.168.200.18/24 |
| bond0        | 10.130.122.100/24 | 10.130.122.101/24 |

<!-- AIR:page -->

## Demo environment access

All environment device access is done via the jump server - `oob-mgmt-server`.

Use the default access credentials to log in to the `oob-mgmt-server`:
 - Username: ***ubuntu***
 - Password: ***nvidia***

***Note:*** *Once you first log in, you must change the default password.*

You can use the web-integrated console or create an SSH service to access the `oob-mgmt-server` using any SSH client.  
Check out the NVIDIA Air [Quick Start](https://docs.nvidia.com/networking-ethernet-software/guides/nvidia-air/Quick-Start/) guide for more information and step-by-step instructions.

Once you log in to the `oob-mgmt-server`, you can access any device in the topology using its hostname.

Login to the DGX, BCM, storage, or K8s nodes, and use their hostnames - `ssh <hostname>` (all have the same username - `ubuntu`, which is identical to the `oob-mgmt-server` username).

Default server credentials are:  
 - Username: ***ubuntu***
 - Password: ***nvidia*** 

```bash
ubuntu@oob-mgmt-server:~$ ssh dgx01
```

Login to the switches using the `cumulus` username - `ssh cumulus@<hostname>`. To ease access, the `cumulus` username was set to passwordless authentication from `oob-mgmt-server`. 
```bash
ubuntu@oob-mgmt-server:~$ ssh cumulus@leaf01
```
When logging in from other environment devices, use `ssh cumulus@<ip-address>`.

Default switch credentials are:  
 - Username: ***cumulus***
 - Password: ***CumulusLinux!*** 

<!-- AIR:page -->

# BasePOD configuration

In the following sections, all BasePOD network configurations will be described step-by-step. As an example, all the commands and configuration verifications will be shown on `leaf01`. 

**Note:** Some configuration steps don’t have verification `show` commands as they are prerequisites for other configurations that will be covered in later sections.

For complete configuration, check out the running-configuration of each leaf switch using `nv config show` or `nv config show -o commands`. You can also view the `startup.yaml` file to check the switch startup-configuration.
```bash
nv config show
nv config show -o commands
cat /etc/nvue.d/startup.yaml
```

## IP addressing  

As mentioned, the E/W network is a pure layer 3 network with p2p (/31) IPv4 addresses between the GPU NICs and the switches. Each GPU-switch port is a separate subnet but from a single supernet. All switch ports connected to GPU NICs are breakout x4.
```bash
nv set interface swp1s0 ip address 10.1.1.1/31
nv set interface swp1s1 ip address 10.1.1.5/31
nv set interface swp1s2 ip address 10.1.1.9/31
nv set interface swp1s3 ip address 10.1.1.13/31
nv set interface swp2s0 ip address 10.1.1.17/31
nv set interface swp2s1 ip address 10.1.1.21/31
nv set interface swp2s2 ip address 10.1.1.25/31
nv set interface swp2s3 ip address 10.1.1.29/31
nv set interface swp3s0 ip address 10.1.1.33/31
nv set interface swp3s1 ip address 10.1.1.37/31
nv set interface swp3s2 ip address 10.1.1.41/31
nv set interface swp3s3 ip address 10.1.1.45/31
nv set interface swp4s0 ip address 10.1.1.49/31
nv set interface swp4s1 ip address 10.1.1.53/31
nv set interface swp4s2 ip address 10.1.1.57/31
nv set interface swp4s3 ip address 10.1.1.61/31
```

The inter-switch ports are router ports with a different p2p (`/31`) subnet each. But from a different supernet than the compute network GPU ports. 
```bash
nv set interface swp61 ip address 172.16.1.28/31
nv set interface swp62 ip address 172.16.1.30/31
nv set interface swp63 ip address 172.16.1.32/31
nv set interface swp64 ip address 172.16.1.34/31
```

The N/S network is a layer 2 network, but for the nodes within it to be able to communicate with the outside world (data center), we enable layer 3 VLAN interfaces ([SVI](https://docs.nvidia.com/networking-ethernet-software/cumulus-linux/Layer-2/Ethernet-Bridging-VLANs/VLAN-aware-Bridge-Mode/#vlan-layer-3-addressing)) that will later be used for VRR instances.

```bash
nv set interface vlan121 ip address 10.130.121.2/24
nv set interface vlan122 ip address 10.130.122.2/24
```

Each SN5600 switch has ports to the two IPMI and two edge switches. All those ports are router ports within different subnets. Later, we will establish BGP neighborships on those ports.

To IPMI switches:
```bash
nv set interface swp29s0 ip address 10.150.0.0/31
nv set interface swp29s1 ip address 10.150.0.2/31
```

To edge switches:
```bash
nv set interface swp45 ip address 10.140.0.0/31
nv set interface swp46 ip address 10.140.0.2/31
```
**Note:** In the demo, we assume p2p (/31) addresses the edge switches, but it depends on the existing data center network.

Finally, we have the loopback addresses of each switch.
```bash
nv set interface lo ip address 10.10.10.1/32
```

Configuration verification:
```bash
cumulus@leaf01:mgmt:~$ nv show interface | grep 10
lo              up            65536  loopback                                      IP Address:                10.10.10.1/32
swp1s0          up     1G     9216   swp       dgx01            48:b0:2d:b3:64:4e  IP Address:                  10.1.1.1/31
swp1s1          up     1G     9216   swp       dgx01            48:b0:2d:13:ba:25  IP Address:                  10.1.1.5/31
swp1s2          up     1G     9216   swp       dgx01            48:b0:2d:48:8b:a9  IP Address:                  10.1.1.9/31
swp1s3          up     1G     9216   swp       dgx01            48:b0:2d:3d:d5:ec  IP Address:                 10.1.1.13/31
swp2s0          up     1G     9216   swp       dgx02            48:b0:2d:d5:ba:12  IP Address:                 10.1.1.17/31
swp2s1          up     1G     9216   swp       dgx02            48:b0:2d:17:6e:28  IP Address:                 10.1.1.21/31
swp2s2          up     1G     9216   swp       dgx02            48:b0:2d:ab:5e:aa  IP Address:                 10.1.1.25/31
swp2s3          up     1G     9216   swp       dgx02            48:b0:2d:af:ab:a4  IP Address:                 10.1.1.29/31
swp3s0          up     1G     9216   swp       dgx03            48:b0:2d:59:51:f4  IP Address:                 10.1.1.33/31
swp3s1          up     1G     9216   swp       dgx03            48:b0:2d:03:dc:4b  IP Address:                 10.1.1.37/31
swp3s2          up     1G     9216   swp       dgx03            48:b0:2d:aa:1c:ef  IP Address:                 10.1.1.41/31
swp3s3          up     1G     9216   swp       dgx03            48:b0:2d:76:59:30  IP Address:                 10.1.1.45/31
swp4s0          up     1G     9216   swp       dgx04            48:b0:2d:45:55:a2  IP Address:                 10.1.1.49/31
swp4s1          up     1G     9216   swp       dgx04            48:b0:2d:41:72:fe  IP Address:                 10.1.1.53/31
swp4s2          up     1G     9216   swp       dgx04            48:b0:2d:27:eb:9d  IP Address:                 10.1.1.57/31
swp4s3          up     1G     9216   swp       dgx04            48:b0:2d:4e:b8:f9  IP Address:                 10.1.1.61/31
swp29s0         up     1G     9216   swp       ipmi01           swp49              IP Address:                10.150.0.0/31
swp29s1         up     1G     9216   swp       ipmi02           swp49              IP Address:                10.150.0.2/31
swp45           up     1G     9216   swp       edge01           swp1               IP Address:                10.140.0.0/31
swp46           up     1G     9216   swp       edge02           swp1               IP Address:                10.140.0.2/31
vlan121         up            9216   svi                                           IP Address:              10.130.121.2/24
vlan121-v0      up            9216   svi                                           IP Address:              10.130.121.1/24
vlan122         up            9216   svi                                           IP Address:              10.130.122.2/24
vlan122-v0      up            9216   svi                                           IP Address:              10.130.122.1/24
```
**Note:** All ports are set to 1G speed as this demo runs on a virtual environment (Cumulus VX).

<!-- AIR:page -->

## Global configuration

To ensure proper BasePOD configuration, we must enable these global configurations:
- Lossless [RoCE](https://docs.nvidia.com/networking-ethernet-software/cumulus-linux/Layer-1-and-Switch-Ports/Quality-of-Service/RDMA-over-Converged-Ethernet-RoCE/)
```bash
nv set qos roce enable on
nv set qos roce mode lossless
```
Configuration verification:
```bash
cumulus@leaf01:mgmt:~$ nv show qos roce
                    operational  applied
------------------  -----------  --------
enable                           on
mode                lossless     lossless
congestion-control
  congestion-mode   ECN
  enabled-tc        0,3
  max-threshold     1.43 MB
  min-threshold     146.48 KB
  probability       100
lldp-app-tlv
...
...
```
- BGP and EVPN protocols
```bash
nv set router bgp enable on
nv set evpn enable on
```
We also enable [Graceful BGP Restart](https://docs.nvidia.com/networking-ethernet-software/cumulus-linux/Layer-3/Border-Gateway-Protocol-BGP/Optional-BGP-Configuration/#graceful-bgp-restart).
```bash
nv set router bgp graceful-restart mode helper-only
```
- NVE interface and its parameters (ARP/ND suppress and tunnel source with loopback address)
```bash
nv set nve vxlan enable on
nv set nve vxlan arp-np-suppress on
nv set nve vxlan source address 10.10.10.1
```
<!-- AIR:page -->

## Routing policies

We use routing policies with IP-prefix lists and route-maps to precisely control the subnets’ redistribution. Of course, in small-scale deployments such as BasePOD, this is less significant as we have a small number of routes, but as we follow the same guidelines for all deployments, we keep the policies here as well.

The first IP prefix-list is set to match all GPU (`/31`) subnets 
```bash
nv set router policy prefix-list dgx_subnet rule 10 action permit
nv set router policy prefix-list dgx_subnet rule 10 match 10.1.1.0/24 max-prefix-len 31
nv set router policy prefix-list dgx_subnet type ipv4
```
Configuration verification:
```bash
cumulus@leaf01:mgmt:~$ nv show router policy prefix-list dgx_subnet rule 10
         applied
-------  -----------
action   permit
[match]  10.1.1.0/24
```
Then this prefix-list is used within a route-map which will later be attached to the BGP `redistribute connected` statement into the `tenant1` VRF so that only those subnets will be injected as Type 5 routes into EVPN (BGP and EVPN configuration is covered later).
```bash
nv set router policy route-map dgx_subnets rule 10 action permit
nv set router policy route-map dgx_subnets rule 10 description permit_dgx_subnet
nv set router policy route-map dgx_subnets rule 10 match ip-prefix-list dgx_subnet
nv set router policy route-map dgx_subnets rule 10 match type ipv4
```
Configuration verification:
```bash
cumulus@leaf01:mgmt:~$ nv show router policy route-map dgx_subnets rule 10
                  applied
----------------  -----------------
match
  ip-prefix-list  dgx_subnet
  type            ipv4
description       permit_dgx_subnet
```
The second IP prefix-list matches all inband management network subnets.
```bash
nv set router policy prefix-list inband_subnets rule 10 action permit
nv set router policy prefix-list inband_subnets rule 10 match 10.130.0.0/16 max-prefix-len 24
nv set router policy prefix-list inband_subnets type ipv4
```
Configuration verification:
```bash
cumulus@leaf01:mgmt:~$ nv show router policy prefix-list inband_subnets rule 10
         applied
-------  -------------
action   permit
[match]  10.130.0.0/16
```
Then, it is used within the route-map, which will be attached to the BGP `redistribute connected` statement into the `inband_storage` VRF.
```bash
nv set router policy route-map inband_subnets rule 10 action permit
nv set router policy route-map inband_subnets rule 10 description permit_dgx_subnet
nv set router policy route-map inband_subnets rule 10 match ip-prefix-list inband_subnets
nv set router policy route-map inband_subnets rule 10 match type ipv4
```
Configuration verification:
```bash
cumulus@leaf01:mgmt:~$ nv show router policy route-map inband_subnets rule 10
                  applied
----------------  -----------------
match
  ip-prefix-list  inband_subnets
  type            ipv4
description       permit_dgx_subnet
```
And the 3rd route-map matches the lo interface (loopback IPv4 address). This route-map will be later attached to the BGP `redistribute connected` statement into the `default` VRF. This address will be used for the NVE tunnel over the underlay network.
```bash
nv set router policy route-map lo_subnet rule 10 action permit
nv set router policy route-map lo_subnet rule 10 description permit_lo_subnet
nv set router policy route-map lo_subnet rule 10 match interface lo
nv set router policy route-map lo_subnet rule 10 match type ipv4
```
Configuration verification:
```bash
cumulus@leaf01:mgmt:~$ nv show router policy route-map lo_subnet rule 10
             applied
-----------  ----------------
match
  interface  lo
  type       ipv4
description  permit_lo_subnet
```
**Note:** When setting up a multi-tenant environment, you will need more route-maps per tenant VRF.

<!-- AIR:page -->

## BGP underlay network

The underlay network is set on the `default` VRF. Although the E/W and the N/S use EVPN in different flavors, this underlay will serve both networks. 

We start with the basic BGP configuration on VRF `default` with the `ipv4` and `l2vpn-evpn` address-families, then the `redistribute connected` with the `lo_subnet` route-map attached.
```bash
nv set vrf default router bgp enable on
nv set vrf default router bgp autonomous-system 65101
nv set vrf default router bgp router-id 10.10.10.1
nv set vrf default router bgp address-family ipv4-unicast enable on
nv set vrf default router bgp address-family ipv4-unicast redistribute connected enable on
nv set vrf default router bgp address-family ipv4-unicast redistribute connected route-map lo_subnet
nv set vrf default router bgp address-family l2vpn-evpn enable on
```
Then, we set the BGP underlay neighbors (the inter-switch p2p links). Each neighbor has a `to-<peer switch>-<peer port>` description for easier troubleshooting, and all underlay neighbors are put within the `undelay` peer-group to set all BGP parameters on a single entity.  
```bash
nv set vrf default router bgp neighbor 172.16.1.29 description to-leaf02-swp61
nv set vrf default router bgp neighbor 172.16.1.29 peer-group underlay
nv set vrf default router bgp neighbor 172.16.1.29 type numbered
...
nv set vrf default router bgp neighbor 172.16.1.35 description to-leaf02-swp64
nv set vrf default router bgp neighbor 172.16.1.35 peer-group underlay
nv set vrf default router bgp neighbor 172.16.1.35 type numbered
```
The peer-group is set with the `remote-as external` for eBGP, description, and a 3x300 [BFD](https://docs.nvidia.com/networking-ethernet-software/cumulus-linux/Layer-3/Bidirectional-Forwarding-Detection-BFD/) for faster port failures detection.
```bash
nv set vrf default router bgp peer-group underlay remote-as external
nv set vrf default router bgp peer-group underlay description underlay_interconnect
nv set vrf default router bgp peer-group underlay bfd enable on
nv set vrf default router bgp peer-group underlay bfd detect-multiplier 3
nv set vrf default router bgp peer-group underlay bfd min-rx-interval 300
nv set vrf default router bgp peer-group underlay bfd min-tx-interval 300
```

**Note:** All BGP neighbors we use in our deployments are numbered. We decided not to go with [BGP unnumbered](https://docs.nvidia.com/networking-ethernet-software/cumulus-linux/Layer-3/Border-Gateway-Protocol-BGP/#bgp-unnumbered) since it's harder to troubleshoot network issues when dealing with iPv6 link-local underlay addresses. This is less of a problem in small-scale deployments, but we follow the same designs for small-scale and scale-out deployments.

Configuration verification:
```bash
cumulus@leaf01:mgmt:~$ nv show vrf default router bgp neighbor brief

AS - Remote Autonomous System, Afi-Safi - Address family, PfxSent - Transmitted
prefix counter, PfxRcvd - Recieved prefix counter

Neighbor     AS     State        Uptime    ResetTime  MsgRcvd  MsgSent  Afi-Safi      PfxSent  PfxRcvd
-----------  -----  -----------  --------  ---------  -------  -------  ------------  -------  -------
...
172.16.1.29  65102  established  00:28:38  1722000    577      577      ipv4-unicast  2        1
172.16.1.31  65102  established  00:28:38  1722000    577      577      ipv4-unicast  2        1
172.16.1.33  65102  established  00:28:38  1722000    577      577      ipv4-unicast  2        1
172.16.1.35  65102  established  00:28:38  1722000    577      577      ipv4-unicast  2        1
```

<!-- AIR:page -->

## BGP overlay network

The overlay network also runs on the `default` VRF. This network serves the NVE tunnels and both E/W and N/S networks. We intend to completely separate underlay and overlay networks and make the overlay more resilient to underlay link failures, so the overlay BGP peering is established between the switches’ loopback interfaces and the `ipv4` address-family is **disabled** on it (only `l2vpn-evpn` is used for this peering). 
```bash
nv set vrf default router bgp neighbor 10.10.10.2 description to-leaf02-loopback
nv set vrf default router bgp neighbor 10.10.10.2 peer-group overlay
nv set vrf default router bgp neighbor 10.10.10.2 type numbered
nv set vrf default router bgp peer-group overlay address-family ipv4-unicast enable off
nv set vrf default router bgp peer-group overlay address-family l2vpn-evpn enable on
```
This BGP peering is set within the `overlay` peer-group with `remote-as external`, `update-source`, `multihop-ttl` configuration. The BFD is set with slightly slower timers as this session is more stable anyway.
```bash
nv set vrf default router bgp peer-group overlay remote-as external
nv set vrf default router bgp peer-group overlay update-source lo
nv set vrf default router bgp peer-group overlay multihop-ttl 2
nv set vrf default router bgp peer-group overlay description overlay_interconnect
nv set vrf default router bgp peer-group overlay bfd enable on
nv set vrf default router bgp peer-group overlay bfd detect-multiplier 3
nv set vrf default router bgp peer-group overlay bfd min-rx-interval 1000
nv set vrf default router bgp peer-group overlay bfd min-tx-interval 1000
```
Configuration verification:
```bash
cumulus@leaf01:mgmt:~$ nv show vrf default router bgp neighbor brief

AS - Remote Autonomous System, Afi-Safi - Address family, PfxSent - Transmitted
prefix counter, PfxRcvd - Recieved prefix counter

Neighbor     AS     State        Uptime    ResetTime  MsgRcvd  MsgSent  Afi-Safi      PfxSent  PfxRcvd
-----------  -----  -----------  --------  ---------  -------  -------  ------------  -------  -------
10.10.10.2   65102  established  00:28:36  1722000    742      745      l2vpn-evpn    190      95
...
```
<!-- AIR:page -->

## E/W network BGP configuration

The BasePOD is designed to be a multi-tenant environment, even though by default it is used as a single-tenant deployment. All the VXLAN, BGP, and EVPN configuration we made so far is to provide an infrastructure for that. The initial state of the configuration for the E/W network is a single-tenant running on VRF `tenant1`. 

First, we must add the relevant GPU ports to the tenant VRF - `tenant1`.
```bash
nv set interface swp1s0-3,swp2s0-3,swp3s0-3,swp4s0-3 ip vrf tenant1
```
Then, to create the `tenant1` control-plane and routing configuration, we create a BGP instance for this VRF with all related global parameters – the `remote-as`, `router-id`, `ipv4`, and `l2vpn-evpn` address-families and statically set the route distinguisher (`rd`) for the VRF.
```bash
nv set vrf tenant1 router bgp enable on
nv set vrf tenant1 router bgp autonomous-system 65101
nv set vrf tenant1 router bgp router-id 10.10.10.1
nv set vrf tenant1 router bgp rd 10.10.10.1:4001
nv set vrf tenant1 router bgp address-family ipv4-unicast enable on
nv set vrf tenant1 router bgp address-family l2vpn-evpn enable on
```
**Note:** We set static `rd` so that the format for each future created VRF will be the same, and it will be easier to troubleshoot.

To reduce route advertisements, we set the SN5600 switches to advertise a single summary route. We aggregate all GPU subnets with an `/24` subnet with an `aggregate-route` configuration. Then, we set a `summary-only` setting so that no specific routes will be advertised alongside the summary route. Again, this is less significant in small-scale deployments such as BasePOD but sufficient for scale-out.
```bash
nv set vrf tenant1 router bgp address-family ipv4-unicast aggregate-route 10.1.1.0/24 summary-only on
```
As mentioned earlier, the E/W network is based on pure EVPN Type 5 routes. So, we use the `redistribute connected` statement with the previously created `dgx_subnets` route-map to insert only the GPU subnets into the `tenant1` VRF. To make all the redistributed GPU subnets EVPN Type 5 routes, we export them into EVPN using the `route-export to-evpn` configuration.
```bash
nv set vrf tenant1 router bgp address-family ipv4-unicast redistribute connected enable on
nv set vrf tenant1 router bgp address-family ipv4-unicast redistribute connected route-map dgx_subnets
nv set vrf tenant1 router bgp address-family ipv4-unicast route-export to-evpn enable on
```
Finally, we enable EVPN protocol on the VRF and assign a L3VNI. 
```bash
nv set vrf tenant1 evpn enable on
nv set vrf tenant1 evpn vni 4001
```
**Note:** For multi-tenancy, add the appropriate GPU ports to the tenant VRF and create a BGP instance using the same method described above.

Configuration verification:
```bash
cumulus@leaf01:mgmt:~$ nv show vrf tenant1 router rib
Address-family  Summary
--------------  -------------------
ipv4            Route:    0.0.0.0/0
                Route:  10.1.1.0/24
                Route:  10.1.1.0/31
                Route: 10.1.1.10/31
                Route: 10.1.1.12/31
                Route: 10.1.1.14/31
                Route: 10.1.1.16/31
                Route: 10.1.1.18/31
                Route:  10.1.1.2/31
                Route: 10.1.1.20/31
                Route: 10.1.1.22/31
                Route: 10.1.1.24/31
                Route: 10.1.1.26/31
                Route: 10.1.1.28/31
                Route: 10.1.1.30/31
                Route: 10.1.1.32/31
                Route: 10.1.1.34/31
                Route: 10.1.1.36/31
                Route: 10.1.1.38/31
                Route:  10.1.1.4/31
                Route: 10.1.1.40/31
                Route: 10.1.1.42/31
                Route: 10.1.1.44/31
                Route: 10.1.1.46/31
                Route: 10.1.1.48/31
                Route: 10.1.1.50/31
                Route: 10.1.1.52/31
                Route: 10.1.1.54/31
                Route: 10.1.1.56/31
                Route: 10.1.1.58/31
                Route:  10.1.1.6/31
                Route: 10.1.1.60/31
                Route: 10.1.1.62/31
                Route:  10.1.1.8/31
ipv6            Route:         ::/0
                Route:    fe80::/64
```
```bash
cumulus@leaf01:mgmt:~$ nv show vrf tenant1 router rib ipv4 route
Route         Protocol   Distance  ResolvedVia  ResolvedViaIntf  Uptime    NHGId  Metric  TableId  Flags
------------  ---------  --------  -----------  ---------------  --------  -----  ------  -------  ------------
0.0.0.0/0     kernel     255       reject                        00:34:42  1      8192    1003     fib-selected
                                                                                                   installed
                                                                                                   selected
10.1.1.0/24   bgp        200       blackhole                     00:34:40  1      0       1003     fib-selected
                                                                                                   installed
                                                                                                   selected
10.1.1.0/31   connected  0         swp1s0                        00:34:42  1      0       1003     fib-selected
                                                                                                   installed
                                                                                                   offloaded
                                                                                                   selected
10.1.1.2/31   bgp        20        10.10.10.2   vlan700_l3       00:34:38  1      0       1003     fib-selected
                                                                                                   installed
                                                                                                   selected
10.1.1.4/31   connected  0         swp1s1                        00:34:42  1      0       1003     fib-selected
                                                                                                   installed
                                                                                                   offloaded
                                                                                                   selected
10.1.1.6/31   bgp        20        10.10.10.2   vlan700_l3       00:34:38  1      0       1003     fib-selected
                                                                                                   installed
                                                                                                   selected
...
...
```
```bash
cumulus@leaf01:mgmt:~$ nv show vrf tenant1 evpn bgp-info
                       operational        applied
---------------------  -----------------  -------
local-vtep             10.10.10.1
rd                     10.10.10.1:4001
router-mac             48:b0:2d:a4:de:e3
system-ip              10.10.10.1
system-mac             48:b0:2d:a4:de:e3
[export-route-target]  65101:4001
[import-route-target]  65101:4001
```
```bash
cumulus@leaf01:mgmt:~$ nv show vrf tenant1 router bgp address-family l2vpn-evpn loc-rib rd 10.10.10.2:4001 route-type 5
route
========
                    ethernet-tag  evpn-prefix-str           ip         mac  path-count  prefix        Summary
    --------------  ------------  ------------------------  ---------  ---  ----------  ------------  --------------------
    0+10.1.1.0/24   0             [5]:[0]:[24]:[10.1.1.0]   10.1.1.0        1           10.1.1.0/24   Neighbor: 10.10.10.2
                                                                                                      Path:              1
    0+10.1.1.2/31   0             [5]:[0]:[31]:[10.1.1.2]   10.1.1.2        1           10.1.1.2/31   Neighbor: 10.10.10.2
                                                                                                      Path:              1
    0+10.1.1.6/31   0             [5]:[0]:[31]:[10.1.1.6]   10.1.1.6        1           10.1.1.6/31   Neighbor: 10.10.10.2
                                                                                                      Path:              1
    0+10.1.1.10/31  0             [5]:[0]:[31]:[10.1.1.10]  10.1.1.10       1           10.1.1.10/31  Neighbor: 10.10.10.2
                                                                                                      Path:              1
    0+10.1.1.14/31  0             [5]:[0]:[31]:[10.1.1.14]  10.1.1.14       1           10.1.1.14/31  Neighbor: 10.10.10.2
                                                                                                      Path:              1
    0+10.1.1.18/31  0             [5]:[0]:[31]:[10.1.1.18]  10.1.1.18       1           10.1.1.18/31  Neighbor: 10.10.10.2
                                                                                                      Path:              1
    0+10.1.1.22/31  0             [5]:[0]:[31]:[10.1.1.22]  10.1.1.22       1           10.1.1.22/31  Neighbor: 10.10.10.2
                                                                                                      Path:              1
    0+10.1.1.26/31  0             [5]:[0]:[31]:[10.1.1.26]  10.1.1.26       1           10.1.1.26/31  Neighbor: 10.10.10.2
                                                                                                      Path:              1
    0+10.1.1.30/31  0             [5]:[0]:[31]:[10.1.1.30]  10.1.1.30       1           10.1.1.30/31  Neighbor: 10.10.10.2
                                                                                                      Path:              1
    0+10.1.1.34/31  0             [5]:[0]:[31]:[10.1.1.34]  10.1.1.34       1           10.1.1.34/31  Neighbor: 10.10.10.2
                                                                                                      Path:              1
    0+10.1.1.38/31  0             [5]:[0]:[31]:[10.1.1.38]  10.1.1.38       1           10.1.1.38/31  Neighbor: 10.10.10.2
                                                                                                      Path:              1
    0+10.1.1.42/31  0             [5]:[0]:[31]:[10.1.1.42]  10.1.1.42       1           10.1.1.42/31  Neighbor: 10.10.10.2
                                                                                                      Path:              1
    0+10.1.1.46/31  0             [5]:[0]:[31]:[10.1.1.46]  10.1.1.46       1           10.1.1.46/31  Neighbor: 10.10.10.2
                                                                                                      Path:              1
    0+10.1.1.50/31  0             [5]:[0]:[31]:[10.1.1.50]  10.1.1.50       1           10.1.1.50/31  Neighbor: 10.10.10.2
                                                                                                      Path:              1
    0+10.1.1.54/31  0             [5]:[0]:[31]:[10.1.1.54]  10.1.1.54       1           10.1.1.54/31  Neighbor: 10.10.10.2
                                                                                                      Path:              1
    0+10.1.1.58/31  0             [5]:[0]:[31]:[10.1.1.58]  10.1.1.58       1           10.1.1.58/31  Neighbor: 10.10.10.2
                                                                                                      Path:              1
    0+10.1.1.62/31  0             [5]:[0]:[31]:[10.1.1.62]  10.1.1.62       1           10.1.1.62/31  Neighbor: 10.10.10.2
                                                                                                      Path:              1
```
<!-- AIR:page -->

## N/S network layer 2 configuration

As we already know, the N/S network must support layer 2 for the DGX management, BCM, k8s, and storage nodes. To enable layer 2, we create bridge domain `br_default` and set VLAN-to-VNI mapping for the EVPN-MH that will be set later for this network.  
```bash
nv set bridge domain br_default type vlan-aware
nv set bridge domain br_default vlan 121 vni 121
nv set bridge domain br_default vlan 122 vni 122
```
Then we set all switchports to the required bridge mode and assign them to the needed VLANs. BCM nodes require two layer 2 ports each to the SN5600 switches, which must be set as `access` (untagged) ports. In our example, these are `VLAN121` and `VLAN122` (BCM requires two different subnets - `internal` and `external`).
```bash
nv set interface swp30s0 bridge domain br_default access 121
nv set interface swp30s1 bridge domain br_default access 122
```
The rest of the nodes (DGX, k8s, and storage) are connected using active-active (LACP) bonds to both SN5600 switches. Those bonds are set with the general bonding configuration - `mtu`, `stp`, `lacp-bypass`, etc.
```bash
nv set interface bond1 bond member swp17s0
nv set interface bond1 description to-dgx01
nv set interface bond2 bond member swp17s1
nv set interface bond2 description to-dgx02
...
nv set interface bond5 bond member swp31s0
nv set interface bond5 description to-k8s01
...
nv set interface bond9 bond member swp34
nv set interface bond9 description to-storage02
...
nv set interface bond1-9 link mtu 9216
nv set interface bond1-9 type bond
nv set interface bond1-9 bond lacp-bypass on
nv set interface bond1-9 bond mode lacp
nv set interface bond1-9 bridge domain br_default stp admin-edge on
nv set interface bond1-9 bridge domain br_default stp auto-edge on
nv set interface bond1-9 bridge domain br_default stp bpdu-guard on
```
Then, they are set as trunk ports with all VLANs allowed. Their native (untagged) VALN is the inband-mgmt. and storage subnet VLAN - `VLAN122`.
```bash
nv set interface bond1-9 bridge domain br_default untagged 122
nv set interface bond1-9 bridge domain br_default vlan all
```

Configuration verification:
```bash
cumulus@leaf01:mgmt:~$ nv show bridge domain br_default port
port     flags                                         state
-------  --------------------------------------------  ----------
bond1    flood,learning,mcast_flood                    forwarding
bond2    flood,learning,mcast_flood                    forwarding
bond3    flood,learning,mcast_flood                    forwarding
bond4    flood,learning,mcast_flood                    forwarding
bond5    flood,learning,mcast_flood                    forwarding
bond6    flood,learning,mcast_flood                    forwarding
bond7    flood,learning,mcast_flood                    forwarding
bond8    flood,learning,mcast_flood                    forwarding
bond9    flood,learning,mcast_flood                    forwarding
swp30s0  flood,learning,mcast_flood                    forwarding
swp30s1  flood,learning,mcast_flood                    forwarding
vxlan48  flood,vlan_tunnel,neigh_suppress,mcast_flood  forwarding
```
```bash
cumulus@leaf01:mgmt:~$ nv show bridge domain br_default stp port bond1
enabled         : yes         admin-edge-port      : yes
restricted-tcn  : no          bpdu-guard-port      : yes
restricted-role : no          bpdu-guard-error     : no
port-path-cost  : 20000       bpdu-filter-port     : no
oper-edge-port  : yes         ba-inconsistent      : no
network-port    : no          auto-edge-port       : yes
mcheck          : no          admin-port-path-cost : 0
```
```bash
cumulus@leaf01:mgmt:~$ nv show bridge domain br_default vlan
     multicast.snooping.querier.source-ip  ptp.enable  Summary
---  ------------------------------------  ----------  --------
121  0.0.0.0                               off         vni: 121
122  0.0.0.0                               off         vni: 122
```
<!-- AIR:page -->

## N/S network EVPN-MH configuration

To provide a standard active-active (and multi-tenant) N/S network without the need for MLAG, we use EVPN-MH. For that, we enable the `evpn multihoming` protocol globally, configure its `startup-delay`, and statically set the L2VNI `rds`.
```bash
nv set evpn multihoming enable on
nv set evpn multihoming startup-delay 10
nv set evpn vni 121 rd 10.10.10.1:121
nv set evpn vni 122 rd 10.10.10.1:122
```
**Note:** We set static `rd` so that the format for each L2VNI created later will always be the same, and it will be easier to troubleshoot.

Each bond has its own unique local multihoming segment identifier.
```bash
nv set interface bond1 evpn multihoming segment local-id 1
nv set interface bond2 evpn multihoming segment local-id 2
...
nv set interface bond9 evpn multihoming segment local-id 9
```
The rest of the EVPN-MH bond parameters are identical for all bonds. Only one of the MH switches should be set with `segment df-preference`.
```bash
nv set interface bond1-9 evpn multihoming segment enable on
nv set interface bond1-9 evpn multihoming segment df-preference 50000
nv set interface bond1-9 evpn multihoming segment mac-address 44:38:39:BE:EF:AA
```
The inter-switch layer 3 ports will serve as the EVPN-MH uplinks.
```bash
nv set interface swp61-64 evpn multihoming uplink on
```

Configuration verification:
```bash
cumulus@leaf01:mgmt:~$ nv show evpn vni

NumMacs - Number of MACs (local and remote) known for this VNI, NumArps - Number
of ARPs (IPv4 and IPv6, local and remote) known for this VNI
, NumRemVteps - Number of Remote Vteps

VNI  NumMacs  NumArps  NumRemVteps  TenantVrf
---  -------  -------  -----------  --------------
121  4        2        1            inband_storage
122  30       10       1            inband_storage
```
```bash
cumulus@leaf01:mgmt:~$ nv show interface bond1 evpn multihoming segment
               operational  applied
-------------  -----------  -----------------
enable                      on
df-preference               50000
local-id                    1
mac-address                 44:38:39:BE:EF:AA
```
```bash
cumulus@leaf01:mgmt:~$ nv show evpn access-vlan-info vlan 122
                        operational  applied
----------------------  -----------  -------
member-interface-count  9
vni                     122
vni-count               1
vxlan-interface         vxlan48

member-interface
===================
    -----
    bond1
    bond2
    bond3
    bond4
    bond5
    bond6
    bond7
    bond8
    bond9
```
<!-- AIR:page -->

## N/S network VRR configuration

To enable the N/S layer 2 network route outside the BasePOD (or between subnets within it), we set gateways to the VLANs (`VLAN121` and `VLAN122`). To provide an active-active and redundant gateway, we use VRR. 
```bash
nv set router vrr enable on
```
Each VLAN has a virtual-IP and virtual-MAC addresses that will be used as the subnet gateways. We use typical VRR configuration with an SVI and virtual addresses.
```bash
nv set interface vlan121 vlan 121
nv set interface vlan121 ip address 10.130.121.2/24
nv set interface vlan121 ip vrr address 10.130.121.1/24
nv set interface vlan121 ip vrr mac-address 00:00:00:00:01:21
nv set interface vlan122 vlan 122
nv set interface vlan122 ip address 10.130.122.2/24
nv set interface vlan122 ip vrr address 10.130.122.1/24
nv set interface vlan122 ip vrr mac-address 00:00:00:00:01:22
nv set interface vlan121-122 type svi
nv set interface vlan121-122 ip vrr enable on
nv set interface vlan121-122 ip vrr state up
```
Those SVIs then must be within the N/S netowork `inband_storage` VRF.
```bash
nv set interface vlan121-122 ip vrf inband_storage
```

Configuration verification:
```bash
cumulus@leaf01:mgmt:~$ nv show interface vlan122 ip vrr
             operational               applied
-----------  ------------------------  -----------------
enable                                 on
mac-address  00:00:00:00:01:22         00:00:00:00:01:22
mac-id                                 none
[address]    10.130.122.1/24           10.130.122.1/24
[address]    fe80::200:ff:fe00:122/64
state        up  
```

<!-- AIR:page -->

## N/S network BGP configuration

The N/S network BGP configuration is similar to the E/W (single-tenant). It runs on VRF `inband_storage`, and to enable its control-plane and routing, we create a separate BGP instance for this VRF with all related global parameters – the `remote-as`, `router-id`, `ipv4`, and `l2vpn-evpn` address-families and statically set the route distinguisher (`rd`) for the VRF.
```bash
nv set vrf inband_storage router bgp enable on
nv set vrf inband_storage router bgp autonomous-system 65101
nv set vrf inband_storage router bgp router-id 10.10.10.1
nv set vrf inband_storage router bgp rd 10.10.10.1:4000
nv set vrf inband_storage router bgp address-family ipv4-unicast enable on
nv set vrf inband_storage router bgp address-family l2vpn-evpn enable on
```
**Note:** We set static `rd` so that the format for each future create VRF will always be the same, and it will be easier to troubleshoot.

We set a single summary route for this VRF to reduce route advertisements to the data center. We aggregate all inband subnets (in our case, a single subnet) with an `/16` prefix. Then, we set a `summary-only` configuration so no specific routes will be advertised alongside the summary route. 
```bash
nv set vrf inband_storage router bgp address-family ipv4-unicast aggregate-route 10.130.0.0/16 summary-only on
```
Then, we use the `redistribute connected` statement with the previously created `inband_subnets` route-map to insert only the inband subnets into the `inband_storage` VRF (no loopback, uplinks, etc.). 
```bash
nv set vrf inband_storage router bgp address-family ipv4-unicast redistribute connected enable on
nv set vrf inband_storage router bgp address-family ipv4-unicast redistribute connected route-map inband_subnets
```
Finally, we enable EVPN protocol on the VRF and assign a L3VNI. 
```bash
nv set vrf inband_storage evpn enable on
nv set vrf inband_storage evpn vni 4000
```
**Note:** For multi-tenancy, create a BGP instance for each tenant VRF using the same method and add the appropriate SVIs.

Configuration verification:
```bash
cumulus@leaf01:mgmt:~$ nv show vrf inband_storage router rib ipv4 route
Route            Protocol   Distance  ResolvedVia  ResolvedViaIntf  Uptime    NHGId  Metric  TableId  Flags
---------------  ---------  --------  -----------  ---------------  --------  -----  ------  -------  ------------
...
10.130.0.0/16    bgp        200       blackhole                     01:12:42  1      0       1002     fib-selected
...
...
```
```bash
cumulus@leaf01:mgmt:~$ nv show vrf inband_storage evpn bgp-info
                       operational        applied
---------------------  -----------------  -------
local-vtep             10.10.10.1
rd                     10.10.10.1:4000
router-mac             48:b0:2d:a4:de:e3
system-ip              10.10.10.1
system-mac             48:b0:2d:a4:de:e3
[export-route-target]  65101:4000
[import-route-target]  65101:4000
```
<!-- AIR:page -->

## IPMI and edge networks configuration

Each of the SN5600 switches has four additional router ports. Two for IPMI switches uplinks, and two for the edge switches connection. In this demo, the IP addresses for those ports are also based on a p2p (`/31`).

To IPMI:
```bash
nv set interface swp29s0 ip address 10.150.0.0/31
nv set interface swp29s1 ip address 10.150.0.2/31
```
To edge:
```bash
nv set interface swp45 ip address 10.140.0.0/31
nv set interface swp46 ip address 10.140.0.2/31
```
All these port subnets are within the `inband_storage` VRF as the N/S and the OOB-mgmt. networks must be accessible from the data center.
```bash
nv set interface swp29s0-1,swp45-46 ip vrf inband_storage
```
Then, within the `inband_storage` VRF BGP instance, sessions are established over those links to the IPMI and edge switches. 
```bash
nv set vrf inband_storage router bgp neighbor 10.140.0.1 description to-edge01-swp1
nv set vrf inband_storage router bgp neighbor 10.140.0.1 peer-group ipmi_edge
nv set vrf inband_storage router bgp neighbor 10.140.0.1 type numbered
...
...
nv set vrf inband_storage router bgp neighbor 10.150.0.3 description to-ipmi02-swp49
nv set vrf inband_storage router bgp neighbor 10.150.0.3 peer-group ipmi_edge
nv set vrf inband_storage router bgp neighbor 10.150.0.3 type numbered
```
We put these neighbors into a separate `ipmi_edge` peer-group and set `remote-as`, description, and BFD parameters.
```bash
nv set vrf inband_storage router bgp peer-group ipmi_edge remote-as external
nv set vrf inband_storage router bgp peer-group ipmi_edge description ipmi_edge_interconnect
nv set vrf inband_storage router bgp peer-group ipmi_edge bfd enable on
nv set vrf inband_storage router bgp peer-group ipmi_edge bfd detect-multiplier 3
nv set vrf inband_storage router bgp peer-group ipmi_edge bfd min-rx-interval 300
nv set vrf inband_storage router bgp peer-group ipmi_edge bfd min-tx-interval 300
```

Configuration verification:
```bash
cumulus@leaf01:mgmt:~$ nv show vrf inband_storage router bgp neighbor

AS - Remote Autonomous System, Afi-Safi - Address family, PfxSent - Transmitted
prefix counter, PfxRcvd - Recieved prefix counter

Neighbor    AS     State        Uptime    ResetTime  MsgRcvd  MsgSent  Afi-Safi      PfxSent  PfxRcvd
----------  -----  -----------  --------  ---------  -------  -------  ------------  -------  -------
10.140.0.1  65106  established  10:51:15  48056000   13030    13063    ipv4-unicast  3        1
10.140.0.3  65107  established  10:51:15  48056000   13030    13031    ipv4-unicast  3        1
10.150.0.1  65104  established  11:06:45  48056000   13341    13341    ipv4-unicast  3        1
10.150.0.3  65105  established  11:06:45  48056000   13340    13341    ipv4-unicast  3        1
```
```bash
cumulus@leaf01:mgmt:~$ nv show vrf inband_storage router rib
Address-family  Summary
--------------  ----------------------
ipv4            Route:       0.0.0.0/0
                Route: 10.100.100.0/32
                Route:   10.130.0.0/16
                Route: 10.130.121.0/24
                Route: 10.130.122.0/24
                Route:   10.140.0.0/31
                Route:   10.140.0.2/31
                Route:   10.150.0.0/31
                Route:   10.150.0.2/31
                Route: 10.200.200.0/32
ipv6            Route:            ::/0
                Route:       fe80::/64
```
```bash
cumulus@leaf01:mgmt:~$ nv show vrf inband_storage router rib ipv4 route
Route            Protocol   Distance  ResolvedVia  ResolvedViaIntf  Uptime    NHGId  Metric  TableId  Flags
---------------  ---------  --------  -----------  ---------------  --------  -----  ------  -------  ------------
...
10.100.100.0/32  bgp        20        10.150.0.1   swp29s0          01:12:20  2      0       1002     fib-selected
                                      10.150.0.3   swp29s1                                            installed
                                                                                                      selected
...
...
10.200.200.0/32  bgp        20        10.140.0.1   swp45            01:12:00  2      0       1002     fib-selected
                                      10.140.0.3   swp46                                              installed
                                                                                                      selected
```
**Note:** In this demo, we only simulate IPMI and data center networks by redistributing their switches’ loopback addresses into the BasePOD N/S network.

To ensure both uplinks (for IPMI and edge) are used to route traffic, we use the `multipath aspath-ignore` setting as both peers use different ASNs.
```bash
nv set vrf inband_storage router bgp path-selection multipath aspath-ignore on
```
Configuration verification:

IPMI subent:
```bash
cumulus@leaf01:mgmt:~$ nv show vrf inband_storage router rib ipv4 route 10.100.100.0/32  
protocol
===========
    Protocol  EntryIdx  TblId  NHGId  Distance  Metric  ResolvedViaIntf  Weight  ResolvedViaInfo
    --------  --------  -----  -----  --------  ------  ---------------  ------  ---------------
    bgp       1         1002   2      20        0       swp29s0          1
                                                        swp29s1          1
```
Edge (DC) subnet:
```bash
cumulus@leaf01:mgmt:~$ nv show vrf inband_storage router rib ipv4 route 10.200.200.0/32
protocol
===========
    Protocol  EntryIdx  TblId  NHGId  Distance  Metric  ResolvedViaIntf  Weight  ResolvedViaInfo
    --------  --------  -----  -----  --------  ------  ---------------  ------  ---------------
    bgp       1         1002   2      20        0       swp45            1
                                                        swp46            1
```

<!-- AIR:page -->

## E/W and N/S networks connectivity test

To test E/W network all-to-all GPU connectivity, we placed a bash script named `ping_test.sh` on the `dgx01` node. This script sends 2 ICMP packets using the ping command to all DGX NICs with the source of each of the `dgx01` NICs.

Run the script to verify E/W all-to-all connectivity.
```bash
ubuntu@dgx01:~$ ./ping_test.sh
PING 10.1.1.0 (10.1.1.0) from 10.1.1.0 : 56(84) bytes of data.
64 bytes from 10.1.1.0: icmp_seq=1 ttl=64 time=0.016 ms
64 bytes from 10.1.1.0: icmp_seq=2 ttl=64 time=0.038 ms

--- 10.1.1.0 ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1025ms
rtt min/avg/max/mdev = 0.016/0.027/0.038/0.011 ms
Ping result from 10.1.1.0 to 10.1.1.0: 0
PING 10.1.1.0 (10.1.1.0) from 10.1.1.2 : 56(84) bytes of data.
64 bytes from 10.1.1.0: icmp_seq=1 ttl=64 time=0.085 ms
64 bytes from 10.1.1.0: icmp_seq=2 ttl=64 time=0.039 ms

--- 10.1.1.0 ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1021ms
rtt min/avg/max/mdev = 0.039/0.062/0.085/0.023 ms
Ping result from 10.1.1.2 to 10.1.1.0: 0
PING 10.1.1.0 (10.1.1.0) from 10.1.1.4 : 56(84) bytes of data.
64 bytes from 10.1.1.0: icmp_seq=1 ttl=64 time=0.011 ms
64 bytes from 10.1.1.0: icmp_seq=2 ttl=64 time=0.039 ms
...
...
```
Ensure there is no connectivity between the E/W and the N/S networks - the GPU NICs in `tenant1` VRF to the nodes in `inband_storage` VRF.
```bash
ubuntu@dgx01:~$ ping 10.130.122.25 -I 10.1.1.0 -c 3
PING 10.130.122.25 (10.130.122.25) from 10.1.1.0 : 56(84) bytes of data.

--- 10.130.122.25 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2034ms

ubuntu@dgx01:~$ ping 10.130.122.101 -I 10.1.1.2 -c 3
PING 10.130.122.101 (10.130.122.101) from 10.1.1.2 : 56(84) bytes of data.

--- 10.130.122.101 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2026ms
```

A similar script (`./ping_test.sh`) is also placed on the `bcm01` node. By running it, verify all-to-all N/S network connectivity within the `inband_storage` VRF.
```bash
ubuntu@bcm01:~$ ./ping_test.sh
PING 10.130.122.254 (10.130.122.254) from 10.130.122.254 : 56(84) bytes of data.
64 bytes from 10.130.122.254: icmp_seq=1 ttl=64 time=0.077 ms
64 bytes from 10.130.122.254: icmp_seq=2 ttl=64 time=0.043 ms

--- 10.130.122.254 ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1016ms
rtt min/avg/max/mdev = 0.043/0.060/0.077/0.017 ms
Ping result from 10.130.122.254 to 10.130.122.254: 0
PING 10.130.122.253 (10.130.122.253) from 10.130.122.254 : 56(84) bytes of data.
64 bytes from 10.130.122.253: icmp_seq=1 ttl=64 time=2.84 ms
64 bytes from 10.130.122.253: icmp_seq=2 ttl=64 time=1.52 ms

--- 10.130.122.253 ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1001ms
rtt min/avg/max/mdev = 1.523/2.182/2.841/0.659 ms
Ping result from 10.130.122.254 to 10.130.122.253: 0
PING 10.130.122.5 (10.130.122.5) from 10.130.122.254 : 56(84) bytes of data.
64 bytes from 10.130.122.5: icmp_seq=1 ttl=64 time=1.53 ms
64 bytes from 10.130.122.5: icmp_seq=2 ttl=64 time=0.894 ms
...
...
```

<!-- AIR:page -->

## Demo configuration recovery

If you made configuration changes to the demo environment and wish to revert all to the initial state, you can use the `basepod_config.yml` ansible-playbook located in the `cumulus_ansible_modules` folder on the `oob-mgmt-server`.
```bash
ubuntu@oob-mgmt-server:~$ cd cumulus_ansible_modules
ubuntu@oob-mgmt-server:~/cumulus_ansible_modules$ ansible-playbook playbooks/basepod_config.yml -i inventories/rail_optimized/hosts
```

THE END.