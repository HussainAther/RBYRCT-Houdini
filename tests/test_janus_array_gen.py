import csv
import math
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.janus_array_gen import FIELDNAMES, generate_array, write_csv


def test_default_array_count_and_ids():
    rows = generate_array()
    assert len(rows) == 264
    assert rows[0].sphere_id == 0
    assert rows[-1].sphere_id == 263


def test_first_layer_geometry():
    rows = generate_array(num_layers=1, spheres_per_layer=4, ring_radius=2.0)
    positions = [(round(r.x, 8), round(r.y, 8)) for r in rows]
    assert positions == [(2.0, 0.0), (0.0, 2.0), (-2.0, 0.0), (-0.0, -2.0)]


def test_layer_metadata():
    rows = generate_array(num_layers=3, spheres_per_layer=2, layer_spacing=1.5)
    assert rows[4].layer_index == 2
    assert rows[4].z == pytest.approx(3.0)
    assert rows[4].steering_angle_deg == pytest.approx(8.0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"num_layers": 0},
        {"spheres_per_layer": 0},
        {"sphere_radius": 0},
        {"layer_spacing": -1},
        {"ring_radius": -1},
    ],
)
def test_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        generate_array(**kwargs)


def test_csv_round_trip(tmp_path):
    output = write_csv(generate_array(num_layers=1, spheres_per_layer=3), tmp_path / "a.csv")
    with output.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        records = list(reader)
    assert reader.fieldnames == FIELDNAMES
    assert len(records) == 3
    assert records[1]["ring_index"] == "1"


def test_cli(tmp_path):
    output = tmp_path / "generated.csv"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/janus_array_gen.py",
            "--layers",
            "2",
            "--spheres-per-layer",
            "5",
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert output.exists()
    assert "10 Janus-sphere records" in result.stdout
