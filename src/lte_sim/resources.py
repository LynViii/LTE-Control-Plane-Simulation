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
    return resource_root() / "scenarios"


def scenario_schema_path() -> Path:
    return scenarios_root() / "schema" / "scenario.schema.json"
