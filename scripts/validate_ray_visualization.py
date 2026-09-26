#!/usr/bin/env python3
"""Create visualization geometry and validation artifacts from ray-engine CSVs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from analysis.ray_validation import (
    build_detector_occupancy,
    read_detector_hits,
    validate_trajectory_geometry,
    write_validation_outputs,
)
from visualization.ray_geometry import build_trajectory_geometry, read_event_csv, write_geometry_csvs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and validate RBYRCT ray visualization data.")
    parser.add_argument("--events", type=Path, default=Path("data/ray_engine/ray_events.csv"))
    parser.add_argument("--detector-hits", type=Path, default=Path("data/ray_engine/detector_hits.csv"))
    parser.add_argument("--pixels-x", type=int, default=256)
    parser.add_argument("--pixels-y", type=int, default=256)
    parser.add_argument("--output-dir", type=Path, default=Path("data/ray_validation"))
    parser.add_argument("--tolerance", type=float, default=1.0e-9)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        event_rows = read_event_csv(args.events)
        points, segments = build_trajectory_geometry(event_rows)
        geometry_paths = write_geometry_csvs(points, segments, args.output_dir)
        report, issues = validate_trajectory_geometry(points, segments, tolerance=args.tolerance)
        occupancy = build_detector_occupancy(
            read_detector_hits(args.detector_hits),
            pixels_x=args.pixels_x,
            pixels_y=args.pixels_y,
        )
        validation_paths = write_validation_outputs(report, issues, occupancy, args.output_dir)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Error: {exc}") from exc

    print(
        f"Validated {report.ray_count} rays and {report.segment_count} segments: "
        f"{'PASS' if report.passed else 'FAIL'} ({report.error_count} errors, "
        f"{report.warning_count} warnings)."
    )
    for name, path in {**geometry_paths, **validation_paths}.items():
        print(f"{name}: {path}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
