"""Houdini Python SOP: import ray_events.csv as attributed trajectory curves.

Python SOP parameters:
- ``events_file_path`` (string): path to Phase 1 ``ray_events.csv``
- ``skip_zero_length_segments`` (toggle, optional): omit layer enter/exit
  transitions that share a position. Defaults to enabled.

The script imports repository-independent CSV data directly so it can be pasted
into a Houdini Python SOP without adjusting ``sys.path``. One polyline is built
per ray. Point attributes preserve event state; primitive attributes summarize
the terminal state and ray ID.
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path

import hou

REQUIRED_FIELDS = {
    "ray_id", "event_index", "event_type", "layer_index",
    "x", "y", "z", "dir_x", "dir_y", "dir_z",
    "energy_kev", "intensity", "cumulative_distance",
    "cumulative_steering_deg",
}
STATE_CODES = {
    "emitted": 0,
    "layer_enter": 1,
    "layer_exit": 2,
    "detector_hit": 3,
    "detector_miss": 4,
    "terminated_low_intensity": 5,
    "terminated_no_layer_intersection": 6,
    "terminated_no_detector_intersection": 7,
}
STATE_COLORS = {
    "emitted": (0.2, 0.6, 1.0),
    "layer_enter": (1.0, 0.8, 0.1),
    "layer_exit": (1.0, 0.35, 0.05),
    "detector_hit": (0.15, 1.0, 0.25),
    "detector_miss": (1.0, 0.15, 0.15),
}

node = hou.pwd()
geo = node.geometry()
geo.clear()

path = Path(node.evalParm("events_file_path")).expanduser()
if not path.is_file():
    raise hou.NodeError(f"Ray event CSV does not exist: {path}")
try:
    skip_zero = bool(node.evalParm("skip_zero_length_segments"))
except hou.OperationFailed:
    skip_zero = True

with path.open(newline="", encoding="utf-8") as handle:
    reader = csv.DictReader(handle)
    missing = REQUIRED_FIELDS - set(reader.fieldnames or ())
    if missing:
        raise hou.NodeError(f"Ray event CSV missing fields: {', '.join(sorted(missing))}")
    rows = list(reader)
if not rows:
    raise hou.NodeError("Ray event CSV contains no rows")

point_specs = {
    "ray_id": (0,), "event_index": (0,), "event_type": "", "state_code": (0,),
    "layer_index": (-1,), "direction": (0.0, 0.0, 1.0), "energy_kev": (0.0,),
    "intensity": (0.0,), "cumulative_distance": (0.0,),
    "cumulative_steering_deg": (0.0,), "is_terminal": (0,),
    "Cd": (1.0, 1.0, 1.0),
}
for name, default in point_specs.items():
    geo.addAttrib(hou.attribType.Point, name, default)
geo.addAttrib(hou.attribType.Prim, "ray_id", 0)
geo.addAttrib(hou.attribType.Prim, "terminal_state", "")
geo.addAttrib(hou.attribType.Prim, "final_intensity", 0.0)

grouped = defaultdict(list)
for row in rows:
    grouped[int(row["ray_id"])].append(row)

for ray_id in sorted(grouped):
    ordered = sorted(grouped[ray_id], key=lambda row: int(row["event_index"]))
    filtered = []
    for row in ordered:
        position = (float(row["x"]), float(row["y"]), float(row["z"]))
        if skip_zero and filtered:
            previous = filtered[-1]
            previous_position = (
                float(previous["x"]), float(previous["y"]), float(previous["z"])
            )
            distance = math.dist(previous_position, position)
            if distance <= 1.0e-12 and previous["event_type"] == "layer_enter" and row["event_type"] == "layer_exit":
                filtered[-1] = row
                continue
        filtered.append(row)

    polygon = geo.createPolygon()
    polygon.setIsClosed(False)
    for row in filtered:
        event_type = row["event_type"]
        point = geo.createPoint()
        point.setPosition((float(row["x"]), float(row["y"]), float(row["z"])))
        point.setAttribValue("ray_id", int(row["ray_id"]))
        point.setAttribValue("event_index", int(row["event_index"]))
        point.setAttribValue("event_type", event_type)
        point.setAttribValue("state_code", STATE_CODES.get(event_type, 99))
        point.setAttribValue("layer_index", int(row["layer_index"]) if row["layer_index"] else -1)
        point.setAttribValue("direction", (
            float(row["dir_x"]), float(row["dir_y"]), float(row["dir_z"])
        ))
        point.setAttribValue("energy_kev", float(row["energy_kev"]))
        point.setAttribValue("intensity", float(row["intensity"]))
        point.setAttribValue("cumulative_distance", float(row["cumulative_distance"]))
        point.setAttribValue("cumulative_steering_deg", float(row["cumulative_steering_deg"]))
        terminal = int(event_type.startswith("terminated_") or event_type.startswith("detector_"))
        point.setAttribValue("is_terminal", terminal)
        point.setAttribValue("Cd", STATE_COLORS.get(event_type, (0.65, 0.65, 0.65)))
        polygon.addVertex(point)

    terminal = ordered[-1]
    polygon.setAttribValue("ray_id", ray_id)
    polygon.setAttribValue("terminal_state", terminal["event_type"])
    polygon.setAttribValue("final_intensity", float(terminal["intensity"]))
