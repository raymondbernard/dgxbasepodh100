
nv config show
nv config show -o commands
cat /etc/nvue.d/startup.yaml

## IP addressing  

# As mentioned, the E/W network is a pure layer 3 network with p2p (/31) IPv4 addresses between the GPU NICs and the switches. Each GPU-switch port is a separate subnet but from a single supernet. All switch ports 
# connected to GPU NICs are breakout x4.
nv set interface swp1s0 ip address 10.1.1.1/31
nv set interface swp1s1 ip address 10.1.1.5/31
nv set interface swp1s2 ip address 10.1.1.9/31
nv set interface swp1s3 ip address 10.1.1.13/31
nv set interface swp2s0 ip address 10.1.1.17/31
nv set interface swp2s1 ip address 10.1.1.21/31

nv set interface swp4s2 ip address 10.1.1.57/31
nv set interface swp4s3 ip address 10.1.1.61/31


# The inter-switch ports are router ports with a different p2p (`/31`) subnet each. But from a different supernet than the compute network GPU ports. 
nv set interface swp61 ip address 172.16.1.28/31
nv set interface swp62 ip address 172.16.1.30/31
nv set interface swp63 ip address 172.16.1.32/31
nv set interface swp64 ip address 172.16.1.34/31


# The N/S network is a layer 2 network, but for the nodes within it to be able to communicate with the outside world (data center), we enable layer 3 VLAN interfaces ([SVI](https://docs.nvidia.com/
#  networking-ethernet-software/cumulus-linux/Layer-2/Ethernet-Bridging-VLANs/VLAN-aware-Bridge-Mode/#vlan-layer-3-addressing)) that will later be used for VRR instances.


nv set interface vlan121 ip address 10.130.121.2/24
nv set interface vlan122 ip address 10.130.122.2/24


# Each SN5600 switch has ports to the two IPMI and two edge switches. All those ports are router ports within different subnets. Later, we will establish BGP neighborships on those ports.

# To IPMI switches:
nv set interface swp29s0 ip address 10.150.0.0/31
nv set interface swp29s1 ip address 10.150.0.2/31

# to edge switches:
nv set interface swp45 ip address 10.140.0.0/31
nv set interface swp46 ip address 10.140.0.2/31

# **Note:** In the demo, we assume p2p (/31) addresses the edge switches, but it depends on the existing data center network.

# Finally, we have the loopback addresses of each switch.

nv set interface lo ip address 10.10.10.1/32


# Configuration verification:

nv show interface | grep 10

## Global configuration

# To ensure proper BasePOD configuration, we must enable these global configurations:
#  Lossless [RoCE](https://docs.nvidia.com/networking-ethernet-software/cumulus-linux/Layer-1-and-Switch-Ports/Quality-of-Service/RDMA-over-Converged-Ethernet-RoCE/)

nv set qos roce enable on
nv set qos roce mode lossless

# Configuration verification:

nv show qos roce
          
#  BGP and EVPN protocols

nv set router bgp enable on
nv set evpn enable on

# We also enable [Graceful BGP Restart](https://docs.nvidia.com/networking-ethernet-software/cumulus-linux/Layer-3/Border-Gateway-Protocol-BGP/Optional-BGP-Configuration/#graceful-bgp-restart).

nv set router bgp graceful-restart mode helper-only

# NVE interface and its parameters (ARP/ND suppress and tunnel source with loopback address)

nv set nve vxlan enable on
nv set nve vxlan arp-np-suppress on
nv set nve vxlan source address 10.10.10.1


## Routing policies

# The first IP prefix-list is set to match all GPU (`/31`) subnets 
nv set router policy prefix-list dgx_subnet rule 10 action permit
nv set router policy prefix-list dgx_subnet rule 10 match 10.1.1.0/24 max-prefix-len 31
nv set router policy prefix-list dgx_subnet type ipv4
# Configuration verification:
nv show router policy prefix-list dgx_subnet rule 10

