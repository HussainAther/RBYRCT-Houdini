# Phase 2A Houdini attenuation visualization

1. Run `python scripts/generate_analytic_phantom_scenarios.py`.
2. Create a Geometry node and place a Python SOP inside it.
3. Add a string parameter named `interactions_file_path`.
4. Paste `houdini/python/import_attenuation_interactions.py` into the Python SOP.
5. Point the parameter at a scenario's `phantom_interactions.csv`.

Each primitive is the exact segment traveled inside one material. Useful
attributes include `material_id`, `path_length`, `mu`, `optical_depth`,
`intensity_before`, `intensity_after`, and `transmission`. The default `Cd`
attribute maps stronger attenuation toward red and higher transmission toward
green.
