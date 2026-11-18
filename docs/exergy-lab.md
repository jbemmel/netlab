# exergy-lab Browser Twin

Use `device: exergy-lab` with the Containerlab provider to run a lab.net relay.
Compatible images start an embedded headless browser controller automatically.
An interactive browser can also own the control plane.

The device supports these features through the Go/Linux dataplane:

* IPv4 and IPv6 BGP, IPv6 link-local transport, IPv4 over IPv6 transport
  (RFC 8950), local AS (including IBGP and VRFs), confederations, address-family
  activation, prefix advertisement, and configurable keepalive/hold timers.
* OSPFv2, OSPFv3, and IS-IS, including routing inside VRFs.
* Redistribution of OSPFv2, OSPFv3, IS-IS, and connected routes into BGP, including VRF instances.
* Asynchronous BFD for BGP, OSPFv2, OSPFv3, and IS-IS over IPv4 or IPv6.
* VLAN access, trunks, routed subinterfaces, and static VXLAN with IPv4 or IPv6 VTEPs.
* VXLAN EVPN bridging and symmetric IRB with tenant L3 VNIs, multiple import/export
  route targets, and IPv4/IPv6 tenant reachability.
* LAG interfaces using Linux bonds, including active and passive LACP and EVPN Ethernet Segments.
* IPv4 and IPv6 anycast gateways on routed interfaces and SVIs, including VRFs.
* The existing BGP SRv6 IPv4 service signaling over IPv6 transport.

Netlab mounts one shared resolved topology at `/config/topology.json`, read-only
in every lab.net container. Each node has a separate `/config/node.json`
containing its name, token, listener settings, `topologyFile`, and the explicit
`topologyFormat: netlab-resolved` declaration. The runtime
creates Linux VRFs, VLAN devices, bridges, bonds, VXLAN VTEPs, and anycast gateway
interfaces from that file. Module configuration does not require a separate CLI. The device belongs to the
`unprovisioned` group so netlab skips dynamic provisioning; Containerlab mounts
the JSON files and invokes the runtime startup hook.

Native VRRP, asymmetric EVPN IRB, and EVPN MPLS transport are not advertised.
The `evpn.multihoming` plugin's segment id is the Ethernet Segment Identifier.

The default image is `ghcr.io/exergy-connect/lab.net-router:latest`, matching the
lab.net deployment default. Override `box` to use another compatible image.

```yaml
provider: clab
module: [ bgp ]
nodes:
  twin:
    device: exergy-lab
    bgp.as: 65001
  native:
    device: frr
    bgp.as: 65002
links:
- twin-native
```

Open `http://<twin-management-ip>:4242/?lab=running-lab` to inspect the running lab.
The embedded headless browser owns the control plane by default; additional browser
pages provide read-only inspection of its live state. An interactive browser can
own the control plane when no other controller owns it; keep that page open while
it does.
Set `LAB_NET_HEADLESS=0` in the container environment to disable the embedded controller.
HTTPS is disabled by default. Set `exergy-lab.https: true` to enable it with a
generated TLS certificate. The management address must be
reachable from your browser. Containerlab does not publish this port on the host.

The device runs as root so its protocol agents can use raw sockets and install
routes. The supervisor loads the node configuration and shared topology once
at startup and waits in `--wait-init` mode.
Containerlab invokes `exergy-lab.net-go --startup` from its exec list after attaching data links.
The supervisor then provisions Linux interfaces and starts the runtime from the
loaded configuration. Runtime reloads do not reread the file or provision Linux.

LLDP is enabled by default (`netlab_lldp_enable: True`). The device sets
`LAB_NET_LLDP=1`, and compatible images run `exergy-lab.net-lldp` on data
interfaces once Containerlab has attached them. The advertised system name is the netlab node
name. Management and loopback interfaces are excluded. Show neighbors with
`exergy-lab.net-lldp show`.