# Then this prefix-list is used within a route-map which will later be attached to the BGP `redistribute connected` statement into the `tenant1` VRF so that only those subnets will be injected as Type 5 routes into EVPN # # (BGP and EVPN configuration is covered later).

nv set router policy route-map dgx_subnets rule 10 action permit
nv set router policy route-map dgx_subnets rule 10 description permit_dgx_subnet
nv set router policy route-map dgx_subnets rule 10 match ip-prefix-list dgx_subnet
nv set router policy route-map dgx_subnets rule 10 match type ipv4

# Configuration verification:

nv show router policy route-map dgx_subnets rule 10

# The second IP prefix-list matches all inband management network subnets.
nv set router policy prefix-list inband_subnets rule 10 action permit
nv set router policy prefix-list inband_subnets rule 10 match 10.130.0.0/16 max-prefix-len 24
nv set router policy prefix-list inband_subnets type ipv4

# Configuration verification:

# nnv show router policy prefix-list inband_subnets rule 10
# Then, it is used within the route-map, which will be attached to the BGP `redistribute connected` statement into the `inband_storage` VRF.
nv set router policy route-map inband_subnets rule 10 action permit
nv set router policy route-map inband_subnets rule 10 description permit_dgx_subnet
nv set router policy route-map inband_subnets rule 10 match ip-prefix-list inband_subnets
nv set router policy route-map inband_subnets rule 10 match type ipv4

# Configuration verification:
nv show router policy route-map inband_subnets rule 10
              
# And the 3rd route-map matches the lo interface (loopback IPv4 address). This route-map will be later attached to the BGP `redistribute connected` statement into the `default` VRF. This address will be used for the NVE # # tunnel over the underlay network.

nv set router policy route-map lo_subnet rule 10 action permit
nv set router policy route-map lo_subnet rule 10 description permit_lo_subnet
nv set router policy route-map lo_subnet rule 10 match interface lo
nv set router policy route-map lo_subnet rule 10 match type ipv4

# Configuration verification:
nv show router policy route-map lo_subnet rule 10

# **Note:** When setting up a multi-tenant environment, you will need more route-maps per tenant VRF.
## BGP underlay network

# The underlay network is set on the `default` VRF. Although the E/W and the N/S use EVPN in different flavors, this underlay will serve both networks. 

# We start with the basic BGP configuration on VRF `default` with the `ipv4` and `l2vpn-evpn` address-families, then the `redistribute connected` with the `lo_subnet` route-map attached.
nv set vrf default router bgp enable on
nv set vrf default router bgp autonomous-system 65101
nv set vrf default router bgp router-id 10.10.10.1
nv set vrf default router bgp address-family ipv4-unicast enable on
nv set vrf default router bgp address-family ipv4-unicast redistribute connected enable on
nv set vrf default router bgp address-family ipv4-unicast redistribute connected route-map lo_subnet
nv set vrf default router bgp address-family l2vpn-evpn enable on

# Then, we set the BGP underlay neighbors (the inter-switch p2p links). Each neighbor has a `to-<peer switch>-<peer port>` description for easier troubleshooting, and all underlay neighbors are put within the `undelay` # # peer-group to set all BGP parameters on a single entity.  
nv set vrf default router bgp neighbor 172.16.1.29 description to-leaf02-swp61
nv set vrf default router bgp neighbor 172.16.1.29 peer-group underlay
nv set vrf default router bgp neighbor 172.16.1.29 type numbered

nv set vrf default router bgp neighbor 172.16.1.35 description to-leaf02-swp64
nv set vrf default router bgp neighbor 172.16.1.35 peer-group underlay
nv set vrf default router bgp neighbor 172.16.1.35 type numbered

# The peer-group is set with the `remote-as external` for eBGP, description, and a 3x300 [BFD](https://docs.nvidia.com/networking-ethernet-software/cumulus-linux/Layer-3/Bidirectional-Forwarding-Detection-BFD/) for faster port failures detection.

