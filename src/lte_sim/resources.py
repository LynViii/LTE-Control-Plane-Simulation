from __future__ import annotations

import sys
from pathlib import Path


def resource_root() -> Path:
    """Resolve immutable application resources in source and PyInstaller builds."""
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled).resolve()
    return Path(__file__).resolve().parents[2]


def package_root() -> Path:
    root = resource_root()
    bundled_package = root / "lte_sim"
    return bundled_package if bundled_package.is_dir() else Path(__file__).resolve().parent


def web_root() -> Path:
    return package_root() / "web"


def scenarios_root() -> Path:
    """Return scenario resources in source, wheel, or PyInstaller layouts.

    v6.0.4 ships a package-local copy so an installed wheel can load scenarios
    from outside the project directory. PyInstaller keeps its historical
    top-level ``scenarios/`` data layout, which remains preferred in _MEIPASS.
    """
    root = resource_root()
    if getattr(sys, "_MEIPASS", None):
        bundled = root / "scenarios"
        if bundled.is_dir():
            return bundled
    packaged = package_root() / "scenarios"
    if packaged.is_dir():
        return packaged
    return root / "scenarios"


def scenario_schema_path() -> Path:
    return scenarios_root() / "schema" / "scenario.schema.json"
