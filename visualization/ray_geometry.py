#!/usr/bin/env python3
"""Convert Phase 1 ray events into visualization-friendly geometry tables.

The module has no Houdini dependency. It performs schema validation and writes
portable point/segment CSV files that can be imported by Houdini, Blender, or
other geometry tools. Houdini-specific geometry creation lives separately in
``houdini/python/import_ray_events.py``.
"""

from __future__ import annotations

import csv
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

REQUIRED_EVENT_FIELDS = {
    "ray_id", "event_index", "event_type", "layer_index",
    "x", "y", "z", "dir_x", "dir_y", "dir_z",
    "energy_kev", "intensity", "cumulative_distance",
    "cumulative_steering_deg",
}

EVENT_STATE_CODES = {
    "emitted": 0,
    "layer_enter": 1,
    "layer_exit": 2,
    "detector_hit": 3,
    "detector_miss": 4,
    "terminated_low_intensity": 5,
    "terminated_no_layer_intersection": 6,
    "terminated_no_detector_intersection": 7,
}


@dataclass(frozen=True)
class TrajectoryPoint:
    point_id: int
    ray_id: int
    event_index: int
    event_type: str
    state_code: int
    layer_index: int
    x: float
    y: float
    z: float
    dir_x: float
    dir_y: float
    dir_z: float
    direction_magnitude: float
    energy_kev: float
    intensity: float
    cumulative_distance: float
    cumulative_steering_deg: float
    is_terminal: int


@dataclass(frozen=True)
class TrajectorySegment:
    segment_id: int
    ray_id: int
    from_point_id: int
    to_point_id: int
    from_event_index: int
    to_event_index: int
    from_event_type: str
    to_event_type: str
    x0: float
    y0: float
    z0: float
    x1: float
    y1: float
    z1: float
    length: float
    intensity_start: float
    intensity_end: float
    steering_start_deg: float
    steering_end_deg: float
    is_zero_length: int


def _parse_int(value: object, field: str, *, blank_value: int = -1) -> int:
    text = "" if value is None else str(value).strip()
    if text == "":
        return blank_value
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"invalid integer in {field}: {value!r}") from exc


def _parse_float(value: object, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid float in {field}: {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"non-finite float in {field}: {value!r}")
    return result


def read_event_csv(path: str | Path) -> list[dict[str, str]]:
    event_path = Path(path).expanduser()
    with event_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or ())
        missing = REQUIRED_EVENT_FIELDS - fields
        if missing:
            raise ValueError(f"event CSV missing fields: {', '.join(sorted(missing))}")
        rows = list(reader)
    if not rows:
        raise ValueError("event CSV contains no events")
    return rows


def build_trajectory_geometry(
    event_rows: Iterable[Mapping[str, object]],
) -> tuple[list[TrajectoryPoint], list[TrajectorySegment]]:
    """Build ordered trajectory points and pairwise segments from event rows."""
    grouped: dict[int, list[Mapping[str, object]]] = {}
    for row in event_rows:
        missing = REQUIRED_EVENT_FIELDS - set(row)
        if missing:
            raise ValueError(f"event row missing fields: {', '.join(sorted(missing))}")
        ray_id = _parse_int(row["ray_id"], "ray_id")
        grouped.setdefault(ray_id, []).append(row)

    points: list[TrajectoryPoint] = []
    segments: list[TrajectorySegment] = []
    point_lookup: dict[tuple[int, int], TrajectoryPoint] = {}

    for ray_id in sorted(grouped):
        ordered = sorted(grouped[ray_id], key=lambda row: _parse_int(row["event_index"], "event_index"))
        seen_indices: set[int] = set()
        for row in ordered:
            event_index = _parse_int(row["event_index"], "event_index")
            if event_index in seen_indices:
                raise ValueError(f"ray {ray_id} has duplicate event_index {event_index}")
            seen_indices.add(event_index)
            event_type = str(row["event_type"]).strip()
            direction = (
                _parse_float(row["dir_x"], "dir_x"),
                _parse_float(row["dir_y"], "dir_y"),
                _parse_float(row["dir_z"], "dir_z"),
            )
            magnitude = math.sqrt(sum(component * component for component in direction))
            point = TrajectoryPoint(
                point_id=len(points),
                ray_id=ray_id,
                event_index=event_index,
                event_type=event_type,
                state_code=EVENT_STATE_CODES.get(event_type, 99),
                layer_index=_parse_int(row["layer_index"], "layer_index"),
                x=_parse_float(row["x"], "x"),
                y=_parse_float(row["y"], "y"),
                z=_parse_float(row["z"], "z"),
                dir_x=direction[0],
                dir_y=direction[1],
                dir_z=direction[2],
                direction_magnitude=magnitude,
                energy_kev=_parse_float(row["energy_kev"], "energy_kev"),
                intensity=_parse_float(row["intensity"], "intensity"),
                cumulative_distance=_parse_float(row["cumulative_distance"], "cumulative_distance"),
                cumulative_steering_deg=_parse_float(
                    row["cumulative_steering_deg"], "cumulative_steering_deg"
                ),
                is_terminal=int(event_type.startswith("terminated_") or event_type.startswith("detector_")),
            )
            points.append(point)
            point_lookup[(ray_id, event_index)] = point

        for previous_row, current_row in zip(ordered, ordered[1:]):
            previous = point_lookup[(ray_id, _parse_int(previous_row["event_index"], "event_index"))]
            current = point_lookup[(ray_id, _parse_int(current_row["event_index"], "event_index"))]
            dx = current.x - previous.x
            dy = current.y - previous.y
            dz = current.z - previous.z
            length = math.sqrt(dx * dx + dy * dy + dz * dz)
            segments.append(
                TrajectorySegment(
                    segment_id=len(segments),
                    ray_id=ray_id,
                    from_point_id=previous.point_id,
                    to_point_id=current.point_id,
                    from_event_index=previous.event_index,
                    to_event_index=current.event_index,
                    from_event_type=previous.event_type,
                    to_event_type=current.event_type,
                    x0=previous.x,
                    y0=previous.y,
                    z0=previous.z,
                    x1=current.x,
                    y1=current.y,
                    z1=current.z,
                    length=length,
                    intensity_start=previous.intensity,
                    intensity_end=current.intensity,
                    steering_start_deg=previous.cumulative_steering_deg,
                    steering_end_deg=current.cumulative_steering_deg,
                    is_zero_length=int(length <= 1.0e-12),
                )
            )
    return points, segments


def write_geometry_csvs(
    points: Sequence[TrajectoryPoint],
    segments: Sequence[TrajectorySegment],
    output_dir: str | Path,
) -> dict[str, Path]:
    directory = Path(output_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "points": directory / "ray_points.csv",
        "segments": directory / "ray_segments.csv",
    }
    for key, records in (("points", points), ("segments", segments)):
        if not records:
            raise ValueError(f"cannot write empty {key} geometry")
        with paths[key].open("w", newline="", encoding="utf-8") as handle:
            fieldnames = list(records[0].__dataclass_fields__)
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(asdict(record) for record in records)
    return {name: path.resolve() for name, path in paths.items()}