nv set vrf default router bgp peer-group underlay remote-as external
nv set vrf default router bgp peer-group underlay description underlay_interconnect
nv set vrf default router bgp peer-group underlay bfd enable on
nv set vrf default router bgp peer-group underlay bfd detect-multiplier 3
nv set vrf default router bgp peer-group underlay bfd min-rx-interval 300
nv set vrf default router bgp peer-group underlay bfd min-tx-interval 300

# **Note:** All BGP neighbors we use in our deployments are numbered. We decided not to go with [BGP unnumbered](https://docs.nvidia.com/networking-ethernet-software/cumulus-linux/Layer-3/Border-Gateway-Protocol-BGP/#bgp-unnumbered) since it's harder to troubleshoot network issues when dealing with iPv6 link-local underlay addresses. This is less of a problem in small-scale deployments, but we follow the same designs for small-scale and scale-out deployments.

# Configuration verification:

nv show vrf default router bgp neighbor brief

# AS - Remote Autonomous System, Afi-Safi - Address family, PfxSent - Transmitted
# prefix counter, PfxRcvd - Recieved prefix counter

## BGP overlay network

# The overlay network also runs on the `default` VRF. This network serves the NVE tunnels and both E/W and N/S networks. We intend to completely separate underlay and overlay networks and make the overlay more resilient to underlay link failures, so the overlay BGP peering is established between the switches’ loopback interfaces and the `ipv4` address-family is **disabled** on it (only `l2vpn-evpn` is used for this peering). 
nv set vrf default router bgp neighbor 10.10.10.2 description to-leaf02-loopback
nv set vrf default router bgp neighbor 10.10.10.2 peer-group overlay
nv set vrf default router bgp neighbor 10.10.10.2 type numbered
nv set vrf default router bgp peer-group overlay address-family ipv4-unicast enable off
nv set vrf default router bgp peer-group overlay address-family l2vpn-evpn enable on

# This BGP peering is set within the `overlay` peer-group with `remote-as external`, `update-source`, `multihop-ttl` configuration. The BFD is set with slightly slower timers as this session is more stable anyway.

nv set vrf default router bgp peer-group overlay remote-as external
nv set vrf default router bgp peer-group overlay update-source lo
nv set vrf default router bgp peer-group overlay multihop-ttl 2
nv set vrf default router bgp peer-group overlay description overlay_interconnect
nv set vrf default router bgp peer-group overlay bfd enable on
nv set vrf default router bgp peer-group overlay bfd detect-multiplier 3
nv set vrf default router bgp peer-group overlay bfd min-rx-interval 1000
nv set vrf default router bgp peer-group overlay bfd min-tx-interval 1000

# Configuration verification:
nv show vrf default router bgp neighbor brief

# AS - Remote Autonomous System, Afi-Safi - Address family, PfxSent - Transmitted
# prefix counter, PfxRcvd - Recieved prefix counter


## E/W network BGP configuration

# The BasePOD is designed to be a multi-tenant environment, even though by default it is used as a single-tenant deployment. All the VXLAN, BGP, and EVPN configuration we made so far is to provide an infrastructure for that. The initial state of the configuration for the E/W network is a single-tenant running on VRF `tenant1`. 

# First, we must add the relevant GPU ports to the tenant VRF - `tenant1`.
nv set interface swp1s0-3,swp2s0-3,swp3s0-3,swp4s0-3 ip vrf tenant1

# Then, to create the `tenant1` control-plane and routing configuration, we create a BGP instance for this VRF with all related global parameters – the `remote-as`, `router-id`, `ipv4`, and `l2vpn-evpn` address-families and statically set the route distinguisher (`rd`) for the VRF.

