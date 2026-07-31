"""Houdini Python SOP: import Janus-sphere CSV records as points.

Create a string parameter named ``csv_file_path`` on the Python SOP and paste
or import this script into the node.
"""

from __future__ import annotations

import csv
from pathlib import Path

import hou


FLOAT_ATTRIBUTES = (
    "sphere_radius",
    "ring_radius",
    "azimuth_deg",
    "steering_angle_deg",
)
INT_ATTRIBUTES = ("sphere_id", "layer_index", "ring_index")
REQUIRED_COLUMNS = {"x", "y", "z", *FLOAT_ATTRIBUTES, *INT_ATTRIBUTES}


def ensure_point_attributes(geo: "hou.Geometry") -> None:
    for name in FLOAT_ATTRIBUTES:
        if geo.findPointAttrib(name) is None:
            geo.addAttrib(hou.attribType.Point, name, 0.0)
    for name in INT_ATTRIBUTES:
        if geo.findPointAttrib(name) is None:
            geo.addAttrib(hou.attribType.Point, name, 0)


def import_csv(geo: "hou.Geometry", csv_path: str) -> int:
    path = Path(csv_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"CSV file does not exist: {path}")

    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or ())
        missing = sorted(REQUIRED_COLUMNS - columns)
        if missing:
            raise ValueError("CSV is missing required columns: " + ", ".join(missing))

        ensure_point_attributes(geo)
        imported = 0
        for line_number, row in enumerate(reader, start=2):
            try:
                point = geo.createPoint()
                point.setPosition((float(row["x"]), float(row["y"]), float(row["z"])))
                for name in FLOAT_ATTRIBUTES:
                    point.setAttribValue(name, float(row[name]))
                for name in INT_ATTRIBUTES:
                    point.setAttribValue(name, int(row[name]))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid value on CSV line {line_number}: {exc}") from exc
            imported += 1
    return imported


def main() -> None:
    node = hou.pwd()
    geo = node.geometry()
    geo.clear()
    csv_path = hou.evalParm("csv_file_path")

    try:
        count = import_csv(geo, csv_path)
    except Exception as exc:
        message = f"Failed to import Janus CSV: {exc}"
        node.addError(message)
        raise hou.NodeError(message) from exc

    print(f"Imported {count} Janus-sphere points from {csv_path}")


main()
