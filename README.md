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

## Phase 1 ray engine

The repository now includes a dependency-free, explicitly idealized ray pipeline:

```text
source -> emit rays -> intersect layers -> steer -> attenuate -> detector -> record
```

Core implementation:

```text
physics/ray_engine.py
scripts/run_ray_engine.py
```

Run the default 5 x 5 beam through five steering planes:

```bash
python3 scripts/run_ray_engine.py
```

Outputs are written to `data/ray_engine/`:

- `rays.csv` — one summary row per emitted ray
- `ray_events.csv` — emitted, layer-enter, layer-exit, termination, and detector events
- `detector_hits.csv` — detector coordinates, active-area status, and pixel indices

Example with custom geometry:

```bash
python3 scripts/run_ray_engine.py \
  --rows 11 \
  --columns 11 \
  --layers 8 \
  --layer-spacing 2.0 \
  --steering-per-layer-deg 0.5 \
  --transmission-per-layer 0.97 \
  --detector-z 24.0 \
  --output-dir data/custom_ray_run
```

### Model boundary

This first ray engine performs exact geometric line-plane intersections and vector rotations, but its steering angle and per-layer transmission are configurable approximations. It does **not** yet calculate crystal orientation, Bragg acceptance, energy-dependent material attenuation, stochastic scattering, or dose. Those should be introduced as replaceable physics models and validated independently.

## Phase 1.5 ray visualization and validation

Phase 1.5 converts ray-event histories into attributed trajectory geometry,
checks spatial consistency, and prepares deterministic Houdini validation data.

Core files:

```text
visualization/ray_geometry.py
analysis/ray_validation.py
scripts/validate_ray_visualization.py
scripts/generate_canonical_ray_scenarios.py
houdini/python/import_ray_events.py
houdini/RAY_VISUALIZATION_SETUP.md
```

Build portable point and segment geometry from the default Phase 1 run:

```bash
python3 scripts/validate_ray_visualization.py
```

Generated artifacts under `data/ray_validation/`:

- `ray_points.csv` — one attributed point per recorded ray event
- `ray_segments.csv` — ordered pairwise trajectory segments
- `detector_occupancy.csv` — dense detector pixel hit and intensity grid
- `validation_summary.json` — machine-readable pass/fail metrics
- `validation_issues.csv` — explicit errors and warnings

The validator checks:

- contiguous event ordering for each ray
- unit-length direction vectors
- monotonic cumulative distance
- exact segment-to-event endpoint agreement
- agreement between segment lengths and cumulative-distance changes
- expected versus suspicious zero-length state transitions
- detector pixel bounds and intensity accumulation

Generate the three canonical visual-audit datasets:

```bash
python3 scripts/generate_canonical_ray_scenarios.py
```

This creates:

```text
data/canonical_scenarios/
  zero_steering/
  symmetric_steering/
  exaggerated_steering/
```

Each scenario includes the Phase 1 trace CSVs, visualization geometry,
detector occupancy, and a validation report. The exaggerated case is
intentionally nonphysical-looking so coordinate, handedness, and detector-shift
errors are easy to see.

For the Houdini Python SOP workflow and suggested node network, see:

```text
houdini/RAY_VISUALIZATION_SETUP.md
```

### Current validation result

The repository's default 25-ray run produces 300 event points and 275 ordered
segments. Phase 1.5 validation passes with zero errors and zero warnings. All
three canonical scenarios also pass.

## Recommended next scientific milestone

Proceed to **Phase 2A: an analytic attenuation phantom** with a single slab or
sphere whose path length and attenuation have closed-form ground truth. Keep
that model separate from the steering approximation, validate it numerically,
and only then move to a heterogeneous breast phantom.

## Phase 2A — Analytic attenuation phantoms

Phase 2A adds closed-form attenuation geometry and Beer–Lambert transport. It
is intentionally an analytic validation stage, not yet a heterogeneous breast
model or Monte Carlo photon-transport solver.

### Included phantoms

- Empty field
- Uniform finite slab, including exact oblique path length
- Uniform sphere with exact chord length
- Nested sphere in which the inner material replaces, rather than overlaps,
  the outer material

### Run the canonical scenarios

```bash
python scripts/generate_analytic_phantom_scenarios.py
```

Outputs are written under `data/analytic_phantoms/<scenario>/`:

- `attenuation_rays.csv` — one summary row per ray
- `phantom_interactions.csv` — exact entry/exit segments and per-material loss
- `detector_intensity.csv` — detector coordinates, pixels, transmission, and
  final intensity
- `analytic_validation_rows.csv` — simulated versus closed-form values
- `analytic_validation_summary.json`
- `analytic_validation_report.md`

### Scientific model

For each non-overlapping material interval, optical depth is accumulated as
`tau = mu * L`, and intensity is updated as `I_out = I_in * exp(-tau)`.
Nested materials are partitioned into disjoint intervals so the inner region is
not double-counted as outer material.

### Houdini

See `houdini/PHASE2A_ATTENUATION_SETUP.md`. The Python SOP importer creates one
polyline per material interaction with attributes including `material_id`,
`path_length`, `mu`, `optical_depth`, `intensity_before`, `intensity_after`, and
`transmission`.

### Validation status

The empty-field, slab, sphere, and nested-sphere canonical datasets all pass at
a tolerance of `1e-10`. The repository test suite contains 31 passing tests.

### Next milestone

Phase 2B should introduce a procedural heterogeneous breast phantom while
retaining these analytic phantoms as regression references.
