# RBYRCT-Houdini Architecture

This document describes the software architecture of the RBYRCT-Houdini project and how its components fit together.

---

## High-Level Overview

RBYRCT-Houdini is organized as a **procedural simulation + data pipeline** for Ray-by-Ray Computed Tomography (RBYRCT).

The system is designed to support:
- X-ray beam steering simulation
- Layered Bragg reflection modeling
- Synthetic detector data generation
- Future integration with ML and hardware control

---

## Architecture Diagram (Conceptual)

Janus Layout Generator
|
v
CSV Geometry Files
|
v
Houdini
(Beam Steering Sim)
|
v
Beam Path CSV
|
v
Detector Endpoints
|
v
Detector Hitmap
|
v
ML / Reconstruction

---

## Core Components

### 1. Geometry & Layout (Python)

Located in `scripts/`:

- `janus_array_gen.py`
  - Generates concentric Janus-sphere layouts
  - Outputs CSV geometry for Houdini

- `validate_csv.py`
  - Ensures generated layouts are consistent and numeric

---

### 2. Beam Steering Simulation (Houdini)

Located in `houdini/`:

- Houdini SOP networks simulate:
  - Layered Bragg reflection
  - Beam attenuation
  - Directional steering
- VEX shaders encode reflection rules and efficiency models

This layer prioritizes **procedural control logic**, not full Monte Carlo transport.

---

### 3. Data Export & Processing (Python)

Located in `scripts/`:

- `export_beam_paths.py`
  - Exports simulated beam paths from Houdini to CSV

- `make_endpoints_from_paths.py`
  - Intersects rays with a detector plane

- `export_detector_hitmap.py`
  - Bins endpoints into a 2D synthetic detector hitmap

---

### 4. Pipeline Orchestration

- `run_pipeline.py`
  - Runs the full workflow end-to-end
  - Supports skipping Houdini for rapid iteration

---

## Design Philosophy

- **Ray-by-ray first**: steer and stop early rather than scan everything
- **Procedural physics**: encode rules and constraints explicitly
- **Data-centric**: every stage produces inspectable artifacts
- **Hardware-agnostic**: control abstractions map cleanly to future devices

---

## Future Extensions

- ML-based inpainting and stopping criteria
- Feedback control loops using detector residuals
- Hardware command generation for Janus or mirror systems
- Validation via Monte Carlo transport tools
