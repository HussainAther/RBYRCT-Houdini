# File: scripts/import_csv_to_points.py

"""
CSV Import Script for Houdini Python SOP
Reads janus_layers_concentric.csv and creates points in Houdini geometry
Each point includes position (x, y, z) and a layer_angle_deg attribute.
"""

import csv
import hou

# === Parameters ===
csv_path = hou.evalParm("csv_file_path")  # You can add this as a parameter in your Python SOP

# === Main Execution ===
geo = hou.pwd().geometry()

try:
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pt = geo.createPoint()
            pt.setPosition((
                float(row["x"]),
                float(row["y"]),
                float(row["z"])
            ))
            pt.setAttribValue("layer_angle_deg", float(row["layer_angle_deg"]))
    print(f"✅ Imported {csv_path} into Houdini geometry.")
except Exception as e:
    print(f"❌ Failed to import CSV: {e}")

