# Considerations for the design of the 'service' module/concept

The **service** module introduces the homonymous abstract concept of a 'service', an association across multiple interfaces on multiple nodes.
Conceptually one can think of this as a 'vlan', but a 'service' is more abstract, device specific and intended to be extended by other modules or plugins. Services model transport services in the core network.

A service has a name (identifier), a numerical id, and a 'type'. The default definition lists no types, values can be added by extensions and then referenced in template logic ( `for s in interface.services { if (s.type=='X') { do something useful with s } }` ). By making templates conditional on the service type, the addition of other service types does not affect/conflict with existing templates (again, unlike vlans)

Besides extensibility, a second consideration why repurposing the 'vlan' module isn't suitable, is the complex attribute copying logic and constraints involved with VLAN SVI interfaces.

Service objects are declared at global or node level, and then referenced from node interfaces. As syntactic sugar, a service can be associated with a link which causes it to be associated with/copied to all interfaces attached to that link.

There are several ways to associate a service with an interface, and the terminology used is platform specific.
For example, in case of SR OS:
* Through a Service Access Point (SAP, customer access point) - by specifying **sap-id**
* Through a (spoke) Service Distribution Point (SDP) - by specifying **spoke-sdp**

The supported service types and associated attributes are defined by each platform.

```
services:
 vpls1:
  id: 1
  type: vpls

 epipe1:
  id: 2
  type: epipe

 epipe2:
  id: 3
  type: epipe

nodes: [ n1, n2, n3 ]

links:
- n1:
  n2:
  service:
   vpls1:      # Example of a link level service spanning all interfaces
    sap-id: 10 # Using 802.1q tag 10 on each interface

- n1:
   service:
    epipe1:
     evpn.eth_tag: 100
    epipe2:
     evpn.eth_tag: 101
  n3:
   service:
    epipe1:
     evpn.eth_tag: 300
    epipe2:
     evpn.eth_tag: 301
```

As illustrated in the (disconnected) example above, every service has both a globally unique name and an numerical id. It can be extended with module or plugin specific attributes, such as an EVPN ethernet tag at the interface level. The use of a 'dict' allows the association of 1:many (interface:service), optionally including specific attributes for each association.

The n1-n2 link in the above topology would be transformed as follows:
```
links:
- n1:
   service:
    vpls1:
     id: 1
     type: vpls
     sap-id: 10
  n2:
   service:
    vpls1:
     id: 1
     type: vpls
     sap-id: 10
```
i.e. the service 'name' is resolved to the node local or global entity, and all its attributes are copied (unless overridden). Only referenced services are included, whether defined globally or only for this specific node.

## Service data model presented to templates

As part of the transformation logic, service dictionaries are converted into a list. A 'name' attribute is added, such that templates can do the following:
```
{% for i in interfaces if 'service' in i %}
{% for s in i.service if s.type=="epipe" %}
... etc
```

## Defining new service types

A new service type can be defined as follows:
```
def init(topology: Box) -> None:
    topology.defaults.service.attributes['global'].type.valid_values.extend(["epipe"])
```
This adds the new 'epipe' type globally; Netlab will copy it to node level automatically

## Defining extra attributes for services

A service definition can be extended with custom module specific attributes at 2 levels:
1. Global/node level:
```
topology.defaults.evpn.attributes.service.evi = { "type": "int", "service_type": "vxlan" }
```
2. Node interface level (as explained above, link level attributes get copied to interface level)
```
topology.defaults.evpn.attributes.service_interface.eth_tag = { "type": "int", "service_type": "epipe" }
```

If 'service_type' is specified (as a string or list of strings), the corresponding attribute is allowed only in services of that/those type(s)