nv set vrf tenant1 router bgp enable on
nv set vrf tenant1 router bgp autonomous-system 65101
nv set vrf tenant1 router bgp router-id 10.10.10.1
nv set vrf tenant1 router bgp rd 10.10.10.1:4001
nv set vrf tenant1 router bgp address-family ipv4-unicast enable on
nv set vrf tenant1 router bgp address-family l2vpn-evpn enable on

# **Note:** We set static `rd` so that the format for each future created VRF will be the same, and it will be easier to troubleshoot.

# To reduce route advertisements, we set the SN5600 switches to advertise a single summary route. We aggregate all GPU subnets with an `/24` subnet with an `aggregate-route` configuration. Then, we set a `summary-only` setting so that no specific routes will be advertised alongside the summary route. Again, this is less significant in small-scale deployments such as BasePOD but sufficient for scale-out.
nv set vrf tenant1 router bgp address-family ipv4-unicast aggregate-route 10.1.1.0/24 summary-only on

# As mentioned earlier, the E/W network is based on pure EVPN Type 5 routes. So, we use the `redistribute connected` statement with the previously created `dgx_subnets` route-map to insert only the GPU subnets into the `tenant1` VRF. To make all the redistributed GPU subnets EVPN Type 5 routes, we export them into EVPN using the `route-export to-evpn` configuration.

nv set vrf tenant1 router bgp address-family ipv4-unicast redistribute connected enable on
nv set vrf tenant1 router bgp address-family ipv4-unicast redistribute connected route-map dgx_subnets
nv set vrf tenant1 router bgp address-family ipv4-unicast route-export to-evpn enable on

# Finally, we enable EVPN protocol on the VRF and assign a L3VNI. 

nv set vrf tenant1 evpn enable on
nv set vrf tenant1 evpn vni 4001

# **Note:** For multi-tenancy, add the appropriate GPU ports to the tenant VRF and create a BGP instance using the same method described above.

# Configuration verification:

nv show vrf tenant1 router rib

# nv show vrf tenant1 router rib ipv4 route

# nv show vrf tenant1 evpn bgp-info


# nv show vrf tenant1 router bgp address-family l2vpn-evpn loc-rib rd 10.10.10.2:4001 route-type 5


## N/S network layer 2 configuration

# As we already know, the N/S network must support layer 2 for the DGX management, BCM, k8s, and storage nodes. To enable layer 2, we create bridge domain `br_default` and set VLAN-to-VNI mapping for the EVPN-MH that will be set later for this network.  

nv set bridge domain br_default type vlan-aware
nv set bridge domain br_default vlan 121 vni 121
nv set bridge domain br_default vlan 122 vni 122

# Then we set all switchports to the required bridge mode and assign them to the needed VLANs. BCM nodes require two layer 2 ports each to the SN5600 switches, which must be set as `access` (untagged) ports. In our example, these are `VLAN121` and `VLAN122` (BCM requires two different subnets - `internal` and `external`).

nv set interface swp30s0 bridge domain br_default access 121
nv set interface swp30s1 bridge domain br_default access 122

# The rest of the nodes (DGX, k8s, and storage) are connected using active-active (LACP) bonds to both SN5600 switches. Those bonds are set with the general bonding configuration - `mtu`, `stp`, `lacp-bypass`, etc.

nv set interface bond1 bond member swp17s0
nv set interface bond1 description to-dgx01
nv set interface bond2 bond member swp17s1
nv set interface bond2 description to-dgx02

nv set interface bond5 bond member swp31s0
nv set interface bond5 description to-k8s01

nv set interface bond9 bond member swp34
nv set interface bond9 description to-storage02

nv set interface bond1-9 link mtu 9216
nv set interface bond1-9 type bond
nv set interface bond1-9 bond lacp-bypass on
nv set interface bond1-9 bond mode lacp
nv set interface bond1-9 bridge domain br_default stp admin-edge on
nv set interface bond1-9 bridge domain br_default stp auto-edge on
nv set interface bond1-9 bridge domain br_default stp bpdu-guard on


