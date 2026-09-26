#!/usr/bin/env python3
"""Validation and detector-occupancy analysis for Phase 1 ray traces."""

from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from visualization.ray_geometry import TrajectoryPoint, TrajectorySegment


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    ray_id: int
    event_index: int
    message: str


@dataclass(frozen=True)
class ValidationReport:
    passed: bool
    ray_count: int
    point_count: int
    segment_count: int
    detector_hits: int
    detector_misses: int
    terminated_rays: int
    zero_length_transition_count: int
    max_direction_norm_error: float
    max_distance_continuity_error: float
    issue_count: int
    error_count: int
    warning_count: int


_ALLOWED_ZERO_LENGTH_TRANSITIONS = {("layer_enter", "layer_exit")}


def validate_trajectory_geometry(
    points: Sequence[TrajectoryPoint],
    segments: Sequence[TrajectorySegment],
    *,
    tolerance: float = 1.0e-9,
) -> tuple[ValidationReport, list[ValidationIssue]]:
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")
    issues: list[ValidationIssue] = []
    grouped_points: dict[int, list[TrajectoryPoint]] = defaultdict(list)
    grouped_segments: dict[int, list[TrajectorySegment]] = defaultdict(list)
    for point in points:
        grouped_points[point.ray_id].append(point)
    for segment in segments:
        grouped_segments[segment.ray_id].append(segment)

    max_norm_error = 0.0
    max_distance_error = 0.0
    zero_length_count = 0

    for ray_id, ray_points in grouped_points.items():
        ordered = sorted(ray_points, key=lambda point: point.event_index)
        expected_indices = list(range(len(ordered)))
        actual_indices = [point.event_index for point in ordered]
        if actual_indices != expected_indices:
            issues.append(ValidationIssue(
                "error", "non_contiguous_event_indices", ray_id, actual_indices[0],
                f"expected event indices {expected_indices}, received {actual_indices}",
            ))
        for point in ordered:
            norm_error = abs(point.direction_magnitude - 1.0)
            max_norm_error = max(max_norm_error, norm_error)
            if norm_error > tolerance:
                issues.append(ValidationIssue(
                    "error", "direction_not_unit", ray_id, point.event_index,
                    f"direction magnitude is {point.direction_magnitude:.12g}",
                ))
            if not 0.0 <= point.intensity <= 1.0:
                issues.append(ValidationIssue(
                    "error", "intensity_out_of_range", ray_id, point.event_index,
                    f"intensity is {point.intensity:.12g}",
                ))

        previous_distance = -math.inf
        for point in ordered:
            if point.cumulative_distance + tolerance < previous_distance:
                issues.append(ValidationIssue(
                    "error", "distance_decreased", ray_id, point.event_index,
                    "cumulative distance decreased",
                ))
            previous_distance = point.cumulative_distance

        ray_segments = sorted(grouped_segments.get(ray_id, []), key=lambda segment: segment.from_event_index)
        if len(ray_segments) != max(0, len(ordered) - 1):
            issues.append(ValidationIssue(
                "error", "segment_count_mismatch", ray_id, -1,
                f"expected {max(0, len(ordered) - 1)} segments, received {len(ray_segments)}",
            ))
        point_by_index = {point.event_index: point for point in ordered}
        for segment in ray_segments:
            start = point_by_index.get(segment.from_event_index)
            end = point_by_index.get(segment.to_event_index)
            if start is None or end is None:
                issues.append(ValidationIssue(
                    "error", "segment_endpoint_missing", ray_id, segment.from_event_index,
                    "segment references a missing point",
                ))
                continue
            endpoint_error = max(
                abs(segment.x0 - start.x), abs(segment.y0 - start.y), abs(segment.z0 - start.z),
                abs(segment.x1 - end.x), abs(segment.y1 - end.y), abs(segment.z1 - end.z),
            )
            if endpoint_error > tolerance:
                issues.append(ValidationIssue(
                    "error", "segment_endpoint_mismatch", ray_id, segment.from_event_index,
                    f"segment endpoint mismatch is {endpoint_error:.12g}",
                ))
            expected_distance_delta = end.cumulative_distance - start.cumulative_distance
            distance_error = abs(segment.length - expected_distance_delta)
            max_distance_error = max(max_distance_error, distance_error)
            if distance_error > tolerance:
                issues.append(ValidationIssue(
                    "error", "distance_continuity_error", ray_id, segment.to_event_index,
                    f"segment length differs from cumulative-distance delta by {distance_error:.12g}",
                ))
            if segment.is_zero_length:
                zero_length_count += 1
                transition = (segment.from_event_type, segment.to_event_type)
                if transition not in _ALLOWED_ZERO_LENGTH_TRANSITIONS:
                    issues.append(ValidationIssue(
                        "warning", "unexpected_zero_length_segment", ray_id, segment.to_event_index,
                        f"zero-length transition {transition[0]} -> {transition[1]}",
                    ))

    terminal_types = [point.event_type for point in points if point.is_terminal]
    detector_hits = terminal_types.count("detector_hit")
    detector_misses = terminal_types.count("detector_miss")
    terminated = sum(event_type.startswith("terminated_") for event_type in terminal_types)
    error_count = sum(issue.severity == "error" for issue in issues)
    warning_count = sum(issue.severity == "warning" for issue in issues)
    report = ValidationReport(
        passed=error_count == 0,
        ray_count=len(grouped_points),
        point_count=len(points),
        segment_count=len(segments),
        detector_hits=detector_hits,
        detector_misses=detector_misses,
        terminated_rays=terminated,
        zero_length_transition_count=zero_length_count,
        max_direction_norm_error=max_norm_error,
        max_distance_continuity_error=max_distance_error,
        issue_count=len(issues),
        error_count=error_count,
        warning_count=warning_count,
    )
    return report, issues


