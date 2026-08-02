#!/usr/bin/env python3
"""Dependency-free idealized ray propagation for RBYRCT geometry experiments.

This module is intentionally a geometric prototype, not a validated X-ray
transport or Bragg-diffraction solver. Rays intersect ordered z-planes, receive
configurable rotations at steering layers, lose intensity according to a simple
per-layer transmission factor, and are finally intersected with a detector
plane. Every state transition is recorded as a structured event.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

_EPSILON = 1.0e-12


@dataclass(frozen=True)
class Vec3:
    """Small immutable 3D vector with the operations needed by the tracer."""

    x: float
    y: float
    z: float

    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> "Vec3":
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    __rmul__ = __mul__

    def dot(self, other: "Vec3") -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: "Vec3") -> "Vec3":
        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    @property
    def magnitude(self) -> float:
        return math.sqrt(self.dot(self))

    def normalized(self) -> "Vec3":
        magnitude = self.magnitude
        if magnitude <= _EPSILON:
            raise ValueError("cannot normalize a zero-length vector")
        return self * (1.0 / magnitude)

    def rotate_about_axis(self, axis: "Vec3", angle_deg: float) -> "Vec3":
        """Return this vector rotated with Rodrigues' rotation formula."""
        unit_axis = axis.normalized()
        angle = math.radians(angle_deg)
        cosine = math.cos(angle)
        sine = math.sin(angle)
        return (
            self * cosine
            + unit_axis.cross(self) * sine
            + unit_axis * (unit_axis.dot(self) * (1.0 - cosine))
        )


@dataclass(frozen=True)
class Ray:
    """An emitted ray before propagation."""

    ray_id: int
    origin: Vec3
    direction: Vec3
    energy_kev: float = 60.0
    intensity: float = 1.0

    def __post_init__(self) -> None:
        if self.ray_id < 0:
            raise ValueError("ray_id cannot be negative")
        if self.energy_kev <= 0:
            raise ValueError("energy_kev must be positive")
        if not 0.0 <= self.intensity <= 1.0:
            raise ValueError("intensity must be between 0 and 1")
        object.__setattr__(self, "direction", self.direction.normalized())


@dataclass(frozen=True)
class Layer:
    """One idealized steering plane perpendicular to the z-axis."""

    layer_index: int
    z: float
    steering_angle_deg: float = 0.0
    transmission: float = 1.0
    rotation_axis: Vec3 = Vec3(0.0, 1.0, 0.0)

    def __post_init__(self) -> None:
        if self.layer_index < 0:
            raise ValueError("layer_index cannot be negative")
        if not 0.0 <= self.transmission <= 1.0:
            raise ValueError("transmission must be between 0 and 1")
        self.rotation_axis.normalized()


@dataclass(frozen=True)
class RayEvent:
    """A complete recorded ray state at one propagation event."""

    ray_id: int
    event_index: int
    event_type: str
    layer_index: int | None
    x: float
    y: float
    z: float
    dir_x: float
    dir_y: float
    dir_z: float
    energy_kev: float
    intensity: float
    cumulative_distance: float
    cumulative_steering_deg: float


@dataclass(frozen=True)
class DetectorHit:
    """A ray intersection with a rectangular detector plane."""

    ray_id: int
    x: float
    y: float
    z: float
    intensity: float
    energy_kev: float
    pixel_x: int | None
    pixel_y: int | None
    inside_detector: bool


@dataclass(frozen=True)
class RayTraceResult:
    """Recorded propagation history and optional detector result for one ray."""

    ray: Ray
    events: tuple[RayEvent, ...]
    detector_hit: DetectorHit | None
    terminated_reason: str


def _intersect_z_plane(position: Vec3, direction: Vec3, z: float) -> tuple[Vec3, float] | None:
    if abs(direction.z) <= _EPSILON:
        return None
    distance = (z - position.z) / direction.z
    if distance <= _EPSILON:
        return None
    return position + direction * distance, distance