# Then, they are set as trunk ports with all VLANs allowed. Their native (untagged) VALN is the inband-mgmt. and storage subnet VLAN - `VLAN122`.
nv set interface bond1-9 bridge domain br_default untagged 122
nv set interface bond1-9 bridge domain br_default vlan all

# Configuration verification:
nv show bridge domain br_default port
nv show bridge domain br_default stp port bond1
nv show bridge domain br_default vlan


## N/S network EVPN-MH configuration

# To provide a standard active-active (and multi-tenant) N/S network without the need for MLAG, we use EVPN-MH. For that, we enable the `evpn multihoming` protocol globally, configure its `startup-delay`, and statically set the L2VNI `rds`.
nv set evpn multihoming enable on
nv set evpn multihoming startup-delay 10
nv set evpn vni 121 rd 10.10.10.1:121
nv set evpn vni 122 rd 10.10.10.1:122

# **Note:** We set static `rd` so that the format for each L2VNI created later will always be the same, and it will be easier to troubleshoot.

# Each bond has its own unique local multihoming segment identifier.
nv set interface bond1 evpn multihoming segment local-id 1
nv set interface bond2 evpn multihoming segment local-id 2

nv set interface bond9 evpn multihoming segment local-id 9
# The rest of the EVPN-MH bond parameters are identical for all bonds. Only one of the MH switches should be set with `segment df-preference`.
nv set interface bond1-9 evpn multihoming segment enable on
nv set interface bond1-9 evpn multihoming segment df-preference 50000
nv set interface bond1-9 evpn multihoming segment mac-address 44:38:39:BE:EF:AA


# The inter-switch layer 3 ports will serve as the EVPN-MH uplinks.
nv set interface swp61-64 evpn multihoming uplink on

# Configuration verification:
nv show evpn vni


nv show interface bond1 evpn multihoming segment

nv show evpn access-vlan-info vlan 122


## N/S network VRR configuration

# To enable the N/S layer 2 network route outside the BasePOD (or between subnets within it), we set gateways to the VLANs (`VLAN121` and `VLAN122`). To provide an active-active and redundant gateway, we use VRR. 

nv set router vrr enable on

# Each VLAN has a virtual-IP and virtual-MAC addresses that will be used as the subnet gateways. We use typical VRR configuration with an SVI and virtual addresses.

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

# Those SVIs then must be within the N/S netowork `inband_storage` VRF.
nv set interface vlan121-122 ip vrf inband_storage

# Configuration verification:

nv show interface vlan122 ip vrr

## N/S network BGP configuration

# The N/S network BGP configuration is similar to the E/W (single-tenant). It runs on VRF `inband_storage`, and to enable its control-plane and routing, we create a separate BGP instance for this VRF with all related global parameters – the `remote-as`, `router-id`, `ipv4`, and `l2vpn-evpn` address-families and statically set the route distinguisher (`rd`) for the VRF.
nv set vrf inband_storage router bgp enable on
nv set vrf inband_storage router bgp autonomous-system 65101
nv set vrf inband_storage router bgp router-id 10.10.10.1
nv set vrf inband_storage router bgp rd 10.10.10.1:4000
nv set vrf inband_storage router bgp address-family ipv4-unicast enable on
nv set vrf inband_storage router bgp address-family l2vpn-evpn enable on

# **Note:** We set static `rd` so that the format for each future create VRF will always be the same, and it will be easier to troubleshoot.

# We set a single summary route for this VRF to reduce route advertisements to the data center. We aggregate all inband subnets (in our case, a single subnet) with an `/16` prefix. Then, we set a `summary-only` configuration so no specific routes will be advertised alongside the summary route. 
nv set vrf inband_storage router bgp address-family ipv4-unicast aggregate-route 10.130.0.0/16 summary-only on

