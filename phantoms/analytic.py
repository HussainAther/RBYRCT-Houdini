#!/usr/bin/env python3
"""Closed-form attenuation phantoms.

All intersections are returned as forward ray-parameter intervals. Direction
vectors are assumed to be normalized, so interval lengths are physical lengths
in repository world units.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from physics.ray_engine import Vec3

_EPS = 1.0e-12


@dataclass(frozen=True)
class Material:
    material_id: str
    mu: float

    def __post_init__(self) -> None:
        if not self.material_id:
            raise ValueError("material_id cannot be empty")
        if self.mu < 0.0 or not math.isfinite(self.mu):
            raise ValueError("mu must be finite and non-negative")


@dataclass(frozen=True)
class PhantomInterval:
    phantom_id: str
    material: Material
    t_enter: float
    t_exit: float

    def __post_init__(self) -> None:
        if self.t_enter < -_EPS or self.t_exit < self.t_enter - _EPS:
            raise ValueError("invalid forward interval")

    @property
    def path_length(self) -> float:
        return max(0.0, self.t_exit - self.t_enter)


class AnalyticPhantom(Protocol):
    phantom_id: str

    def intervals(self, origin: Vec3, direction: Vec3) -> tuple[PhantomInterval, ...]: ...


@dataclass(frozen=True)
class SlabPhantom:
    phantom_id: str
    material: Material
    z_min: float
    z_max: float

    def __post_init__(self) -> None:
        if self.z_max <= self.z_min:
            raise ValueError("z_max must exceed z_min")

    def intervals(self, origin: Vec3, direction: Vec3) -> tuple[PhantomInterval, ...]:
        d = direction.normalized()
        if abs(d.z) <= _EPS:
            return ()
        t0 = (self.z_min - origin.z) / d.z
        t1 = (self.z_max - origin.z) / d.z
        enter, exit_ = sorted((t0, t1))
        enter = max(enter, 0.0)
        if exit_ <= enter + _EPS:
            return ()
        return (PhantomInterval(self.phantom_id, self.material, enter, exit_),)


@dataclass(frozen=True)
class SpherePhantom:
    phantom_id: str
    material: Material
    center: Vec3
    radius: float

    def __post_init__(self) -> None:
        if self.radius <= 0.0 or not math.isfinite(self.radius):
            raise ValueError("radius must be finite and positive")

    def intervals(self, origin: Vec3, direction: Vec3) -> tuple[PhantomInterval, ...]:
        d = direction.normalized()
        oc = origin - self.center
        b = 2.0 * oc.dot(d)
        c = oc.dot(oc) - self.radius * self.radius
        discriminant = b * b - 4.0 * c
        if discriminant < -_EPS:
            return ()
        root = math.sqrt(max(0.0, discriminant))
        t0 = (-b - root) / 2.0
        t1 = (-b + root) / 2.0
        enter = max(min(t0, t1), 0.0)
        exit_ = max(t0, t1)
        if exit_ <= enter + _EPS:
            return ()
        return (PhantomInterval(self.phantom_id, self.material, enter, exit_),)


@dataclass(frozen=True)
class NestedSpherePhantom:
    """Concentric or off-center inner sphere replacing outer material."""

    phantom_id: str
    outer_material: Material
    inner_material: Material
    center: Vec3
    outer_radius: float
    inner_radius: float
    inner_center: Vec3 | None = None

    def __post_init__(self) -> None:
        if self.outer_radius <= 0.0 or self.inner_radius <= 0.0:
            raise ValueError("radii must be positive")
        inner_center = self.inner_center or self.center
        offset = (inner_center - self.center).magnitude
        if offset + self.inner_radius > self.outer_radius + _EPS:
            raise ValueError("inner sphere must be fully contained by outer sphere")

    def intervals(self, origin: Vec3, direction: Vec3) -> tuple[PhantomInterval, ...]:
        outer = SpherePhantom(
            self.phantom_id + ":outer", self.outer_material, self.center, self.outer_radius
        ).intervals(origin, direction)
        if not outer:
            return ()
        inner = SpherePhantom(
            self.phantom_id + ":inner",
            self.inner_material,
            self.inner_center or self.center,
            self.inner_radius,
        ).intervals(origin, direction)
        if not inner:
            interval = outer[0]
            return (PhantomInterval(self.phantom_id, self.outer_material, interval.t_enter, interval.t_exit),)

        o = outer[0]
        i = inner[0]
        inner_enter = max(i.t_enter, o.t_enter)
        inner_exit = min(i.t_exit, o.t_exit)
        if inner_exit <= inner_enter + _EPS:
            return (PhantomInterval(self.phantom_id, self.outer_material, o.t_enter, o.t_exit),)

        pieces: list[PhantomInterval] = []
        if inner_enter > o.t_enter + _EPS:
            pieces.append(PhantomInterval(self.phantom_id, self.outer_material, o.t_enter, inner_enter))
        pieces.append(PhantomInterval(self.phantom_id, self.inner_material, inner_enter, inner_exit))
        if o.t_exit > inner_exit + _EPS:
            pieces.append(PhantomInterval(self.phantom_id, self.outer_material, inner_exit, o.t_exit))
        return tuple(pieces)
