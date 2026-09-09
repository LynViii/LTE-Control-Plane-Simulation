from __future__ import annotations
import copy, hashlib, json, platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4
from .run_repository import RunRepository
from .version import __version__
NOISE_FIELDS = {"time", "durationMs", "transactionId", "correlation_id", "requestId"}


def normalize_event(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: normalize_event(value[key]) for key in sorted(value) if key not in NOISE_FIELDS}
    if isinstance(value, list):
        return [normalize_event(item) for item in value]
    return value


def fingerprint_events(events: Iterable[dict]) -> str:
    lines = [json.dumps(normalize_event(event), ensure_ascii=False, sort_keys=True, separators=(",", ":")) for event in events]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _json_write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class InteractiveRunArchiver:
    """Archive a completed Web/headless Attach without running a second engine.

    Interactive runs already happened through the real TaskBus and TCP path, so
    the archiver snapshots their terminal state and transaction-scoped trace.
    Each record contains evidence from this actual Attach.
    """

    def __init__(self, output_root: Path, source: str = "INTERACTIVE"):
        self.output_root = Path(output_root).resolve()
        self.repository = RunRepository(self.output_root)
        self.source = source

    def __call__(self, state: dict) -> dict:
        flow = state.get("flow", {})
        transaction_id = str(flow.get("transactionId") or "").strip()
        if not transaction_id or flow.get("running"):
            raise ValueError("only a completed Attach transaction can be archived")

        scenario = copy.deepcopy(state.get("scenario", {}))
        scenario_id = str(scenario.get("id") or "UNKNOWN")
        finished_wall = datetime.now(timezone.utc)
        source_slug = {
            "WEB_INTERACTIVE": "web",
            "HEADLESS_INTERACTIVE": "headless",
        }.get(self.source, "interactive")
        run_id = f"{finished_wall:%Y%m%dT%H%M%SZ}-{source_slug}-{scenario_id.lower()}-{transaction_id[:8]}"
        self.output_root.mkdir(parents=True, exist_ok=True)
        run_dir = self.output_root / run_id
        if run_dir.exists():
            summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
            return {"runId": run_id, "runDir": str(run_dir), "summary": summary}

        events = [
            copy.deepcopy(event)
            for event in state.get("runtimeEvents", [])
            if event.get("transactionId") == transaction_id
        ]
        fingerprint = fingerprint_events(events)
        result = "SUCCESS" if state.get("modem", {}).get("attachStatus") == "ATTACHED" else "FAILURE"
        runtime_context = {
            "source": self.source,
            "scenario": scenario,
            "customFault": copy.deepcopy(state.get("customFault", {})) if scenario_id == "CUSTOM" else None,
            "speedMultiplier": state.get("runtime", {}).get("speedMultiplier", 1.0),
        }
        scenario_hash = hashlib.sha256(
            json.dumps(runtime_context, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        summary = {
            "source": self.source,
            "runType": "LTE",
            "scenarioId": scenario_id,
            "legacyScenario": scenario_id,
            "result": result,
            "finalState": state.get("modem", {}).get("attachStatus"),
            "failedStep": flow.get("failedStep"),
            "completedSteps": len(flow.get("completed", [])),
            "durationMs": flow.get("durationMs"),
            "fingerprint": fingerprint,
            "transactionId": transaction_id,
            "metrics": copy.deepcopy(state.get("metrics", {})),
            "expectationMatched": None,
        }
        manifest = {
            "formatVersion": "1.0",
            "runId": run_id,
            "simulatorVersion": __version__,
            "source": self.source,
            "scenarioId": scenario_id,
            "scenarioHash": scenario_hash,
            "clockMode": "realtime",
            "transport": "tcp-json-lines.v1",
            "startedAt": flow.get("startedAt"),
            "finishedAt": flow.get("finishedAt") or finished_wall.isoformat().replace("+00:00", "Z"),
            "result": result,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "artifacts": ["scenario-context.json", "manifest.json", "summary.json", "events.json", "faults.json", "diagnosis.json", "primitives.json", "logs.json", "fingerprint.txt"],
        }

        temp_dir = self.output_root / f".{run_id}.tmp-{uuid4().hex[:8]}"
        temp_dir.mkdir(parents=False, exist_ok=False)
        try:
            _json_write(temp_dir / "scenario-context.json", runtime_context)
            _json_write(temp_dir / "summary.json", summary)
            _json_write(temp_dir / "manifest.json", manifest)
            _json_write(temp_dir / "events.json", events)
            _json_write(temp_dir / "faults.json", state.get('faultEvidence',[]))
            _json_write(temp_dir / "diagnosis.json", state.get('diagnosis',{}))
            _json_write(temp_dir / "primitives.json", state.get('taskEvents',state.get('primitiveTrace',[])))
            _json_write(temp_dir / "logs.json", state.get('logs',[]))
            (temp_dir / "fingerprint.txt").write_text(fingerprint + "\n", encoding="ascii")
            temp_dir.rename(run_dir)
        except Exception:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
        return {"runId": run_id, "runDir": str(run_dir), "summary": summary}
