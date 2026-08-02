"""Core ray-model primitives for the RBYRCT Houdini prototype."""

from .ray_engine import (
    DetectorHit,
    Layer,
    Ray,
    RayEvent,
    RayTraceResult,
    Vec3,
    emit_rectangular_beam,
    trace_ray,
    trace_rays,
)

__all__ = [
    "DetectorHit",
    "Layer",
    "Ray",
    "RayEvent",
    "RayTraceResult",
    "Vec3",
    "emit_rectangular_beam",
    "trace_ray",
    "trace_rays",
]
