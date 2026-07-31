#!/usr/bin/env python3
"""Generate concentric Janus-sphere layers for Houdini visualization.

This module produces deterministic geometry and metadata. The per-layer steering
angle is an idealized visualization parameter; it is not a validated Bragg-law
calculation.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True)
class JanusSphere:
    """One sphere location and its simulation metadata."""

    sphere_id: int
    layer_index: int
    ring_index: int
    x: float
    y: float
    z: float
    sphere_radius: float
    ring_radius: float
    azimuth_deg: float
    steering_angle_deg: float


FIELDNAMES = list(JanusSphere.__dataclass_fields__)


def generate_array(
    *,
    num_layers: int = 11,
    spheres_per_layer: int = 24,
    sphere_radius: float = 1.0,
    layer_spacing: float = 2.5,
    ring_radius: float = 20.0,
    steering_per_layer_deg: float = 4.0,
) -> list[JanusSphere]:
    """Return a deterministic concentric array.

    Raises:
        ValueError: If a count is non-positive or a geometric value is invalid.
    """
    if num_layers <= 0:
        raise ValueError("num_layers must be positive")
    if spheres_per_layer <= 0:
        raise ValueError("spheres_per_layer must be positive")
    if sphere_radius <= 0:
        raise ValueError("sphere_radius must be positive")
    if layer_spacing < 0:
        raise ValueError("layer_spacing cannot be negative")
    if ring_radius < 0:
        raise ValueError("ring_radius cannot be negative")

    rows: list[JanusSphere] = []
    sphere_id = 0
    for layer_index in range(num_layers):
        z = layer_index * layer_spacing
        steering_angle = layer_index * steering_per_layer_deg
        for ring_index in range(spheres_per_layer):
            azimuth_rad = 2.0 * math.pi * ring_index / spheres_per_layer
            rows.append(
                JanusSphere(
                    sphere_id=sphere_id,
                    layer_index=layer_index,
                    ring_index=ring_index,
                    x=ring_radius * math.cos(azimuth_rad),
                    y=ring_radius * math.sin(azimuth_rad),
                    z=z,
                    sphere_radius=sphere_radius,
                    ring_radius=ring_radius,
                    azimuth_deg=math.degrees(azimuth_rad),
                    steering_angle_deg=steering_angle,
                )
            )
            sphere_id += 1
    return rows


def write_csv(rows: Iterable[JanusSphere], output_path: str | Path) -> Path:
    """Write sphere records to CSV and return the resolved output path."""
    path = Path(output_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
    return path.resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate concentric Janus-sphere layers for Houdini."
    )
    parser.add_argument("--layers", type=int, default=11)
    parser.add_argument("--spheres-per-layer", type=int, default=24)
    parser.add_argument("--sphere-radius", type=float, default=1.0)
    parser.add_argument("--layer-spacing", type=float, default=2.5)
    parser.add_argument("--ring-radius", type=float, default=20.0)
    parser.add_argument("--steering-per-layer-deg", type=float, default=4.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/janus_layers_concentric.csv"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        rows = generate_array(
            num_layers=args.layers,
            spheres_per_layer=args.spheres_per_layer,
            sphere_radius=args.sphere_radius,
            layer_spacing=args.layer_spacing,
            ring_radius=args.ring_radius,
            steering_per_layer_deg=args.steering_per_layer_deg,
        )
        output = write_csv(rows, args.output)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Error: {exc}") from exc

    print(f"Wrote {len(rows)} Janus-sphere records to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