# Then, we use the `redistribute connected` statement with the previously created `inband_subnets` route-map to insert only the inband subnets into the `inband_storage` VRF (no loopback, uplinks, etc.). 
nv set vrf inband_storage router bgp address-family ipv4-unicast redistribute connected enable on
nv set vrf inband_storage router bgp address-family ipv4-unicast redistribute connected route-map inband_subnets

# Finally, we enable EVPN protocol on the VRF and assign a L3VNI. 
nv set vrf inband_storage evpn enable on
nv set vrf inband_storage evpn vni 4000

# **Note:** For multi-tenancy, create a BGP instance for each tenant VRF using the same method and add the appropriate SVIs.

# Configuration verification:
nv show vrf inband_storage router rib ipv4 route

nv show vrf inband_storage evpn bgp-info
           

## IPMI and edge networks configuration

Each of the SN5600 switches has four additional router ports. Two for IPMI switches uplinks, and two for the edge switches connection. In this demo, the IP addresses for those ports are also based on a p2p (`/31`).

# To IPMI:
nv set interface swp29s0 ip address 10.150.0.0/31
nv set interface swp29s1 ip address 10.150.0.2/31
# To edge:
nv set interface swp45 ip address 10.140.0.0/31
nv set interface swp46 ip address 10.140.0.2/31

# All these port subnets are within the `inband_storage` VRF as the N/S and the OOB-mgmt. networks must be accessible from the data center.

nv set interface swp29s0-1,swp45-46 ip vrf inband_storage

# Then, within the `inband_storage` VRF BGP instance, sessions are established over those links to the IPMI and edge switches. 

nv set vrf inband_storage router bgp neighbor 10.140.0.1 description to-edge01-swp1
nv set vrf inband_storage router bgp neighbor 10.140.0.1 peer-group ipmi_edge
nv set vrf inband_storage router bgp neighbor 10.140.0.1 type numbered

nv set vrf inband_storage router bgp neighbor 10.150.0.3 description to-ipmi02-swp49
nv set vrf inband_storage router bgp neighbor 10.150.0.3 peer-group ipmi_edge
nv set vrf inband_storage router bgp neighbor 10.150.0.3 type numbered

# We put these neighbors into a separate `ipmi_edge` peer-group and set `remote-as`, description, and BFD parameters.
nv set vrf inband_storage router bgp peer-group ipmi_edge remote-as external
nv set vrf inband_storage router bgp peer-group ipmi_edge description ipmi_edge_interconnect
nv set vrf inband_storage router bgp peer-group ipmi_edge bfd enable on
nv set vrf inband_storage router bgp peer-group ipmi_edge bfd detect-multiplier 3
nv set vrf inband_storage router bgp peer-group ipmi_edge bfd min-rx-interval 300
nv set vrf inband_storage router bgp peer-group ipmi_edge bfd min-tx-interval 300


# Configuration verification

nv show vrf inband_storage router bgp neighbor

# AS - Remote Autonomous System, Afi-Safi - Address family, PfxSent - Transmitted
# prefix counter, PfxRcvd - Recieved prefix counter


nv show vrf inband_storage router rib

nv show vrf inband_storage router rib ipv4 route

# **Note:** In this demo, we only simulate IPMI and data center networks by redistributing their switches’ loopback addresses into the BasePOD N/S network.

# To ensure both uplinks (for IPMI and edge) are used to route traffic, we use the `multipath aspath-ignore` setting as both peers use different ASNs.
nv set vrf inband_storage router bgp path-selection multipath aspath-ignore on

# Configuration verification:

# IPMI subent:

nv show vrf inband_storage router rib ipv4 route 10.100.100.0/32  

# Edge (DC) subnet:
nv show vrf inband_storage router rib ipv4 route 10.200.200.0/32

## E/W and N/S networks connectivity test

# To test E/W network all-to-all GPU connectivity, we placed a bash script named `ping_test.sh` on the `dgx01` node. This script sends 2 ICMP packets using the ping command to all DGX NICs with the source of each of the `dgx01` NICs.

# Run the script to verify E/W all-to-all connectivity.




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

