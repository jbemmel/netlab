# exergy-lab Browser Twin

Use `device: exergy-lab` with the Containerlab provider to run a lab.net relay.
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
    device: exergy-lab
    bgp.as: 65001
  native:
    device: frr
    bgp.as: 65002
links:
- twin-native
```

Open `http://<twin-management-ip>:8080/` and launch the browser control plane.
HTTPS is disabled by default. Set `exergy-lab.https: true` to enable it with a
generated TLS certificate. The management address must be
reachable from your browser. Containerlab does not publish this port on the host.

The device runs as root so its protocol agents can use raw sockets and install
routes. Netlab configures Linux interface addresses through the container's
network namespace and mounts a generated topology in `/config/exergy-lab.json`.
Protocol configuration is read from this file by the browser and relay.

The device sets `LAB_NET_INITIAL_DONE_FILE=/var/run/initial.done`. Compatible
images wait for that marker before starting the relay, browser, and protocol
helpers. The initial configuration template creates it inside the container
only after Linux provisioning succeeds. Use an image with this startup gate;
older images ignore the variable and can start helpers before addresses exist.

LLDP is enabled by default (`netlab_lldp_enable: True`). The device sets
`LAB_NET_LLDP=1`, and compatible images run `lldpd` on data interfaces after
provisioning. The advertised system name is the netlab node name. Management
and loopback interfaces are excluded.

Node attributes `exergy-lab.port` (default 8080), `exergy-lab.https` (default false), and
`exergy-lab.token` configure the relay. The default token is
`lab-net-browser-connect`; set a private token for shared environments.
Generated files contain the token and should be treated as lab credentials.

See `tests/integration/exergy-lab/topology.yml` for a two-router example.
