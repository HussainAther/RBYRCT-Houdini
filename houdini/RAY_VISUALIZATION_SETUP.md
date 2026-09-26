# Houdini Ray Visualization Setup

## Python SOP trajectory import

1. Run the ray engine and validation scripts from the repository root:

   ```bash
   python3 scripts/run_ray_engine.py
   python3 scripts/validate_ray_visualization.py
   ```

2. In Houdini, create a Geometry object and enter it.
3. Add a **Python SOP**.
4. Add a string parameter named `events_file_path`.
5. Optionally add a toggle named `skip_zero_length_segments` and enable it.
6. Paste or load `houdini/python/import_ray_events.py` in the Python SOP.
7. Set `events_file_path` to `data/ray_engine/ray_events.csv`.

The SOP creates one open polyline per ray. Points carry:

- `ray_id`, `event_index`, `event_type`, `state_code`, `layer_index`
- `direction`, `energy_kev`, `intensity`
- `cumulative_distance`, `cumulative_steering_deg`
- `is_terminal`, `Cd`

Primitives carry `ray_id`, `terminal_state`, and `final_intensity`.

## Suggested display network

- Add a **Polywire SOP** after the importer for visible ray tubes.
- Drive wire radius with `intensity`, while keeping a nonzero minimum radius.
- Use point `Cd` to distinguish source, layer, detector-hit, detector-miss, and
  termination states.
- Add a **Blast SOP** with expressions such as `@terminal_state=detector_miss`
  to isolate failure classes.
- Import `detector_occupancy.csv` separately for detector heat-map work.

## Canonical validation scenes

Generate three deterministic datasets:

```bash
python3 scripts/generate_canonical_ray_scenarios.py
```

They appear under `data/canonical_scenarios/`:

- `zero_steering`: baseline line-plane geometry
- `symmetric_steering`: positive steering followed by equal negative steering
- `exaggerated_steering`: intentionally obvious curvature and detector shift

These datasets are meant for visual auditing, not physical validation.