Node attributes `exergy-lab.port` (default 4242), `exergy-lab.https` (default false), and
`exergy-lab.token` configure the relay. The default token is
`lab-net-browser-connect`; set a private token for shared environments.
Generated files contain the token and should be treated as lab credentials.

See `tests/integration/exergy-lab/topology.yml` for a two-router example.

## BFD

Add the `bfd` module and enable BFD on routing protocols or BGP sessions:

```yaml
provider: clab
module: [ bgp, ospf, bfd ]
plugin: [ bgp.session ]
bfd:
  min_tx: 100
  min_rx: 100
  multiplier: 3
ospf.bfd: true
nodes:
  twin:
    device: exergy-lab
    bgp.as: 65001
  native:
    device: frr
    bgp.as: 65002
links:
- twin:
  native:
  role: internal
  bgp.bfd: true
```

`role: internal` keeps the IGP enabled on this inter-AS link. Use `isis.bfd: true`
for IS-IS. Per-interface BFD timers override node timers; `bfd: false` disables
IGP BFD on an interface. The `bgp.session` plugin supplies BGP neighbor enablement.
The device consumes the standard resolved netlab BFD settings directly from the
mounted JSON, including protocol enablement and node/interface timers.

Intervals are milliseconds (1–60000), and the detection multiplier is 1–255.
Use a current lab.net image containing the BFD helper and browser runtime.
Echo mode, authentication, demand mode, and strict BFD are unsupported. IS-IS
honors the per-address-family BFD flags on dual-stack interfaces.

See `tests/integration/exergy-lab/bfd.yml` for a dual-stack FRR interoperability
lab with shared protocol sessions, interface opt-outs, and timer overrides.
Inspect BFD in the browser's BFD tab and use `show bfd peers` on FRR.

(exergy-lab-bgp-mnh)=
## BGP MultiNexthop WECMP Use Case

`tests/integration/exergy-lab/bgp-mnh.yml` models weighted ECMP from ingress
PEs `r3` and `r4` toward the Internet feed `192.168.255.10/32` on `r0`.
It uses Exergy Lab for every router, retaining the roles of the reference
topology rather than its cRPD and vMX implementations.

Router `r0` is in AS 65100 and peers with four egress PEs in AS 65000:
`r11`, `r12`, `r13`, and `r14`. Their external link bandwidths are 10000,
20000, 30000, and 40000 Mbps. All provider routers connect through `p1`,
which runs OSPF only. Route reflectors `rr1` and `rr2` distribute BGP routes
to the egress and ingress PEs over loopback sessions. Ingress loopbacks are
`198.51.100.3/32` and `198.51.100.4/32`.

Set `bgp.mnh: send` on `rr1` and `rr2`, and `bgp.mnh: receive` on ingress
and egress PEs. RRs originate MNH; PEs consume it without sending MNH.
Boolean `true` selects `send` on RRs and `receive` on other routers.
The setting is omitted on `r0`; `p1` has no BGP process.

Egress PEs attach a link-bandwidth extended community to routes imported from
EBGP, using the external interface bandwidth in Mbps. RRs combine eligible
paths for a prefix into a single MNH advertisement with per-endpoint bandwidth
in bits per second. Reflected next hops remain the egress loopbacks. A PE uses
the selected reflector's complete set, so duplicate advertisements from the
two RRs do not double the weights.

Enable `module: [ bgp, ospf, mpls ]` on the PEs and RRs, and
`module: [ ospf, mpls ]` on `p1`, with these MPLS settings:

```yaml
mpls:
  ldp: false
  static: true
```

Static transport labels are `16000 + node.id`, allocated consistently from the
shared topology. Linux installs a weighted IP route whose next hops each push
an egress transport label. `p1` swaps that label toward the egress, which pops
it and forwards the original IP packet. LFIB entries follow IGP reachability
and are removed when no longer needed. This is static label forwarding, with
no LDP signaling. The Linux host needs `mpls_router` and `mpls_iptunnel` kernel
support loaded before deployment; startup enables the MPLS label table and
MPLS input on provider interfaces.

