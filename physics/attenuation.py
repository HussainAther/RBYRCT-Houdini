#!/usr/bin/env python3
"""Beer-Lambert transport through analytic Phase 2A phantoms."""

from __future__ import annotations

import csv
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

from phantoms.analytic import AnalyticPhantom, PhantomInterval
from physics.ray_engine import DetectorHit, Ray, Vec3, _detector_pixel, _intersect_z_plane


@dataclass(frozen=True)
class AttenuationInteraction:
    ray_id: int
    interaction_index: int
    phantom_id: str
    material_id: str
    entry_x: float
    entry_y: float
    entry_z: float
    exit_x: float
    exit_y: float
    exit_z: float
    path_length: float
    mu: float
    optical_depth: float
    intensity_before: float
    intensity_after: float


@dataclass(frozen=True)
class AttenuationRayResult:
    ray: Ray
    interactions: tuple[AttenuationInteraction, ...]
    detector_hit: DetectorHit | None
    final_intensity: float
    total_path_length: float
    total_optical_depth: float
    terminated_reason: str


def beer_lambert(intensity: float, mu: float, path_length: float) -> float:
    if intensity < 0.0 or mu < 0.0 or path_length < 0.0:
        raise ValueError("intensity, mu, and path_length must be non-negative")
    return intensity * math.exp(-mu * path_length)


def _merged_intervals(
    phantoms: Sequence[AnalyticPhantom], origin: Vec3, direction: Vec3
) -> list[PhantomInterval]:
    intervals = [interval for phantom in phantoms for interval in phantom.intervals(origin, direction)]
    intervals.sort(key=lambda item: (item.t_enter, item.t_exit, item.material.material_id))
    for previous, current in zip(intervals, intervals[1:]):
        if current.t_enter < previous.t_exit - 1.0e-10:
            raise ValueError(
                "overlapping phantom intervals are ambiguous; use a composite phantom such as NestedSpherePhantom"
            )
    return intervals


def trace_attenuation_ray(
    ray: Ray,
    phantoms: Sequence[AnalyticPhantom],
    *,
    detector_z: float,
    detector_width: float = 50.0,
    detector_height: float = 50.0,
    detector_pixels_x: int = 256,
    detector_pixels_y: int = 256,
) -> AttenuationRayResult:
    direction = ray.direction.normalized()
    intervals = _merged_intervals(phantoms, ray.origin, direction)
    intensity = ray.intensity
    interactions: list[AttenuationInteraction] = []
    total_path = 0.0
    total_tau = 0.0

    for index, interval in enumerate(intervals):
        entry = ray.origin + direction * interval.t_enter
        exit_ = ray.origin + direction * interval.t_exit
        length = interval.path_length
        tau = interval.material.mu * length
        after = beer_lambert(intensity, interval.material.mu, length)
        interactions.append(
            AttenuationInteraction(
                ray_id=ray.ray_id,
                interaction_index=index,
                phantom_id=interval.phantom_id,
                material_id=interval.material.material_id,
                entry_x=entry.x,
                entry_y=entry.y,
                entry_z=entry.z,
                exit_x=exit_.x,
                exit_y=exit_.y,
                exit_z=exit_.z,
                path_length=length,
                mu=interval.material.mu,
                optical_depth=tau,
                intensity_before=intensity,
                intensity_after=after,
            )
        )
        intensity = after
        total_path += length
        total_tau += tau

    detector_intersection = _intersect_z_plane(ray.origin, direction, detector_z)
    if detector_intersection is None:
        return AttenuationRayResult(
            ray, tuple(interactions), None, intensity, total_path, total_tau, "no_detector_intersection"
        )
    position, _ = detector_intersection
    pixel_x, pixel_y, inside = _detector_pixel(
        position,
        width=detector_width,
        height=detector_height,
        pixels_x=detector_pixels_x,
        pixels_y=detector_pixels_y,
    )
    hit = DetectorHit(
        ray_id=ray.ray_id,
        x=position.x,
        y=position.y,
        z=position.z,
        intensity=intensity,
        energy_kev=ray.energy_kev,
        pixel_x=pixel_x,
        pixel_y=pixel_y,
        inside_detector=inside,
    )
    return AttenuationRayResult(
        ray,
        tuple(interactions),
        hit,
        intensity,
        total_path,
        total_tau,
        "detector_hit" if inside else "detector_miss",
    )


def trace_attenuation_rays(
    rays: Iterable[Ray], phantoms: Sequence[AnalyticPhantom], **kwargs: object
) -> list[AttenuationRayResult]:
    return [trace_attenuation_ray(ray, phantoms, **kwargs) for ray in rays]


def write_attenuation_csvs(
    results: Sequence[AttenuationRayResult], output_dir: str | Path
) -> dict[str, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "summaries": directory / "attenuation_rays.csv",
        "interactions": directory / "phantom_interactions.csv",
        "detector": directory / "detector_intensity.csv",
    }
    with paths["summaries"].open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "ray_id", "initial_intensity", "final_intensity", "total_path_length",
            "total_optical_depth", "interaction_count", "terminated_reason",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            writer.writerow({
                "ray_id": result.ray.ray_id,
                "initial_intensity": result.ray.intensity,
                "final_intensity": result.final_intensity,
                "total_path_length": result.total_path_length,
                "total_optical_depth": result.total_optical_depth,
                "interaction_count": len(result.interactions),
                "terminated_reason": result.terminated_reason,
            })
    with paths["interactions"].open("w", newline="", encoding="utf-8") as handle:
        fields = list(AttenuationInteraction.__dataclass_fields__)
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            writer.writerows(asdict(item) for item in result.interactions)
    with paths["detector"].open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "ray_id", "x", "y", "z", "pixel_x", "pixel_y", "inside_detector",
            "energy_kev", "initial_intensity", "final_intensity", "transmission",
            "total_path_length", "total_optical_depth",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            if result.detector_hit is None:
                continue
            hit = result.detector_hit
            writer.writerow({
                "ray_id": result.ray.ray_id,
                "x": hit.x, "y": hit.y, "z": hit.z,
                "pixel_x": hit.pixel_x, "pixel_y": hit.pixel_y,
                "inside_detector": hit.inside_detector,
                "energy_kev": hit.energy_kev,
                "initial_intensity": result.ray.intensity,
                "final_intensity": result.final_intensity,
                "transmission": result.final_intensity / result.ray.intensity if result.ray.intensity else 0.0,
                "total_path_length": result.total_path_length,
                "total_optical_depth": result.total_optical_depth,
            })
    return {key: value.resolve() for key, value in paths.items()}