def _detector_pixel(
    point: Vec3,
    *,
    width: float,
    height: float,
    pixels_x: int,
    pixels_y: int,
) -> tuple[int | None, int | None, bool]:
    inside = -width / 2.0 <= point.x <= width / 2.0 and -height / 2.0 <= point.y <= height / 2.0
    if not inside:
        return None, None, False
    normalized_x = min((point.x + width / 2.0) / width, 1.0 - _EPSILON)
    normalized_y = min((point.y + height / 2.0) / height, 1.0 - _EPSILON)
    return int(normalized_x * pixels_x), int(normalized_y * pixels_y), True


def emit_rectangular_beam(
    *,
    rows: int = 5,
    columns: int = 5,
    width: float = 8.0,
    height: float = 8.0,
    source_z: float = -10.0,
    target: Vec3 = Vec3(0.0, 0.0, 0.0),
    energy_kev: float = 60.0,
    intensity: float = 1.0,
) -> list[Ray]:
    """Emit a deterministic grid of rays aimed from a source plane at target."""
    if rows <= 0 or columns <= 0:
        raise ValueError("rows and columns must be positive")
    if width < 0 or height < 0:
        raise ValueError("beam width and height cannot be negative")

    rays: list[Ray] = []
    for row in range(rows):
        y = 0.0 if rows == 1 else -height / 2.0 + height * row / (rows - 1)
        for column in range(columns):
            x = 0.0 if columns == 1 else -width / 2.0 + width * column / (columns - 1)
            origin = Vec3(x, y, source_z)
            rays.append(
                Ray(
                    ray_id=len(rays),
                    origin=origin,
                    direction=target - origin,
                    energy_kev=energy_kev,
                    intensity=intensity,
                )
            )
    return rays


def trace_ray(
    ray: Ray,
    layers: Sequence[Layer],
    *,
    detector_z: float,
    detector_width: float = 50.0,
    detector_height: float = 50.0,
    detector_pixels_x: int = 256,
    detector_pixels_y: int = 256,
    minimum_intensity: float = 1.0e-6,
) -> RayTraceResult:
    """Propagate one ray through ordered steering planes to a detector."""
    if detector_width <= 0 or detector_height <= 0:
        raise ValueError("detector dimensions must be positive")
    if detector_pixels_x <= 0 or detector_pixels_y <= 0:
        raise ValueError("detector pixel counts must be positive")
    if minimum_intensity < 0:
        raise ValueError("minimum_intensity cannot be negative")

    ordered_layers = sorted(layers, key=lambda layer: layer.z)
    position = ray.origin
    direction = ray.direction
    intensity = ray.intensity
    cumulative_distance = 0.0
    cumulative_steering = 0.0
    events: list[RayEvent] = []

    def record(event_type: str, layer_index: int | None = None) -> None:
        events.append(
            RayEvent(
                ray_id=ray.ray_id,
                event_index=len(events),
                event_type=event_type,
                layer_index=layer_index,
                x=position.x,
                y=position.y,
                z=position.z,
                dir_x=direction.x,
                dir_y=direction.y,
                dir_z=direction.z,
                energy_kev=ray.energy_kev,
                intensity=intensity,
                cumulative_distance=cumulative_distance,
                cumulative_steering_deg=cumulative_steering,
            )
        )

    record("emitted")

    for layer in ordered_layers:
        intersection = _intersect_z_plane(position, direction, layer.z)
        if intersection is None:
            record("terminated_no_layer_intersection", layer.layer_index)
            return RayTraceResult(ray, tuple(events), None, "no_layer_intersection")

        position, distance = intersection
        cumulative_distance += distance
        record("layer_enter", layer.layer_index)

        direction = direction.rotate_about_axis(layer.rotation_axis, layer.steering_angle_deg).normalized()
        cumulative_steering += abs(layer.steering_angle_deg)
        intensity *= layer.transmission
        record("layer_exit", layer.layer_index)

        if intensity < minimum_intensity:
            record("terminated_low_intensity", layer.layer_index)
            return RayTraceResult(ray, tuple(events), None, "low_intensity")

    intersection = _intersect_z_plane(position, direction, detector_z)
    if intersection is None:
        record("terminated_no_detector_intersection")
        return RayTraceResult(ray, tuple(events), None, "no_detector_intersection")

    position, distance = intersection
    cumulative_distance += distance
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
    record("detector_hit" if inside else "detector_miss")
    return RayTraceResult(ray, tuple(events), hit, "detector_hit" if inside else "detector_miss")


