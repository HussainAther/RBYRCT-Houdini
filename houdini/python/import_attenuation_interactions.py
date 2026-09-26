"""Houdini Python SOP: visualize Phase 2A phantom interactions.

Create a string parameter named ``interactions_file_path`` and point it at
``phantom_interactions.csv``. Each interaction becomes an open two-point
polyline from phantom entry to exit. Point/primitive attributes expose material,
path length, attenuation coefficient, optical depth, and intensity change.
"""

from __future__ import annotations

import csv
from pathlib import Path

import hou

REQUIRED = {
    "ray_id", "interaction_index", "phantom_id", "material_id",
    "entry_x", "entry_y", "entry_z", "exit_x", "exit_y", "exit_z",
    "path_length", "mu", "optical_depth", "intensity_before", "intensity_after",
}

node = hou.pwd()
geo = node.geometry()
geo.clear()
path = Path(node.evalParm("interactions_file_path")).expanduser()
if not path.is_file():
    raise hou.NodeError(f"Interaction CSV does not exist: {path}")
with path.open(newline="", encoding="utf-8") as handle:
    reader = csv.DictReader(handle)
    missing = REQUIRED - set(reader.fieldnames or ())
    if missing:
        raise hou.NodeError(f"Interaction CSV missing fields: {', '.join(sorted(missing))}")
    rows = list(reader)

for name, default in {
    "ray_id": 0, "interaction_index": 0, "phantom_id": "", "material_id": "",
    "path_length": 0.0, "mu": 0.0, "optical_depth": 0.0,
    "intensity_before": 0.0, "intensity_after": 0.0, "transmission": 0.0,
}.items():
    geo.addAttrib(hou.attribType.Point, name, default)
    geo.addAttrib(hou.attribType.Prim, name, default)
geo.addAttrib(hou.attribType.Point, "Cd", (1.0, 1.0, 1.0))

for row in rows:
    values = {
        "ray_id": int(row["ray_id"]),
        "interaction_index": int(row["interaction_index"]),
        "phantom_id": row["phantom_id"],
        "material_id": row["material_id"],
        "path_length": float(row["path_length"]),
        "mu": float(row["mu"]),
        "optical_depth": float(row["optical_depth"]),
        "intensity_before": float(row["intensity_before"]),
        "intensity_after": float(row["intensity_after"]),
        "transmission": float(row["intensity_after"]) / float(row["intensity_before"]),
    }
    primitive = geo.createPolygon()
    primitive.setIsClosed(False)
    for position in (
        (float(row["entry_x"]), float(row["entry_y"]), float(row["entry_z"])),
        (float(row["exit_x"]), float(row["exit_y"]), float(row["exit_z"])),
    ):
        point = geo.createPoint()
        point.setPosition(position)
        for name, value in values.items():
            point.setAttribValue(name, value)
        point.setAttribValue("Cd", (1.0 - values["transmission"], values["transmission"], 0.1))
        primitive.addVertex(point)
    for name, value in values.items():
        primitive.setAttribValue(name, value)