def read_detector_hits(path: str | Path) -> list[dict[str, str]]:
    hit_path = Path(path).expanduser()
    with hit_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"ray_id", "pixel_x", "pixel_y", "inside_detector", "intensity"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"detector CSV missing fields: {', '.join(sorted(missing))}")
        return list(reader)


def build_detector_occupancy(
    hit_rows: Iterable[Mapping[str, object]],
    *,
    pixels_x: int,
    pixels_y: int,
) -> list[dict[str, float | int]]:
    if pixels_x <= 0 or pixels_y <= 0:
        raise ValueError("detector pixel counts must be positive")
    occupancy: dict[tuple[int, int], tuple[int, float]] = {}
    for row in hit_rows:
        inside = str(row["inside_detector"]).strip().lower() in {"1", "true", "yes"}
        if not inside:
            continue
        pixel_x = int(row["pixel_x"])
        pixel_y = int(row["pixel_y"])
        if not 0 <= pixel_x < pixels_x or not 0 <= pixel_y < pixels_y:
            raise ValueError(f"detector pixel outside configured bounds: ({pixel_x}, {pixel_y})")
        count, intensity = occupancy.get((pixel_x, pixel_y), (0, 0.0))
        occupancy[(pixel_x, pixel_y)] = (count + 1, intensity + float(row["intensity"]))
    return [
        {
            "pixel_x": x,
            "pixel_y": y,
            "hit_count": occupancy.get((x, y), (0, 0.0))[0],
            "total_intensity": occupancy.get((x, y), (0, 0.0))[1],
        }
        for y in range(pixels_y)
        for x in range(pixels_x)
    ]


def write_validation_outputs(
    report: ValidationReport,
    issues: Sequence[ValidationIssue],
    occupancy: Sequence[Mapping[str, object]],
    output_dir: str | Path,
) -> dict[str, Path]:
    directory = Path(output_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary": directory / "validation_summary.json",
        "issues": directory / "validation_issues.csv",
        "occupancy": directory / "detector_occupancy.csv",
    }
    with paths["summary"].open("w", encoding="utf-8") as handle:
        json.dump(asdict(report), handle, indent=2, sort_keys=True)
        handle.write("\n")
    with paths["issues"].open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ValidationIssue.__dataclass_fields__))
        writer.writeheader()
        writer.writerows(asdict(issue) for issue in issues)
    with paths["occupancy"].open("w", newline="", encoding="utf-8") as handle:
        fieldnames = ["pixel_x", "pixel_y", "hit_count", "total_intensity"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(occupancy)
    return {name: path.resolve() for name, path in paths.items()}
