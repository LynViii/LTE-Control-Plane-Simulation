"""Source-tree validation that does not depend on delivery-only documents.

This profile is intended for a fresh Git clone/CI checkout.  The stricter
``self_test.py`` remains the delivery-package acceptance test and may validate
``docs/`` and release-facing contracts in addition to runtime code.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_TESTS = [
    "devtools/tests/test_core.py",
    "devtools/tests/test_e2e.py",
    "devtools/tests/test_lan_mode.py",
    "devtools/tests/test_security_core.py",
    "devtools/tests/test_srtp_udp.py",
    "devtools/tests/test_v50_boundaries.py",
    "devtools/tests/test_v50_faults.py",
    "devtools/tests/test_v50_transport.py",
    "devtools/tests/test_v604_hardening.py",
    "devtools/tests/test_v610_security_upgrade.py",
    "devtools/tests/test_v611_security_hardening.py",
    "devtools/tests/test_v612_review_hardening.py",
    "devtools/tests/test_windows_firewall.py",
]


def run(cmd: list[str], label: str, *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print(label)
    subprocess.run(cmd, cwd=cwd, check=True, env=env)
    print("PASS\n")


def wheel_resource_check(temp: Path, env: dict[str, str]) -> None:
    wheel_dir = temp / "wheel"
    wheel_dir.mkdir()
    run([
        sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "--no-build-isolation", "-w", str(wheel_dir)
    ], "[4/5] Build wheel", env=env)
    wheels = list(wheel_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected one wheel, found {wheels}")
    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    required = {
        "lte_sim/scenarios/normal-attach.yaml",
        "lte_sim/scenarios/schema/scenario.schema.json",
        "lte_sim/web/index.html",
    }
    missing = sorted(required - names)
    if missing:
        raise RuntimeError(f"wheel missing package resources: {missing}")

    target = temp / "site"
    run([sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(target), str(wheel)],
        "[5/5] Install wheel in isolated target", env=env)
    outside = temp / "outside"
    outside.mkdir()
    code = (
        f"import sys; sys.path.insert(0, {str(target)!r}); "
        "from lte_sim.resources import scenarios_root, scenario_schema_path; "
        "from lte_sim.scenario import default_loader; "
        "root=scenarios_root(); schema=scenario_schema_path(); "
        "assert root.is_dir() and schema.is_file(); "
        "specs=default_loader().load_directory(root); "
        "assert 'NORMAL' in specs and len(specs)>=1; "
        "print(root); print(len(specs))"
    )
    isolated_env = env.copy()
    isolated_env.pop("PYTHONPATH", None)
    subprocess.run([sys.executable, "-I", "-c", code], cwd=outside, check=True, env=isolated_env)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="lte-source-self-test-") as td:
        temp = Path(td)
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        env["PYTHONPATH"] = str(ROOT / "src")
        try:
            run([sys.executable, "-m", "compileall", "-q", str(ROOT / "src"), str(ROOT / "devtools" / "tests")],
                "[1/5] Python compileall", env=env)
            node = shutil.which("node")
            if node:
                run([node, "--check", str(ROOT / "src" / "lte_sim" / "web" / "app.js")],
                    "[2/5] JavaScript syntax", env=env)
            else:
                print("[2/5] JavaScript syntax\nSKIP (Node.js not installed)\n")
            run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *SOURCE_TESTS],
                "[3/5] Source runtime test profile", env=env)
            wheel_resource_check(temp, env)
            print("SOURCE CHECKS PASSED")
            return 0
        except (subprocess.CalledProcessError, RuntimeError) as exc:
            print(f"SOURCE CHECK FAILED: {exc}", file=sys.stderr)
            return getattr(exc, "returncode", 1) or 1
        finally:
            shutil.rmtree(ROOT / "build", ignore_errors=True)
            for path in (ROOT / "src").glob("*.egg-info"):
                shutil.rmtree(path, ignore_errors=True)
            for pyc in ROOT.rglob("*.pyc"):
                pyc.unlink(missing_ok=True)
            for cache in ROOT.rglob("__pycache__"):
                shutil.rmtree(cache, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
