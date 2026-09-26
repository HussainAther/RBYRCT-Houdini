"""Procedural heterogeneous attenuation phantoms."""

from __future__ import annotations

from dataclasses import dataclass

from phantoms.analytic import Material, PhantomInterval
from physics.ray_engine import Vec3


@dataclass(frozen=True)
class EllipsoidRegion:
    region_id: str
    material: Material
    center: Vec3
    radii: Vec3
    priority: int = 0

    def __post_init__(self) -> None:
        if self.radii.x <= 0.0 or self.radii.y <= 0.0 or self.radii.z <= 0.0:
            raise ValueError("ellipsoid radii must be positive")

    def intervals(
        self,
        origin: Vec3,
        direction: Vec3,
    ) -> tuple[PhantomInterval, ...]:
        ox = (origin.x - self.center.x) / self.radii.x
        oy = (origin.y - self.center.y) / self.radii.y
        oz = (origin.z - self.center.z) / self.radii.z

        dx = direction.x / self.radii.x 
        dy = direction.y / self.radii.y
        dz = direction.z / self.radii.z

        a = dx * dx + dy * dy + dz * dz
        b = 2.0 * (ox * dx + oy * dy + oz * dz)
        c = ox * ox + oy * oy + oz * oz - 1.0

        discriminant = b * b - 4.0 * a * c

        if discriminant < 0.0:
            return ()
