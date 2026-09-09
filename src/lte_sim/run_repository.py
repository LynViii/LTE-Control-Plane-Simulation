from __future__ import annotations

import difflib
import json
import shutil
from pathlib import Path
from typing import Any


_NOISE_FIELDS = {
    "time", "startedAt", "finishedAt", "durationMs", "rttMs", "transactionId",
    "requestId", "keyId", "lastIvHex", "lastTagHex", "ciphertextB64", "tagHex", "ivHex",
    "sentAt", "receivedAt", "sentEpoch", "receivedEpoch", "wireHex", "ciphertextHex",
    "authenticationTagHex",
}


def _normalize_event(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_event(value[key]) for key in sorted(value) if key not in _NOISE_FIELDS}
    if isinstance(value, list):
        return [_normalize_event(item) for item in value]
    return value


class RunRepository:
    """Single read/index/export layer for ordinary Attach and Security runs."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def ensure(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root

    def resolve(self, run_id: str) -> Path:
        normalized = str(run_id).strip().replace("\\", "/")
        if not normalized or normalized.startswith("/"):
            raise ValueError("invalid run id")
        candidate = (self.root / normalized).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("invalid run id") from exc
        if not candidate.is_dir() or not (candidate / "summary.json").is_file():
            raise ValueError(f"run not found: {run_id}")
        return candidate

    @staticmethod
    def _read_json(path: Path, *, default: Any = None) -> Any:
        if not path.is_file():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default

    def get_summary(self, run_id: str) -> dict:
        run_dir = self.resolve(run_id)
        summary = self._read_json(run_dir / "summary.json")
        if not isinstance(summary, dict):
            raise ValueError(f"invalid summary.json for run: {run_id}")
        return summary

    def get_trace(self, run_id: str) -> list[dict]:
        run_dir = self.resolve(run_id)
        for filename in ("events.json", "trace.json", "protocol-trace.json"):
            value = self._read_json(run_dir / filename)
            if isinstance(value, list):
                return value
        return []

    def get(self, run_id: str) -> dict:
        run_dir = self.resolve(run_id)
        summary = self.get_summary(run_id)
        manifest = self._read_json(run_dir / "manifest.json", default={})
        if not isinstance(manifest, dict):
            manifest = {}
        return {
            "runId": run_dir.relative_to(self.root).as_posix(),
            "runDir": str(run_dir),
            "summary": summary,
            "manifest": manifest,
            "events": self.get_trace(run_id),
        }

    def list(self) -> list[dict]:
        records: list[dict] = []
        if not self.root.exists():
            return records
        for summary_path in self.root.rglob("summary.json"):
            try:
                relative = summary_path.relative_to(self.root)
                if any(part.startswith(".") for part in relative.parts):
                    continue
                summary = self._read_json(summary_path)
                if not isinstance(summary, dict):
                    continue
                run_dir = summary_path.parent
                run_id = run_dir.relative_to(self.root).as_posix()
                manifest = self._read_json(run_dir / "manifest.json", default={})
                if not isinstance(manifest, dict):
                    manifest = {}
                record = dict(summary)
                record.update({
                    "runId": run_id,
                    "runDir": str(run_dir),
                    "formatVersion": manifest.get("formatVersion", "legacy"),
                    "simulatorVersion": manifest.get("simulatorVersion", summary.get("simulatorVersion", "legacy/unknown")),
                    "hasTrace": any((run_dir / name).is_file() for name in ("events.json", "trace.json", "protocol-trace.json")),
                    "hasPcap": (run_dir / "traffic.pcap").is_file(),
                    "modifiedEpoch": summary_path.stat().st_mtime,
                })
                records.append(record)
            except (OSError, ValueError):
                continue
        return sorted(records, key=lambda item: (item.get("modifiedEpoch", 0), item["runId"]), reverse=True)

    def export_zip(self, run_id: str, destination: Path) -> Path:
        run_dir = self.resolve(run_id)
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        created = shutil.make_archive(str(destination.with_suffix("")), "zip", root_dir=run_dir)
        return Path(created)
