# Considerations for the design of the 'service' module/concept

The **service** module introduces the homonymous abstract concept of a 'service', an association across multiple interfaces on multiple nodes.
The closest match in the current code base would be a 'vlan', but a 'service' is more abstract and intended to be extended by other modules or plugins.

A service has a name (identifier), a numerical id, and a 'type'. The default definition lists no types, values can be added by extensions and then referenced in template logic ( `for s in interface.services { if (s.type=='X') { do something useful with s } }` ). By making templates conditional on the service type, the addition of other service types does not affect/conflict with existing templates (again, unlike vlans)

Besides extensibility, a second consideration why 'vlan' isn't suitable, is the complex attribute copying logic and constraints involved with VLAN SVI interfaces.

Service objects are declared at global or node level, and then referenced from node interfaces. As syntactic sugar, a service can be associated with a link which causes it to be associated with/copied to all interfaces attached to that link.

There are several ways to associate a service with an interface:
* Through a Service Access Point (SAP, customer access point) - by specifying **sap-id**
* Through a (spoke) Service Distribution Point (SDP) - by specifying **spoke-sdp**

## Modeling vlans as a type of service: For Future Study (FFS)
It would be possible to migrate/modify the logic in the 'vlan' module to include a 'vlan' type service. This exercise is explicitly left as a potential future endeavour, and out of scope of the current 'service' module. Consequently, the examples given below refer to a hypothetical 'vlan' type service for illustrative purposes only

```
services:
 vlan1:
  id: 1
  type: vlan   # Hypothetical example, no intention to rewrite vlan code for now
  vlan.id: 100 # Example of a service attribute defined by an extension module/plugin
  vlan.mode: bridge

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
   vlan1:  # Example of a service spanning all interfaces

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
    epipe1:
     evpn.eth_tag: 301
```

As illustrated above, every service has both a globally unique name and an numerical id. It can be extended with module or plugin specific attributes, such as a VLAN id (tag) or an EVPN ethernet tag at the interface level. The use of a 'dict' allows the association of 1:many (interface:service), optionally including specific attributes for each association.

The n1-n2 link in the above topology would be transformed as follows:
```
links:
- n1:
   service:
    vlan1:
     id: 1
     type: vlan
     vlan.id: 100
     vlan.mode: bridge
  n2:
   service:
    vlan1:
     id: 1
     type: vlan
     vlan.id: 100
     vlan.mode: bridge
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



