from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from .fault_injection.core import FaultConfig

class ScenarioValidationError(ValueError):
    pass

@dataclass(frozen=True)
class ScenarioSpec:
    path: Path
    data: dict[str, Any]
    @property
    def id(self) -> str:
        return str(self.data["id"])
    @property
    def canonical_json(self) -> str:
        return json.dumps(self.data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json.encode("utf-8")).hexdigest()
    def clone(self) -> dict[str, Any]:
        return copy.deepcopy(self.data)

class ScenarioLoader:
    def __init__(self, schema_path: Path):
        self.schema_path = Path(schema_path)
        schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        self.validator = Draft202012Validator(schema)
    def load(self, path: Path) -> ScenarioSpec:
        path = Path(path)
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ScenarioValidationError(f"cannot load scenario {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ScenarioValidationError("scenario root must be an object")
        errors = sorted(self.validator.iter_errors(data), key=lambda item: list(item.path))
        if errors:
            detail = "; ".join(f"{'.'.join(map(str, err.path)) or '<root>'}: {err.message}" for err in errors)
            raise ScenarioValidationError(detail)
        FaultConfig.parse(data["fault"])
        return ScenarioSpec(path.resolve(), data)
    def load_directory(self, directory: Path) -> dict[str, ScenarioSpec]:
        specs = [self.load(path) for path in sorted(Path(directory).glob("*.yaml"))]
        if len({item.id for item in specs}) != len(specs):
            raise ScenarioValidationError("duplicate scenario id")
        return {item.id: item for item in specs}

def default_loader(project_root: Path) -> ScenarioLoader:
    return ScenarioLoader(Path(project_root) / "scenarios" / "schema" / "scenario.schema.json")
