"""Run the standalone SRTP SDK demo without LTE Attach/Web/HTTP."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lte_sim.security_engine.standalone import run_standalone_demo


def main() -> int:
    result = run_standalone_demo("Standalone SRTP demo packet", sequence=321)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
