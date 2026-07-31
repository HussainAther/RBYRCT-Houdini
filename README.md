# RBYRCT-Houdini

A Houdini-based prototyping toolkit for visualizing **Ray-by-Ray Computed Tomography (RBYRCT)** concepts with layered Janus-sphere arrays and idealized ray steering.

> **Scientific scope:** the current steering model applies a configurable angular rotation per layer for geometry and visualization experiments. It is inspired by the intended beam-steering concept, but it is **not yet a validated Bragg-diffraction or X-ray transport model**.

## Current capabilities

- Deterministic generation of concentric, multilayer Janus-sphere arrays
- Configurable layer count, spacing, ring radius, sphere radius, and steering increment
- Rich CSV metadata for Houdini and downstream analysis
- Houdini Python SOP importer with validation and point-attribute creation
- Numerically guarded VEX layered-steering visualization
- Automated Python tests

## Repository layout

```text
scripts/
  janus_array_gen.py       Generate Janus-sphere CSV data
  import_csv_to_points.py  Import generated data in a Houdini Python SOP
houdini/
  bragg_reflection.vfl     Idealized layered steering VEX
tests/
  test_janus_array_gen.py  Generator and CLI tests
data/                       Generated CSV data
```

## Generate the default array

From the repository root:

```bash
python3 scripts/janus_array_gen.py
```

This writes 264 records—11 layers × 24 spheres—to:

```text
data/janus_layers_concentric.csv
```

### Custom example

```bash
python3 scripts/janus_array_gen.py \
  --layers 8 \
  --spheres-per-layer 32 \
  --sphere-radius 0.8 \
  --layer-spacing 2.0 \
  --ring-radius 18.0 \
  --steering-per-layer-deg 3.0 \
  --output data/custom_array.csv
```

## CSV schema

Each row includes:

- `sphere_id`
- `layer_index`
- `ring_index`
- `x`, `y`, `z`
- `sphere_radius`
- `ring_radius`
- `azimuth_deg`
- `steering_angle_deg`

## Houdini import

1. Create a Geometry node and enter it.
2. Add a Python SOP.
3. Add a string parameter named `csv_file_path`.
4. Load or paste `scripts/import_csv_to_points.py` into the Python SOP.
5. Point `csv_file_path` to the generated CSV.

The importer clears the current SOP geometry, validates the CSV schema, creates the required point attributes, and generates one point per sphere record.

## VEX steering visualization

`houdini/bragg_reflection.vfl` expects these controls:

- `num_layers`
- `deflection_per_layer`
- `efficiency_per_layer`

It updates velocity `v`, records `total_efficiency`, and sets `Cd` for visualization. Degenerate input directions, normals, and rotation axes are handled explicitly.

## Tests

Install pytest if needed, then run:

```bash
python3 -m pytest -q
```

## Next scientific milestone

The next major module should model explicit rays, geometric intersections, steering/reflection events, attenuation, and detector-plane hits. More realistic Bragg or X-ray transport physics should be introduced as separate, documented models rather than silently folded into the visualization approximation.

## License

MIT License.