The implementation supports up to 16 IPv4 unicast endpoints in the default
routing table, with primary-path, equal-preference Forward instructions and
endpoint bandwidths. It follows the encoding in
[draft-ietf-idr-multinexthop-attribute-05](https://datatracker.ietf.org/doc/html/draft-ietf-idr-multinexthop-attribute-05)
and uses experimental attribute code **254**, since the draft's IANA code is
unassigned. This local lab profile is not a claim of Junos interoperability.
Unsupported optional encodings discard MNH and use the conventional next hop;
invalid v0 mandatory MNH makes the route ineligible. Linux weights use exact
integer ratios where possible and scale to its 1–256 range when necessary.

The runtime regression tests cover these acceptance criteria:

* Both ingress PEs receive all four egress next hops for `192.168.255.10/32`
  through either reflector, retaining their bandwidth information.
* Each ingress PE installs weights `1:2:3:4`, corresponding to approximately
  10%, 20%, 30%, and 40% of sufficiently many independent traffic flows.
* Receiving the same next hops through both reflectors does not double their
  weights. Reflectors remain outside the forwarding path.
* Removing the `r0-r14` link withdraws that next hop and leaves weights
  `1:2:3` on `r11-r13`; restoring the link restores `1:2:3:4`.
* Loss of either reflector preserves the next hops learned through the other.

`lab.net/tests/bgp-mnh.test.js` exercises signaling direction, MPLS forwarding,
weights, malformed wire input, and reconvergence. Go tests check Linux route
commands, snapshot validation, and MPLS startup settings. Live kernel forwarding
still needs validation on an MPLS-capable deployment.

Check topology transformation without deploying containers:

```bash
netlab create tests/integration/exergy-lab/bgp-mnh.yml -o none
```

Omitting `bgp.mnh` or setting it to `false` requests ordinary BGP behavior.

## MPLS VPNv4

Exergy Lab supports VPNv4 over BGP and LDP transport. Enable `bgp`, `mpls`,
`vrf`, and an underlay IGP on the provider edge routers, and enable
`mpls.vpn.ipv4` for the desired BGP session types. IPv6 VPN routes are not
supported. VPNv4 sessions need extended community propagation for route targets.
The image must include the `bgp_vpn`, `bgp`, `mpls`, `ldp`, and `vrf` features.

`tests/integration/exergy-lab/vpnv4.yml` provides an FRR interoperability
topology with two isolated VRFs. The Linux host needs the `mpls_router` and
`mpls_iptunnel` kernel modules for forwarding.

## BGP Graceful Restart

The `bgp.session` plugin's `bgp.gr` settings are supported at node, VRF, and
neighbor level. The device consumes the resolved JSON directly, including
`state` (`enable`, `helper`, or `disable`), `restart_time`, and `stalepath_time`.
VRFs have independent settings; node-level GR settings do not propagate to them.
GR is disabled unless explicitly configured. IPv4 unicast, IPv6 unicast, and
EVPN use independent negotiated restart state and End-of-RIB processing.

Use a current lab.net image or update its browser/WASM artifacts before testing.
`tests/integration/bgp.session/14-gr.yml` checks the advertised restart, helper,
and disabled modes against FRR probes, including VRF neighbors. Run it from an
empty deployment directory with `netlab up -d exergy-lab -p clab <path-to-test>`,
then run `netlab validate` after any local artifact update.

Lab.net also supports opt-in LLGR through the `bgp.session` plugin's `bgp.llgr`
settings, using a `state` and a `stale_time` in seconds. LLGR requires GR
to be enabled or in helper mode on the same session. RFC 8538 is enabled with GR by default: the device advertises the N bit and
retains routes after eligible notifications and hold-timer expiry when both
peers negotiate it. Set `bgp.gr.notification: false` to use legacy notification
handling. Cease/Hard Reset always removes routes, as do administrative node/link
and BFD failures. Explicit withdrawals are never deferred.
