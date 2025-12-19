# YANG Validation Plugin Test Cases

This directory contains test cases for the basic YANG validation plugin.

## Test Files

### 01-minimal.yml
Minimal valid topology that demonstrates successful YANG validation at the default `post_transform` phase.

### 02-invalid-node.yml
Topology with an invalid link referencing a non-existent node. **Note**: Netlab's built-in validation catches this error during the `transform_setup` phase, before YANG validation runs. This test demonstrates that netlab validates node references early in the transformation process.

### 03-custom-validation.yml
Valid topology demonstrating YANG validation working correctly. The YANG plugin includes custom validation that checks constraints like `linkindex >= 1`, which ensures data integrity after transformation.

## Example: Error YANG Can Catch That Netlab Doesn't

While netlab performs extensive validation during transformation, YANG validation can catch constraint violations that might occur after transformation or in edge cases:

### Example: Invalid linkindex Value

**Scenario**: After transformation, if somehow a link has `linkindex=0` or a negative value (perhaps due to a transformation bug or manual manipulation), YANG validation would catch it.

**Why netlab doesn't catch it**: Netlab assigns `linkindex` automatically starting from 1, so this error is unlikely during normal operation. However, YANG validates the constraint explicitly:
- YANG model: `linkindex` must be `uint32` with range `1..max`
- If a link had `linkindex: 0`, YANG validation would fail with a type/range constraint error

**Other examples YANG can catch**:

1. **Type constraint violations**: YANG validates that `linkindex` is a `uint32` with range `1..max`. If somehow a link had `linkindex=0` or a non-integer value after transformation, YANG would catch it.

2. **Structural constraints**: YANG validates that link interfaces list has `min-elements 1`, ensuring every link has at least one interface.

3. **String length constraints**: YANG can validate string lengths (e.g., node names must be non-empty with `length "1..max"`).

4. **Cross-field validation**: YANG MUST statements can validate relationships between fields that netlab might not check.

5. **Data integrity after transformation**: YANG validates the final transformed structure, catching any inconsistencies that might have been introduced during transformation.

## Running Tests

```bash
source setup.sh
./netlab create tests/integration/yang_validation/01-minimal.yml
```

## Validation Phases

The plugin can validate at two phases:
- `init`: After loading and defaults merging, before transformation
- `post_transform`: After all transformations are complete (default)

Configure the phase in the topology:
```yaml
defaults:
  yang_validation:
    validate_phase: init  # or 'post_transform'
```

