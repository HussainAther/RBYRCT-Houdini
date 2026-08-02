#!/usr/bin/env python3
"""Repository-root CLI wrapper for :mod:`physics.ray_engine`."""

from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from physics.ray_engine import main


if __name__ == "__main__":
    raise SystemExit(main())
