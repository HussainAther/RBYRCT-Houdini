#!/usr/bin/env python3
"""Generate the four canonical Phase 2A phantom datasets."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.attenuation_validation import validate_results, write_validation_report
from phantoms import Material, NestedSpherePhantom, SlabPhantom, SpherePhantom
from physics.attenuation import trace_attenuation_rays, write_attenuation_csvs
from physics.ray_engine import Ray, Vec3


def parallel_beam(xs: list[float], *, source_z: float = -10.0) -> list[Ray]:
    return [Ray(i, Vec3(x, 0.0, source_z), Vec3(0.0, 0.0, 1.0)) for i, x in enumerate(xs)]


def run_scenario(name: str, rays: list[Ray], phantoms, expected_path, expected_intensity, out: Path) -> None:
    results = trace_attenuation_rays(
        rays,
        phantoms,
        detector_z=15.0,
        detector_width=20.0,
        detector_height=20.0,
        detector_pixels_x=64,
        detector_pixels_y=64,
    )
    out.mkdir(parents=True, exist_ok=True)
    write_attenuation_csvs(results, out)
    summary, rows = validate_results(name, results, expected_path, expected_intensity)
    write_validation_report(summary, rows, out)
    print(f"{name}: {'PASS' if summary.passed else 'FAIL'} ({summary.ray_count} rays)")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("data/analytic_phantoms"))
    args = parser.parse_args(argv)
    xs = [-4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0]
    rays = parallel_beam(xs)

    run_scenario(
        "empty_field", rays, [],
        lambda result: 0.0,
        lambda result: result.ray.intensity,
        args.output_dir / "empty_field",
    )

    slab_mu = 0.12
    slab_thickness = 4.0
    slab = SlabPhantom("slab", Material("uniform_slab", slab_mu), 0.0, slab_thickness)
    run_scenario(
        "uniform_slab", rays, [slab],
        lambda result: slab_thickness,
        lambda result: result.ray.intensity * math.exp(-slab_mu * slab_thickness),
        args.output_dir / "uniform_slab",
    )

    sphere_mu = 0.15
    radius = 3.0
    sphere = SpherePhantom("sphere", Material("uniform_sphere", sphere_mu), Vec3(0.0, 0.0, 3.0), radius)
    def sphere_length(result):
        x = result.ray.origin.x
        return 2.0 * math.sqrt(max(0.0, radius * radius - x * x)) if abs(x) < radius else 0.0
    run_scenario(
        "uniform_sphere", rays, [sphere],
        sphere_length,
        lambda result: result.ray.intensity * math.exp(-sphere_mu * sphere_length(result)),
        args.output_dir / "uniform_sphere",
    )

    outer_mu, inner_mu = 0.08, 0.25
    outer_radius, inner_radius = 4.0, 1.5
    nested = NestedSpherePhantom(
        "nested_sphere", Material("outer", outer_mu), Material("inner", inner_mu),
        Vec3(0.0, 0.0, 3.0), outer_radius, inner_radius,
    )
    def nested_lengths(result):
        x = result.ray.origin.x
        outer = 2.0 * math.sqrt(max(0.0, outer_radius ** 2 - x ** 2)) if abs(x) < outer_radius else 0.0
        inner = 2.0 * math.sqrt(max(0.0, inner_radius ** 2 - x ** 2)) if abs(x) < inner_radius else 0.0
        return outer, inner
    run_scenario(
        "nested_sphere", rays, [nested],
        lambda result: nested_lengths(result)[0],
        lambda result: result.ray.intensity * math.exp(
            -outer_mu * (nested_lengths(result)[0] - nested_lengths(result)[1])
            -inner_mu * nested_lengths(result)[1]
        ),
        args.output_dir / "nested_sphere",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
