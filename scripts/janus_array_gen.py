# File: scripts/janus_array_gen.py

"""
Janus Sphere Layer Generator
Generates a concentric ring layout of Janus spheres for Ray-by-Ray CT simulation.

Each layer consists of spheres positioned in a circle around the origin.
Layer deflection increases by 4 degrees per layer (Bragg reflection model).
Outputs to CSV for use in Houdini or other render/simulation pipelines.
"""

import numpy as np
import csv
import os

# Parameters
num_layers = 11               # Number of layers stacked vertically
spheres_per_layer = 24        # Spheres arranged per circular ring
sphere_radius = 1.0           # Radius of each sphere
layer_spacing = 2.5           # Distance between each layer (Z-axis)
circle_radius = 20.0          # Radius of each circular ring

# Output file
output_file = "janus_layers_concentric.csv"

rows = []

# Generate point positions and metadata for each layer
for i in range(num_layers):
    z = i * layer_spacing
    angle_step = 2 * np.pi / spheres_per_layer
    layer_angle = i * 4       # Total deflection angle in degrees

    for j in range(spheres_per_layer):
        theta = j * angle_step
        x = circle_radius * np.cos(theta)
        y = circle_radius * np.sin(theta)
        rows.append([x, y, z, layer_angle])

# Save to CSV
os.makedirs("data", exist_ok=True)
csv_path = os.path.join("data", output_file)

with open(csv_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["x", "y", "z", "layer_angle_deg"])
    writer.writerows(rows)

print(f"✅ Concentric Janus layer array written to: {csv_path}")

