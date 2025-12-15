# Phase Analysis: What Gets Added in Each Transformation Phase

This document analyzes the dump files to determine what gets added to the topology structure in each transformation phase.

## Summary

### INIT Phase
- **Nodes**: Basic structure with `name`, `device`, and empty `interfaces` list
- **Links**: Basic structure with `linkindex` and `interfaces` list (nodes only, no addresses)
- **No**: pools, addressing, node IDs, management IPs, loopbacks, or node interfaces

### POST_NODE_TRANSFORM Phase
**Added to Nodes:**
- `id`: Node identifier (1, 2, etc.)
- `box`: Vagrant box or Docker container identifier
- `mtu`: Device-wide MTU
- `role`: Node role (router, host, etc.)
- `mgmt`: Management interface configuration (ifname, ipv4, mac)
- `loopback`: Loopback interface configuration (ifindex, ifname, ipv4, type, virtual_interface, neighbors)
- `af`: Address family configuration
- `module`: List of configuration modules
- `ospf`: OSPF module node attributes (area)

**Added to Topology:**
- `pools`: Address pools (mgmt, loopback, p2p, lan, router_id, vrf_loopback, l2only)
- `addressing`: Addressing configuration (mgmt, loopback, p2p, lan, router_id, vrf_loopback, l2only)
- `module`: Topology-level module list
- `provider`: Virtualization provider

**Links:** Still have only basic structure (no addresses or interface details)

### POST_LINK_TRANSFORM Phase
**Added to Nodes:**
- `interfaces`: Now populated with actual interface data:
  - `ifindex`: Interface index
  - `ifname`: Interface name
  - `ipv4`: IPv4 address
  - `linkindex`: Link index this interface belongs to
  - `mtu`: Interface MTU
  - `name`: Interface name/description
  - `type`: Interface type
  - `neighbors`: List of neighbor interfaces (ifname, ipv4, node)

**Added to Links:**
- `node_count`: Number of nodes connected to this link
- `type`: Link type (p2p, lan, stub, loopback)
- `prefix`: Link prefix configuration (ipv4)
- `interfaces`: Now populated with interface details:
  - `ifindex`: Interface index
  - `ifname`: Interface name
  - `ipv4`: IPv4 address
  - `node`: Node name

### POST_TRANSFORM Phase
**Added to Nodes:**
- `interfaces[].ospf`: OSPF module-specific interface attributes:
  - `area`: OSPF area
  - `network_type`: OSPF network type
  - `passive`: Passive interface flag
- `loopback.ospf`: OSPF module-specific loopback attributes:
  - `area`: OSPF area
  - `passive`: Passive interface flag
- `ospf.af`: OSPF address family configuration (ipv4)
- `ospf.router_id`: OSPF router ID

**Links:** No changes from post_link_transform

## Key Observations

1. **Node Transformation (post_node_transform)**:
   - Assigns node IDs
   - Creates management interfaces
   - Creates loopback interfaces
   - Sets up address pools and addressing configuration
   - Adds device-specific attributes (box, mtu, role)

2. **Link Transformation (post_link_transform)**:
   - Creates node interfaces from links
   - Assigns IP addresses to interfaces
   - Sets up neighbor relationships
   - Determines link types and prefixes

3. **Post Transform (post_transform)**:
   - Module-specific transformations (e.g., OSPF)
   - Adds module attributes to interfaces and loopbacks
   - Finalizes routing protocol configuration

## Data Structure Evolution

```
INIT:
  nodes: [{name, device, interfaces: []}]
  links: [{linkindex, interfaces: [{node}]}]

POST_NODE_TRANSFORM:
  nodes: [{name, device, id, box, mtu, role, mgmt, loopback, af, module, ospf, interfaces: []}]
  links: [{linkindex, interfaces: [{node}]}]
  pools: {...}
  addressing: {...}

POST_LINK_TRANSFORM:
  nodes: [{..., interfaces: [{ifindex, ifname, ipv4, linkindex, mtu, name, type, neighbors}]}]
  links: [{linkindex, node_count, type, prefix, interfaces: [{node, ifindex, ifname, ipv4}]}]

POST_TRANSFORM:
  nodes: [{..., interfaces: [{..., ospf: {...}}], loopback: {..., ospf: {...}}, ospf: {af, router_id}}]
```


