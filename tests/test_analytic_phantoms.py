import csv
import json
import math
import subprocess
import sys

import pytest

from analysis.attenuation_validation import validate_results
from phantoms import Material, NestedSpherePhantom, SlabPhantom, SpherePhantom
from physics.attenuation import beer_lambert, trace_attenuation_ray, write_attenuation_csvs
from physics.ray_engine import Ray, Vec3


def test_beer_lambert():
    assert beer_lambert(1.0, 0.2, 3.0) == pytest.approx(math.exp(-0.6))


def test_slab_exact_path_length():
    slab = SlabPhantom("slab", Material("water", 0.1), 0.0, 4.0)
    ray = Ray(0, Vec3(0.0, 0.0, -2.0), Vec3(0.0, 0.0, 1.0))
    interval = slab.intervals(ray.origin, ray.direction)[0]
    assert interval.path_length == pytest.approx(4.0)


def test_oblique_slab_path_length():
    slab = SlabPhantom("slab", Material("water", 0.1), 0.0, 4.0)
    ray = Ray(0, Vec3(0.0, 0.0, -2.0), Vec3(1.0, 0.0, 1.0))
    interval = slab.intervals(ray.origin, ray.direction)[0]
    assert interval.path_length == pytest.approx(4.0 / ray.direction.z)


def test_sphere_chord_and_miss_and_tangent():
    sphere = SpherePhantom("sphere", Material("soft", 0.2), Vec3(0.0, 0.0, 0.0), 2.0)
    central = Ray(0, Vec3(0.0, 0.0, -5.0), Vec3(0.0, 0.0, 1.0))
    offset = Ray(1, Vec3(1.0, 0.0, -5.0), Vec3(0.0, 0.0, 1.0))
    tangent = Ray(2, Vec3(2.0, 0.0, -5.0), Vec3(0.0, 0.0, 1.0))
    miss = Ray(3, Vec3(2.1, 0.0, -5.0), Vec3(0.0, 0.0, 1.0))
    assert sphere.intervals(central.origin, central.direction)[0].path_length == pytest.approx(4.0)
    assert sphere.intervals(offset.origin, offset.direction)[0].path_length == pytest.approx(2 * math.sqrt(3))
    assert sphere.intervals(tangent.origin, tangent.direction) == ()
    assert sphere.intervals(miss.origin, miss.direction) == ()


def test_nested_sphere_replaces_outer_material():
    nested = NestedSpherePhantom(
        "nested", Material("outer", 0.1), Material("inner", 0.3),
        Vec3(0.0, 0.0, 0.0), 3.0, 1.0,
    )
    ray = Ray(0, Vec3(0.0, 0.0, -5.0), Vec3(0.0, 0.0, 1.0))
    intervals = nested.intervals(ray.origin, ray.direction)
    assert [item.material.material_id for item in intervals] == ["outer", "inner", "outer"]
    assert [item.path_length for item in intervals] == pytest.approx([2.0, 2.0, 2.0])
    result = trace_attenuation_ray(ray, [nested], detector_z=5.0)
    assert result.total_path_length == pytest.approx(6.0)
    assert result.total_optical_depth == pytest.approx(0.1 * 4.0 + 0.3 * 2.0)
    assert result.final_intensity == pytest.approx(math.exp(-1.0))


def test_interaction_records_and_detector_output(tmp_path):
    sphere = SpherePhantom("sphere", Material("soft", 0.2), Vec3(0.0, 0.0, 0.0), 2.0)
    ray = Ray(0, Vec3(0.0, 0.0, -5.0), Vec3(0.0, 0.0, 1.0))
    result = trace_attenuation_ray(ray, [sphere], detector_z=5.0, detector_pixels_x=8, detector_pixels_y=8)
    assert len(result.interactions) == 1
    interaction = result.interactions[0]
    assert interaction.entry_z == pytest.approx(-2.0)
    assert interaction.exit_z == pytest.approx(2.0)
    paths = write_attenuation_csvs([result], tmp_path)
    with paths["interactions"].open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["material_id"] == "soft"
    assert float(rows[0]["path_length"]) == pytest.approx(4.0)


def test_validation_compares_closed_form():
    sphere = SpherePhantom("sphere", Material("soft", 0.2), Vec3(0.0, 0.0, 0.0), 2.0)
    ray = Ray(0, Vec3(0.0, 0.0, -5.0), Vec3(0.0, 0.0, 1.0))
    result = trace_attenuation_ray(ray, [sphere], detector_z=5.0)
    summary, rows = validate_results(
        "sphere", [result], lambda _: 4.0, lambda _: math.exp(-0.8)
    )
    assert summary.passed
    assert rows[0].passed


def test_canonical_scenario_cli(tmp_path):
    completed = subprocess.run(
        [sys.executable, "scripts/generate_analytic_phantom_scenarios.py", "--output-dir", str(tmp_path)],
        check=True, capture_output=True, text=True,
    )
    assert completed.stdout.count("PASS") == 4
    for name in ("empty_field", "uniform_slab", "uniform_sphere", "nested_sphere"):
        directory = tmp_path / name
        assert (directory / "attenuation_rays.csv").exists()
        assert (directory / "phantom_interactions.csv").exists()
        assert (directory / "detector_intensity.csv").exists()
        with (directory / "analytic_validation_summary.json").open(encoding="utf-8") as handle:
            assert json.load(handle)["passed"] is True
