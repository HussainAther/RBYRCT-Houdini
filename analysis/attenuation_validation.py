#!/usr/bin/env python3
"""Closed-form validation reports for Phase 2A attenuation scenarios."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

from physics.attenuation import AttenuationRayResult


@dataclass(frozen=True)
class AttenuationValidationRow:
    ray_id: int
    expected_path_length: float
    simulated_path_length: float
    path_length_abs_error: float
    expected_intensity: float
    simulated_intensity: float
    intensity_abs_error: float
    passed: bool


@dataclass(frozen=True)
class AttenuationValidationSummary:
    scenario: str
    ray_count: int
    passed_count: int
    failed_count: int
    max_path_length_abs_error: float
    max_intensity_abs_error: float
    tolerance: float
    passed: bool


def validate_results(
    scenario: str,
    results: Sequence[AttenuationRayResult],
    expected_path_length: Callable[[AttenuationRayResult], float],
    expected_intensity: Callable[[AttenuationRayResult], float],
    *,
    tolerance: float = 1.0e-10,
) -> tuple[AttenuationValidationSummary, list[AttenuationValidationRow]]:
    rows: list[AttenuationValidationRow] = []
    for result in results:
        expected_l = expected_path_length(result)
        expected_i = expected_intensity(result)
        path_error = abs(result.total_path_length - expected_l)
        intensity_error = abs(result.final_intensity - expected_i)
        rows.append(
            AttenuationValidationRow(
                ray_id=result.ray.ray_id,
                expected_path_length=expected_l,
                simulated_path_length=result.total_path_length,
                path_length_abs_error=path_error,
                expected_intensity=expected_i,
                simulated_intensity=result.final_intensity,
                intensity_abs_error=intensity_error,
                passed=path_error <= tolerance and intensity_error <= tolerance,
            )
        )
    failed = sum(not row.passed for row in rows)
    summary = AttenuationValidationSummary(
        scenario=scenario,
        ray_count=len(rows),
        passed_count=len(rows) - failed,
        failed_count=failed,
        max_path_length_abs_error=max((row.path_length_abs_error for row in rows), default=0.0),
        max_intensity_abs_error=max((row.intensity_abs_error for row in rows), default=0.0),
        tolerance=tolerance,
        passed=failed == 0,
    )
    return summary, rows


def write_validation_report(
    summary: AttenuationValidationSummary,
    rows: Sequence[AttenuationValidationRow],
    output_dir: str | Path,
) -> dict[str, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "analytic_validation_summary.json"
    csv_path = directory / "analytic_validation_rows.csv"
    md_path = directory / "analytic_validation_report.md"
    json_path.write_text(json.dumps(asdict(summary), indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(AttenuationValidationRow.__dataclass_fields__))
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    status = "PASS" if summary.passed else "FAIL"
    md_path.write_text(
        "\n".join([
            f"# Analytic Attenuation Validation — {summary.scenario}",
            "",
            f"**Status:** {status}",
            f"**Rays:** {summary.ray_count}",
            f"**Passed:** {summary.passed_count}",
            f"**Failed:** {summary.failed_count}",
            f"**Maximum path-length error:** {summary.max_path_length_abs_error:.6e}",
            f"**Maximum intensity error:** {summary.max_intensity_abs_error:.6e}",
            f"**Tolerance:** {summary.tolerance:.6e}",
            "",
            "The expected values are computed independently from the scenario's closed-form geometry and Beer–Lambert model.",
        ]) + "\n",
        encoding="utf-8",
    )
    return {"summary": json_path.resolve(), "rows": csv_path.resolve(), "report": md_path.resolve()}
