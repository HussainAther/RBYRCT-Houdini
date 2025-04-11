# File: scripts/janus_array_gen.py

"""
Janus Sphere Layer Generator
Generates a **curved/concentric layout** of Janus spheres in 11 layers for Ray-by-Ray CT.
Each layer is a circular arc (or full ring) of Janus spheres simulating beam steering.
"""

import numpy as np
import csv

# Parameters
num_layers = 11               # Number of layers (stacked in Z)
spheres_per_layer = 24       # Spheres arranged in a circle per layer
sphere_radius = 1.0          # Radius of each Janus sphere
layer_spacing = 2.5          # Z-distance between layers
circle_radius = 20.0         # Radius of each ring in X/Y

# Output file
output_file = "janus_layers_concentric.csv"

rows = []

for i in range(num_layers):
    z = i * layer_spacing
    angle_step = 2 * np.pi / spheres_per_layer
    layer_angle = i * 4       # in degrees, for metadata

    for j in range(spheres_per_layer):
        theta = j * angle_step
        x = circle_radius * np.cos(theta)
        y = circle_radius * np.sin(theta)
        rows.append([x, y, z, layer_angle])

# Save to CSV
with open(output_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["x", "y", "z", "layer_angle_deg"])
    writer.writerows(rows)

print(f"Concentric Janus layer array written to {output_file}")

