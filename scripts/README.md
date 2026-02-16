# Scripts (RBYRCT-Houdini)

This folder contains Python utilities for generating geometry, validating outputs, exporting simulation results, and running the end-to-end pipeline.

---

## Overview

### Geometry / Layout
- **`janus_array_gen.py`**
  - Generates concentric Janus-sphere layer layouts (CSV).
  - Output: `data/janus_layers_concentric.csv`

- **`validate_csv.py`**
  - Validates CSV headers, numeric fields, and (optionally) expected row counts.

---

### Houdini Export
- **`export_beam_paths.py`** *(run with `hython`)*
  - Loads a `.hip/.hiplc`, reads a SOP node’s point geometry, exports point attributes to CSV.
  - Typical exports: `P` → `x,y,z`, `N` → `nx,ny,nz`, `Cd` → `r,g,b`, plus `intensity`.

Example:
```bash
python scripts/export_beam_paths.py \
  --hip houdini/projects/bragg_reflection_demo.hiplc \
  --node /obj/janus_beam_reflection/geo1/OUT_REFLECTION \
  --out data/beam_paths.csv

````

---

### Detector / Imaging Outputs

* **`make_endpoints_from_paths.py`**

  * Intersects rays with a detector plane `z = z_det` to compute detector endpoints.
  * Output: `data/ray_endpoints.csv`

Example:

```bash
python scripts/make_endpoints_from_paths.py data/beam_paths.csv \
  --z-det 0 \
  --out data/ray_endpoints.csv \
  --write-weight
```

* **`export_detector_hitmap.py`**

  * Bins detector endpoints into a 2D hitmap (CSV) and writes metadata JSON.
  * Outputs: `data/hitmap.csv`, `data/hitmap_meta.json`

Example:

```bash
python scripts/export_detector_hitmap.py data/ray_endpoints.csv \
  --out data/hitmap.csv \
  --meta data/hitmap_meta.json \
  --width 256 --height 256
```

---

## One-Command Pipeline

* **`run_pipeline.py`**

  * Runs: layout generation → (optional) Houdini export → endpoints → hitmap → validation.

Example:

```bash
python scripts/run_pipeline.py \
  --hip houdini/projects/bragg_reflection_demo.hiplc \
  --node /obj/janus_beam_reflection/geo1/OUT_REFLECTION
```

Skip Houdini export if `data/beam_paths.csv` already exists:

```bash
python scripts/run_pipeline.py --skip-houdini
```

---

## Notes

* `export_beam_paths.py` must be run with **Houdini’s Python** (`hython`), not system Python.
* This project focuses on **procedural steering + planning simulation** and dataset generation.

````

Save and exit.

---

## 3) Stage + commit
```bash
git status
git add scripts/README.md
git commit -m "Docs: add scripts README with usage examples"
````

---

## 4) Push + open PR

```bash
git push -u origin docs-scripts-readme
gh pr create \
  --title "Docs: add scripts README with usage examples" \
  --body "Adds scripts/README.md documenting each utility and how to run the end-to-end pipeline."
```

