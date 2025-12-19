# YANG Validation Plugin

## Use Case

The YANG validation plugin allows you to express **additional constraints beyond what netlab already enforces** using YANG data modeling. While netlab has extensive built-in validation that catches many common errors, YANG models enable you to:

- Define custom validation rules using YANG `MUST` statements
- Enforce module-specific constraints (e.g., "BGP attributes require the BGP module to be active")
- Validate complex cross-tree relationships
- Express business logic constraints that are specific to your organization or use case
- Catch errors that netlab's standard validation might not detect

## How It Works

The plugin validates the topology structure against a YANG model at a specified transformation phase (default: `post_transform`). The YANG model defines:

- **Data structure**: The expected structure of nodes, links, and topology-level attributes
- **Constraints**: Rules expressed via YANG `MUST` statements that validate data integrity
- **Type checking**: Validation of data types and allowed values

When validation fails, the plugin reports specific errors indicating which constraints were violated.

## Configuration

Enable the plugin in your topology file:

```yaml
plugin: [yang_validation]
```

Configure validation settings in `defaults.yml` or in your topology:

```yaml
yang_validation:
  validate_phase: post_transform  # 'init' or 'post_transform' (default)
  model: package:extra/yang_validation/model/netlab-topology.yang
```

## Example: STP Protocol Constraint

The plugin can enforce constraints that netlab doesn't check by default. For example, the STP module YANG model prevents setting the STP protocol at the node level:

```yang
container stp {
  must "not(protocol)" {
    error-message "STP protocol cannot be set at node level. Set it globally in defaults.stp.protocol instead.";
  }
}
```

This catches errors like:

```yaml
nodes:
  s1:
    stp.protocol: rstp  # ERROR: YANG validation will catch this
```

## YANG Model Structure

The plugin includes:

- **`netlab-topology.yang`**: Main topology model defining nodes, links, and topology-level structures
- **`netlab-stp.yang`**: STP module-specific definitions and groupings

The models use `anydata` for flexible structures while providing structured validation for specific attributes (like `stp` containers) where constraints need to be enforced.

## Validation Phases

- **`init`**: Validates after loading and defaults merging (before transformation)
- **`post_transform`**: Validates after all transformations are complete (default)

Choose the phase based on when you need to validate specific aspects of the topology.

## Extending the Model

To add new constraints:

1. Define new YANG groupings or containers in module-specific YANG files
2. Import and use them in `netlab-topology.yang`
3. Add `MUST` statements to express constraints
4. Update the plugin's data transformation if needed to match the YANG structure

## See Also

- Test cases: `tests/integration/yang_validation/`
- YANG models: `netsim/extra/yang_validation/model/`

