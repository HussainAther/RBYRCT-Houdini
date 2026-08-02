import csv
import math
import subprocess
import sys

import pytest

from physics.ray_engine import (
    Layer,
    Ray,
    Vec3,
    emit_rectangular_beam,
    trace_ray,
    write_trace_csvs,
)


def test_vec3_rotation_about_y_axis():
    rotated = Vec3(0.0, 0.0, 1.0).rotate_about_axis(Vec3(0.0, 1.0, 0.0), 90.0)
    assert rotated.x == pytest.approx(1.0)
    assert rotated.y == pytest.approx(0.0)
    assert rotated.z == pytest.approx(0.0, abs=1e-12)


def test_emit_rectangular_beam_is_deterministic():
    rays = emit_rectangular_beam(rows=2, columns=3, width=4.0, height=2.0)
    assert len(rays) == 6
    assert rays[0].ray_id == 0
    assert rays[-1].ray_id == 5
    assert rays[0].origin == Vec3(-2.0, -1.0, -10.0)
    assert rays[-1].origin == Vec3(2.0, 1.0, -10.0)
    assert all(ray.direction.magnitude == pytest.approx(1.0) for ray in rays)


def test_trace_records_layers_and_detector_hit():
    ray = Ray(0, Vec3(0.0, 0.0, -5.0), Vec3(0.0, 0.0, 1.0))
    layers = [
        Layer(0, z=0.0, steering_angle_deg=1.0, transmission=0.9),
        Layer(1, z=2.0, steering_angle_deg=1.0, transmission=0.8),
    ]
    result = trace_ray(ray, layers, detector_z=10.0)

    assert result.terminated_reason == "detector_hit"
    assert result.detector_hit is not None
    assert result.detector_hit.intensity == pytest.approx(0.72)
    assert [event.event_type for event in result.events] == [
        "emitted",
        "layer_enter",
        "layer_exit",
        "layer_enter",
        "layer_exit",
        "detector_hit",
    ]
    assert result.events[-1].cumulative_steering_deg == pytest.approx(2.0)
    assert result.detector_hit.x > 0.0


def test_detector_miss_is_recorded():
    ray = Ray(0, Vec3(0.0, 0.0, -1.0), Vec3(1.0, 0.0, 1.0))
    result = trace_ray(
        ray,
        [],
        detector_z=10.0,
        detector_width=1.0,
        detector_height=1.0,
    )
    assert result.terminated_reason == "detector_miss"
    assert result.detector_hit is not None
    assert result.detector_hit.inside_detector is False
    assert result.detector_hit.pixel_x is None


def test_low_intensity_terminates_before_detector():
    ray = Ray(0, Vec3(0.0, 0.0, -1.0), Vec3(0.0, 0.0, 1.0))
    result = trace_ray(
        ray,
        [Layer(0, z=0.0, transmission=0.0001)],
        detector_z=10.0,
        minimum_intensity=0.001,
    )
    assert result.terminated_reason == "low_intensity"
    assert result.detector_hit is None


def test_csv_outputs(tmp_path):
    ray = Ray(0, Vec3(0.0, 0.0, -1.0), Vec3(0.0, 0.0, 1.0))
    result = trace_ray(ray, [], detector_z=1.0)
    paths = write_trace_csvs([result], tmp_path)
    assert set(paths) == {"rays", "events", "detector_hits"}
    with paths["events"].open(newline="", encoding="utf-8") as handle:
        events = list(csv.DictReader(handle))
    assert [event["event_type"] for event in events] == ["emitted", "detector_hit"]


def test_cli(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_ray_engine.py",
            "--rows", "2",
            "--columns", "2",
            "--layers", "2",
            "--output-dir", str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Traced 4 rays" in result.stdout
    assert (tmp_path / "rays.csv").exists()
    assert (tmp_path / "ray_events.csv").exists()
    assert (tmp_path / "detector_hits.csv").exists()
