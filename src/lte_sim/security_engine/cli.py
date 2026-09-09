from __future__ import annotations

import argparse
import json
from pathlib import Path

from .service import run_standalone_core_checks, verify_reference_vectors
from .standalone import StandaloneSrtpModule, run_standalone_demo


def _self_test() -> dict:
    key = bytes(range(30))
    result = run_standalone_demo(b"LTE-SIM standalone SRTP self-test", sequence=7, master_key_and_salt=key)
    vectors = verify_reference_vectors()
    core = run_standalone_core_checks()
    return {
        "ok": bool(result["ok"] and vectors.get("ok") and core.get("ok")),
        "standaloneModule": {
            "ok": result["ok"],
            "executionId": result["executionId"],
            "inputSha256": result["inputSha256"],
            "protectedSha256": result["protectedSha256"],
            "recoveredSha256": result["recoveredSha256"],
            "state": result["state"],
        },
        "referenceVectors": vectors,
        "coreChecks": {"ok": core.get("ok"), "passed": core.get("passed"), "total": core.get("total")},
    }


def _demo(payload: str, sequence: int) -> dict:
    # Interactive demo uses a fresh ephemeral 30-byte master key+salt on every
    # execution. Key material is never printed or persisted; only its SHA-256
    # fingerprint is exposed through public_state().
    return run_standalone_demo(payload, sequence=sequence)


def _write_optional_output(path: str | None, result: dict) -> None:
    if not path:
        return
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Standalone SRTP module demo. It does not start LTE Attach, Web UI or HTTP API."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    self_test = sub.add_parser("self-test", help="run standalone protocol/vector checks")
    self_test.add_argument("--output", help="optional JSON output path")
    demo = sub.add_parser("demo", help="protect and unprotect one raw RTP packet")
    demo.add_argument("--payload", default="standalone-sdk-demo", help="UTF-8 RTP payload")
    demo.add_argument("--sequence", type=int, default=321, help="RTP sequence number (0..65535)")
    demo.add_argument("--output", help="optional JSON output path")
    args = parser.parse_args(argv)
    result = _self_test() if args.command == "self-test" else _demo(args.payload, args.sequence)
    _write_optional_output(getattr(args, "output", None), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok", result.get("roundtrip", False)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
