# Considerations for the design of the 'service' module/concept

The **service** module introduces the homonymous abstract concept of a 'service', an association across multiple interfaces on multiple nodes.
The closest match in the current code base would be a 'vlan', but a 'service' is more abstract and intended to be extended by other modules or plugins.

A service has a name (identifier), a numerical id, and a 'type'. The default definition lists no types, values can be added by extensions and then referenced in template logic ( `for s in topology.services { if (s.type=='X') { do something useful with s } }` ). By making templates conditional on the service type, the addition of other service types does not affect existing templates (again, unlike vlans)

Besides extensibility, a second consideration why 'vlan' isn't suitable, is the complex attribute copying logic involved with VLAN SVI interfaces.
Service objects are declared at global or node level, and then referenced from node interfaces. As syntactic sugar, a service can be associated with a link which causes it to be associated with all interfaces attached to that link. From there, an individual extension module - like **vlan** (ffs) - may decide to create a virtual interface and move (some of) the merged service attributes there (warning about any inconsistencies), whereas another - like **epipe** - might leave them all on the physical interfaces.

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



