(plugin-netbrain)=
# Integration with Netbrain

[Netbrain](https://www.netbraintech.com/) provides a platform with APIs to manage network devices in operational networks. This plugin provides support for 2 key use cases

1) Automatically create a Netbrain map of the devices present in the Netlab topology
2) Retrieve the current configuration of network devices in the topology, and provision it as 'startup' config

These use cases combined enable the use of Netlab for testing and staging configuration changes in live networks, by determining the difference between the current state (IST) and the desired state (SOLL) as obtained through the evaluation of Netlab templates. The changes can be validated virtually, and can then be input to a Change Management runbook.

## Supported Platforms

Maps can be generated for any devices, but the running configuration may need some "massaging" before serving as a viable startup config. For example, reconfiguration of the management IP address must be avoided.
The plugin currently contains specific logic for modifying Dell OS10 configs; other platforms could readily be added.

## Using the Plugin

To use the plugin, add it to the **plugin** list in the lab topology:

```
plugin: [ ...., netbrain ]

defaults.netbrain:
  api_user: "admin"                        # Any valid Netbrain user account
  api_url: "https://netbrain.example.com"  # Pointer to the local Netbrain API
  api_stub: "Netlab"                       # Created in the web interface

  create_map: False
  expand_topology: L3                      # Whether to automatically expand the map to include L2 or L3 neighbors
  get_config: True                         # Whether to retrieve the current config

```
Since it is likely unnescessary to create a map every time ```netlab up``` is invoked, map creation is ```off``` by default and can be triggered once using
```netlab create -s defaults.netlab.create_map=True```

The plugin requires an environment variable ```NETBRAIN_TOKEN``` to be set to a valid Netbrain API token. Such a token can be obtained using ```curl``` (for example).

```netbrain.get_config``` can also be configured at the node level, for example to skip certain nodes.