# lab.net Browser Twin

Use `device: labnet` with the Containerlab provider to run a lab.net relay.
The browser owns the control plane; keep its page open while running the lab.
The initial integration supports numbered BGP, OSPF, and IS-IS configurations.
Advanced protocol options are not advertised as supported.

The default image is `ghcr.io/exergy-connect/lab.net-go:latest`, matching the
lab.net deployment default. Override `box` to use another compatible image.

```yaml
provider: clab
module: [ bgp ]
nodes:
  twin:
    device: labnet
    bgp.as: 65001
  native:
    device: frr
    bgp.as: 65002
links:
- twin-native
```

Open `http://<twin-management-ip>:8080/` and launch the browser control plane.
HTTPS is disabled by default. Set `labnet.https: true` to enable it with a
generated TLS certificate. The management address must be
reachable from your browser. Containerlab does not publish this port on the host.

The device runs as root so its protocol agents can use raw sockets and install
routes. Netlab configures Linux interface addresses through the container's
network namespace and mounts a generated topology in `/config/relay.json`.
Protocol configuration is read from this file by the browser and relay.

Node attributes `labnet.port` (default 8080), `labnet.https` (default false), and
`labnet.token` configure the relay. The default token is
`lab-net-browser-connect`; set a private token for shared environments.
Generated files contain the token and should be treated as lab credentials.

See `tests/integration/labnet/topology.yml` for a two-router example.
