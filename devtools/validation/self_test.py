from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]


class DomCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.tabs: list[str] = []
        self.panels: list[tuple[str | None, bool]] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        classes = set(attrs.get("class", "").split())
        if "workspace-tab" in classes:
            self.tabs.append(attrs.get("data-view", ""))
        if "view-panel" in classes:
            self.panels.append((attrs.get("data-view-panel"), "active" in classes))


def run(cmd: list[str], label: str, *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print(label)
    subprocess.run(cmd, cwd=cwd, check=True, env=env)
    print("PASS\n")


def parse_dom() -> DomCollector:
    parser = DomCollector()
    parser.feed((ROOT / "src" / "lte_sim" / "web" / "index.html").read_text(encoding="utf-8"))
    return parser


def check_html_ids() -> None:
    js = (ROOT / "src" / "lte_sim" / "web" / "app.js").read_text(encoding="utf-8")
    parser = parse_dom()
    if len(parser.ids) != len(set(parser.ids)):
        raise RuntimeError("Duplicate HTML ids detected")
    refs = set(re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", js))
    refs |= set(re.findall(r"\$\(['\"]#([^'\"]+)['\"]\)", js))
    missing = sorted(refs - set(parser.ids))
    if missing:
        raise RuntimeError(f"JavaScript references missing HTML ids: {missing}")
    print(f"HTML parse/id consistency PASS ({len(refs)} JS id references)\n")


def check_workspace() -> None:
    parser = parse_dom()
    expected = ["overview", "at", "tasks", "security", "debug"]
    if parser.tabs != expected:
        raise RuntimeError(f"Workspace tabs mismatch: {parser.tabs}")
    if [x[0] for x in parser.panels] != expected:
        raise RuntimeError(f"Workspace panels mismatch: {parser.panels}")
    if sum(1 for _, active in parser.panels if active) != 1:
        raise RuntimeError("Exactly one workspace panel must be active by default")
    print("5-view Web Workspace PASS\n")


def check_frontend_contract() -> None:
    if (ROOT / "src" / "lte_sim" / "desktop_app.py").exists():
        raise RuntimeError("Obsolete Native Desktop source must not be delivered")
    if (ROOT / "scripts" / "run-desktop.ps1").exists():
        raise RuntimeError("Obsolete run-desktop.ps1 must not be delivered")
    required = [
        ROOT / "scripts" / "windows" / "run-web.ps1",
        ROOT / "src" / "lte_sim" / "embedded_app.py",
        ROOT / "scripts" / "windows" / "build-exe.ps1",
        ROOT / "scripts" / "windows" / "security-demo.cmd",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"Missing Web/EXE frontend files: {missing}")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if "lte-sim-web" not in pyproject or "lte-sim-embedded" not in pyproject or "lte-sim-desktop" in pyproject:
        raise RuntimeError("Web/EXE entry-point contract mismatch")
    print("Web + Windows EXE frontend contract PASS\n")


def check_api_contract() -> None:
    js = (ROOT / "src" / "lte_sim" / "web" / "app.js").read_text(encoding="utf-8")
    api = (ROOT / "src" / "lte_sim" / "http_api.py").read_text(encoding="utf-8")
    frontend_paths = set(re.findall(r'["\'](/api/[A-Za-z0-9_/?=&.-]+)', js))
    missing = sorted(path for path in frontend_paths if path.split("?", 1)[0] not in api)
    if missing:
        raise RuntimeError(f"Frontend API paths missing from HTTP server: {missing}")
    for required in (
        "/api/attach/cancel",
        "/api/runs/location",
        "/api/runs/open-folder",
        "/api/security/self-test",
        "/api/security/udp",
        "/api/security/standalone-demo",
        "/api/diagnostics/blind",
    ):
        if required not in api:
            raise RuntimeError(f"Required HTTP route missing: {required}")
    print(f"Frontend/API route contract PASS ({len(frontend_paths)} frontend routes)\n")


def check_document_contract() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    docs_dir = ROOT / "docs"
    required_docs = [
        "README.md",
        "ARCHITECTURE.md",
        "ATTACH_AND_DIAGNOSIS.md",
        "SECURITY.md",
        "TECHNICAL_DESIGN.md",
        "WINDOWS_BUILD.md",
        "images/flowcharts/README.md",
    ]
    missing = [name for name in required_docs if not (docs_dir / name).is_file()]
    if missing:
        raise RuntimeError(f"Required public docs missing: {missing}")

    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    docs_index = (docs_dir / "README.md").read_text(encoding="utf-8")
    security_doc = (docs_dir / "SECURITY.md").read_text(encoding="utf-8")
    windows_doc = (docs_dir / "WINDOWS_BUILD.md").read_text(encoding="utf-8")

    if version not in root_readme:
        raise RuntimeError("Root README version does not match VERSION")
    if version not in security_doc or version not in windows_doc:
        raise RuntimeError("Versioned public technical docs do not match VERSION")

    for name in required_docs[1:6]:
        if name not in docs_index:
            raise RuntimeError(f"docs/README.md does not index {name}")

    for phrase in (
        "StandaloneSrtpModule",
        "SRTCP",
        "32-bit NAS COUNT",
        "128-EEA2",
        "128-EIA2",
        "re-key",
        "AES-GCM",
    ):
        if phrase not in security_doc:
            raise RuntimeError(f"SECURITY.md missing current implementation detail: {phrase}")

    build_script = (ROOT / "scripts" / "windows" / "build-exe.ps1").read_text(encoding="utf-8")
    for required_path in (
        "docs\\WINDOWS_BUILD.md",
        "README.md",
        "LICENSES\\README.md",
    ):
        if required_path not in build_script:
            raise RuntimeError(f"Windows build script missing public release dependency: {required_path}")
    for obsolete_path in (
        "docs\\Windows构建与运行.md",
        "docs\\第三方依赖与许可.md",
    ):
        if obsolete_path in build_script:
            raise RuntimeError(f"Windows build script still depends on private/internal file: {obsolete_path}")

    flowcharts = [
        "00-system-flow-overview.webp",
        "01-lte-attach-11-step-state-machine.webp",
        "02-mib-sib-validation-branches.webp",
        "03-authentication-res-xres-decision.webp",
        "04-control-plane-timer-timeout-path.webp",
        "05-fault-injection-runtime-consumption.webp",
        "06-modem-four-tasks-taskbus.webp",
        "07-system-architecture-three-entities.webp",
        "08-srtp-real-validation-path.webp",
        "09-failure-diagnosis-closed-loop.webp",
    ]
    missing_flows = [name for name in flowcharts if not (docs_dir / "images" / "flowcharts" / name).is_file()]
    if missing_flows:
        raise RuntimeError(f"Missing public flowcharts: {missing_flows}")

    print(f"Public documentation contract PASS ({len(required_docs)} indexed docs, {len(flowcharts)} flowcharts)\n")


def main() -> int:
    generated_bytecode: list[Path] = []
    run_token = uuid4().hex[:8]
    supplied_temp = os.environ.get("LTE_SIM_TEST_TEMP")
    supplied_pytest = os.environ.get("LTE_SIM_PYTEST_BASETEMP")
    temp_dir = Path(supplied_temp) if supplied_temp else ROOT.parent / f"lte-delivery-temp-{run_token}"
    pytest_dir = Path(supplied_pytest) if supplied_pytest else ROOT.parent / f"lte-delivery-pytest-{run_token}"
    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        pytest_dir.mkdir(parents=True, exist_ok=True)
        test_env = os.environ.copy()
        test_env["TEMP"] = str(temp_dir)
        test_env["TMP"] = str(temp_dir)
        test_env["PYTHONDONTWRITEBYTECODE"] = "1"
        test_env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        test_env["PYTHONPATH"] = str(ROOT / "src")
        run(
            [sys.executable, "-m", "compileall", "-q", "-b", str(ROOT / "src"), str(ROOT / "devtools" / "tests")],
            "[1/8] Python compileall",
            env=test_env,
        )
        generated_bytecode = list(ROOT.rglob("*.pyc"))

        print("[2/8] HTML structure/id consistency")
        check_html_ids()

        print("[3/8] Web Workspace structure")
        check_workspace()

        print("[4/8] Web + Windows EXE frontend contract")
        check_frontend_contract()

        print("[5/8] JavaScript syntax")
        node = shutil.which("node")
        if node:
            subprocess.run([node, "--check", str(ROOT / "src" / "lte_sim" / "web" / "app.js")], check=True)
            print("PASS\n")
        else:
            print("SKIP (Node.js not installed; runtime does not require Node.js)\n")

        print("[6/8] Frontend/API route contract")
        check_api_contract()

        print("[7/8] Public documentation/release contract")
        check_document_contract()

        run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--basetemp", str(pytest_dir)],
            "[8/8] Unit + Feature + E2E + UI test suite",
            env=test_env,
        )
        print("ALL CHECKS PASSED")
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"CHECK FAILED: {exc}", file=sys.stderr)
        return exc.returncode or 1
    except Exception as exc:
        print(f"CHECK FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        for path in generated_bytecode:
            path.unlink(missing_ok=True)
        if not supplied_temp:
            shutil.rmtree(temp_dir, ignore_errors=True)
        if not supplied_pytest:
            shutil.rmtree(pytest_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
