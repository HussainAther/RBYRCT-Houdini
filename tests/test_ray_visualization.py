import csv
import json
import subprocess
import sys

import pytest

from analysis.ray_validation import (
    build_detector_occupancy,
    validate_trajectory_geometry,
    write_validation_outputs,
)
from physics.ray_engine import Layer, Ray, Vec3, trace_ray, write_trace_csvs
from visualization.ray_geometry import (
    build_trajectory_geometry,
    read_event_csv,
    write_geometry_csvs,
)


def _trace(tmp_path, *, angle=2.0):
    ray = Ray(0, Vec3(0.0, 0.0, -5.0), Vec3(0.0, 0.0, 1.0))
    result = trace_ray(
        ray,
        [Layer(0, 0.0, angle, 0.9), Layer(1, 2.0, angle, 0.8)],
        detector_z=10.0,
        detector_width=20.0,
        detector_height=20.0,
        detector_pixels_x=8,
        detector_pixels_y=8,
    )
    return write_trace_csvs([result], tmp_path)


def test_geometry_preserves_order_and_attributes(tmp_path):
    paths = _trace(tmp_path)
    points, segments = build_trajectory_geometry(read_event_csv(paths["events"]))
    assert [point.event_index for point in points] == list(range(6))
    assert points[0].event_type == "emitted"
    assert points[-1].event_type == "detector_hit"
    assert all(point.direction_magnitude == pytest.approx(1.0) for point in points)
    assert len(segments) == len(points) - 1
    assert sum(segment.is_zero_length for segment in segments) == 2


def test_validation_passes_for_engine_output(tmp_path):
    paths = _trace(tmp_path)
    points, segments = build_trajectory_geometry(read_event_csv(paths["events"]))
    report, issues = validate_trajectory_geometry(points, segments)
    assert report.passed
    assert report.error_count == 0
    assert report.detector_hits == 1
    assert issues == []


def test_validation_detects_non_unit_direction(tmp_path):
    paths = _trace(tmp_path)
    rows = read_event_csv(paths["events"])
    rows[0]["dir_z"] = "2.0"
    points, segments = build_trajectory_geometry(rows)
    report, issues = validate_trajectory_geometry(points, segments)
    assert not report.passed
    assert any(issue.code == "direction_not_unit" for issue in issues)


def test_detector_occupancy_is_dense_and_accumulates():
    rows = [
        {"inside_detector": "True", "pixel_x": "1", "pixel_y": "0", "intensity": "0.5"},
        {"inside_detector": "True", "pixel_x": "1", "pixel_y": "0", "intensity": "0.25"},
        {"inside_detector": "False", "pixel_x": "", "pixel_y": "", "intensity": "1.0"},
    ]
    occupancy = build_detector_occupancy(rows, pixels_x=2, pixels_y=2)
    assert len(occupancy) == 4
    occupied = next(row for row in occupancy if row["pixel_x"] == 1 and row["pixel_y"] == 0)
    assert occupied["hit_count"] == 2
    assert occupied["total_intensity"] == pytest.approx(0.75)


def test_writers_and_cli(tmp_path):
    trace_dir = tmp_path / "trace"
    output_dir = tmp_path / "validation"
    paths = _trace(trace_dir)
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_ray_visualization.py",
            "--events", str(paths["events"]),
            "--detector-hits", str(paths["detector_hits"]),
            "--pixels-x", "8",
            "--pixels-y", "8",
            "--output-dir", str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "PASS" in result.stdout
    expected = {
        "ray_points.csv", "ray_segments.csv", "detector_occupancy.csv",
        "validation_summary.json", "validation_issues.csv",
    }
    assert expected <= {path.name for path in output_dir.iterdir()}
    with (output_dir / "validation_summary.json").open(encoding="utf-8") as handle:
        assert json.load(handle)["passed"] is True


def test_read_event_csv_rejects_bad_schema(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("ray_id,event_index\n0,0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing fields"):
        read_event_csv(path)
