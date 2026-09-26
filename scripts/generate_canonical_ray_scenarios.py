#!/usr/bin/env python3
"""Generate zero, symmetric, and exaggerated steering validation scenarios."""

from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from physics.ray_engine import Layer, Vec3, emit_rectangular_beam, trace_rays, write_trace_csvs
from analysis.ray_validation import build_detector_occupancy, read_detector_hits, validate_trajectory_geometry, write_validation_outputs
from visualization.ray_geometry import build_trajectory_geometry, read_event_csv, write_geometry_csvs


def _scenario_layers(name: str) -> list[Layer]:
    angles = {
        "zero_steering": [0.0, 0.0, 0.0, 0.0],
        "symmetric_steering": [2.0, 2.0, -2.0, -2.0],
        "exaggerated_steering": [8.0, 8.0, 8.0, 8.0],
    }[name]
    return [
        Layer(index, z=float(index) * 2.0, steering_angle_deg=angle, transmission=0.97)
        for index, angle in enumerate(angles)
    ]


def main() -> int:
    root = Path("data/canonical_scenarios")
    rays = emit_rectangular_beam(rows=3, columns=3, width=4.0, height=4.0, source_z=-8.0)
    for name in ("zero_steering", "symmetric_steering", "exaggerated_steering"):
        directory = root / name
        results = trace_rays(
            rays,
            _scenario_layers(name),
            detector_z=16.0,
            detector_width=30.0,
            detector_height=30.0,
            detector_pixels_x=32,
            detector_pixels_y=32,
        )
        paths = write_trace_csvs(results, directory)
        points, segments = build_trajectory_geometry(read_event_csv(paths["events"]))
        write_geometry_csvs(points, segments, directory)
        report, issues = validate_trajectory_geometry(points, segments)
        occupancy = build_detector_occupancy(
            read_detector_hits(paths["detector_hits"]), pixels_x=32, pixels_y=32
        )
        write_validation_outputs(report, issues, occupancy, directory)
        print(f"{name}: {'PASS' if report.passed else 'FAIL'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