def trace_rays(rays: Iterable[Ray], layers: Sequence[Layer], **kwargs: object) -> list[RayTraceResult]:
    """Trace each ray with identical geometry and detector settings."""
    return [trace_ray(ray, layers, **kwargs) for ray in rays]


def write_trace_csvs(results: Sequence[RayTraceResult], output_dir: str | Path) -> dict[str, Path]:
    """Write ray summaries, event histories, and detector records to CSV."""
    directory = Path(output_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "rays": directory / "rays.csv",
        "events": directory / "ray_events.csv",
        "detector_hits": directory / "detector_hits.csv",
    }

    with paths["rays"].open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "ray_id", "origin_x", "origin_y", "origin_z", "dir_x", "dir_y", "dir_z",
            "energy_kev", "initial_intensity", "terminated_reason", "event_count",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            ray = result.ray
            writer.writerow({
                "ray_id": ray.ray_id,
                "origin_x": ray.origin.x,
                "origin_y": ray.origin.y,
                "origin_z": ray.origin.z,
                "dir_x": ray.direction.x,
                "dir_y": ray.direction.y,
                "dir_z": ray.direction.z,
                "energy_kev": ray.energy_kev,
                "initial_intensity": ray.intensity,
                "terminated_reason": result.terminated_reason,
                "event_count": len(result.events),
            })

    event_fieldnames = list(RayEvent.__dataclass_fields__)
    with paths["events"].open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=event_fieldnames)
        writer.writeheader()
        for result in results:
            for event in result.events:
                writer.writerow(asdict(event))

    hit_fieldnames = list(DetectorHit.__dataclass_fields__)
    with paths["detector_hits"].open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=hit_fieldnames)
        writer.writeheader()
        for result in results:
            if result.detector_hit is not None:
                writer.writerow(asdict(result.detector_hit))

    return {name: path.resolve() for name, path in paths.items()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the idealized RBYRCT ray engine.")
    parser.add_argument("--rows", type=int, default=5)
    parser.add_argument("--columns", type=int, default=5)
    parser.add_argument("--beam-width", type=float, default=8.0)
    parser.add_argument("--beam-height", type=float, default=8.0)
    parser.add_argument("--source-z", type=float, default=-10.0)
    parser.add_argument("--layers", type=int, default=5)
    parser.add_argument("--first-layer-z", type=float, default=0.0)
    parser.add_argument("--layer-spacing", type=float, default=2.5)
    parser.add_argument("--steering-per-layer-deg", type=float, default=1.0)
    parser.add_argument("--transmission-per-layer", type=float, default=0.98)
    parser.add_argument("--detector-z", type=float, default=20.0)
    parser.add_argument("--detector-width", type=float, default=50.0)
    parser.add_argument("--detector-height", type=float, default=50.0)
    parser.add_argument("--detector-pixels-x", type=int, default=256)
    parser.add_argument("--detector-pixels-y", type=int, default=256)
    parser.add_argument("--energy-kev", type=float, default=60.0)
    parser.add_argument("--output-dir", type=Path, default=Path("data/ray_engine"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.layers < 0:
            raise ValueError("layers cannot be negative")
        layers = [
            Layer(
                layer_index=index,
                z=args.first_layer_z + index * args.layer_spacing,
                steering_angle_deg=args.steering_per_layer_deg,
                transmission=args.transmission_per_layer,
            )
            for index in range(args.layers)
        ]
        rays = emit_rectangular_beam(
            rows=args.rows,
            columns=args.columns,
            width=args.beam_width,
            height=args.beam_height,
            source_z=args.source_z,
            energy_kev=args.energy_kev,
        )
        results = trace_rays(
            rays,
            layers,
            detector_z=args.detector_z,
            detector_width=args.detector_width,
            detector_height=args.detector_height,
            detector_pixels_x=args.detector_pixels_x,
            detector_pixels_y=args.detector_pixels_y,
        )
        paths = write_trace_csvs(results, args.output_dir)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Error: {exc}") from exc

    hits = sum(result.terminated_reason == "detector_hit" for result in results)
    print(f"Traced {len(results)} rays; {hits} hit the active detector area.")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
