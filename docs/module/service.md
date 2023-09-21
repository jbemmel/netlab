# Service Configuration Module

The **service** module offers an abstract end-2-end concept of a transport service. Various platforms support different ways of getting packets across the network, which are modeled as services of different types.

Because platforms and the terminology they use are so different, each platform defines its own set of supported service types with associated attributes.
At runtime, the service module will validate the configuration against the data model definition for a given node, based on its device type.

To give an example:
```
defaults.device: sros

module: [ vlan, service, evpn, mpls, isis, bgp ]

vlans:
  tenant:
    mode: bridge

services:
 epipe-1:
  id: 1
  type: epipe

nodes: [c1,n1,n2,c2]

links:
- c1:
  n1:
   ipv4: False
   service: 
    epipe-1:
     sap-id: vlan
  vlan.access: tenant
- n1:
   service:
    epipe-1:
     evpn.eth_tag: 10
  n2:
   service:
    epipe-1:
     evpn.eth_tag: 20
- n2:
   ipv4: False
   service: 
    epipe-1:
     sap-id: vlan
  c2:
  vlan.access: tenant
```

The above illustrates a network of 2 SR OS devices (n1,n2) that use a BGP-EVPN signalled "epipe" service to transport packets for a tenant VLAN.
The **sros** device supports the 'epipe' type service, and defines an **evpn** module attribute 'eth_tag' to be used on service interface associations.
At the edges, `sap-id: vlan` determines the Service Access Point (SAP) identifier based on associated VLAN (in this case, untagged)

The **service** module is designed to be extensible by platforms or plugins; using different values for 'type' ensures that templates written for different types don't conflict.

In general, multiple services can be associated with any given link or interface. The mapping to VLAN trunks is done in order of declaration, as follows:
```
vlans:
 voice:
  id: 100
 data:
  id: 200

services:
 voice-epipe:
  id: 1
  type: epipe
 data-epipe:
  id: 2
  type: epipe

links:
- c1:
  n1:
   ipv4: False
   service: 
    voice-epipe:
     sap-id: vlan
    data-epipe:
     sap-id: vlan
  vlan.trunk: [ voice, data ]
... 
```
In this case, the 'voice' VLAN would map to the 'voice-epipe' service (sap-id 100), and similar for 'data'.