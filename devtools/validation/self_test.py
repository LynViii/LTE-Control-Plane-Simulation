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
    for required in ("/api/attach/cancel", "/api/runs/location", "/api/runs/open-folder", "/api/security/self-test", "/api/security/udp", "/api/security/standalone-demo", "/api/diagnostics/blind"):
        if required not in api:
            raise RuntimeError(f"Required HTTP route missing: {required}")
    print(f"Frontend/API route contract PASS ({len(frontend_paths)} frontend routes)\n")


def check_document_contract() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    docs_dir = ROOT / "docs"
    required_docs = [
        "README.md", "README-说明书.md", "LTE控制面系统仿真平台技术文档.md", "LTE控制面系统仿真平台结题报告.md",
        "项目架构与源码结构.md", "状态机与故障诊断.md", "Security实现与测试.md", "LAN模式使用与排查.md",
        "Windows构建与运行.md", "学习内容.md", "需求验收与交付.md", "版本记录.md", "第三方依赖与许可.md",
        "reference/Security独立Demo.md", "reference/完整更新记录.md", "reference/流程图提示词.md",
    ]
    missing = [name for name in required_docs if not (docs_dir / name).is_file()]
    if missing:
        raise RuntimeError(f"Required current docs missing: {missing}")
    if (docs_dir / "README-给带教老师.md").exists():
        raise RuntimeError("Obsolete README-给带教老师.md must not be delivered")

    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    manual = (docs_dir / "README-说明书.md").read_text(encoding="utf-8")
    if version not in root_readme or version not in manual:
        raise RuntimeError("Current README/manual version does not match VERSION")

    current_text = "\n".join((docs_dir / name).read_text(encoding="utf-8") for name in required_docs if name not in {"reference/完整更新记录.md", "版本记录.md"})
    obsolete_claims = [
        "Windows 下默认最大化",
        "Windows 默认最大化",
        "运行控制改为三个等宽按钮同排",
        "运行控制收敛为 `开始 Attach / 关闭无线 / 重置状态`",
        "正常链路 3 包",
        "Experiment 页面可以直接启动 LTE / SRTP",
    ]
    found = [claim for claim in obsolete_claims if claim in root_readme or claim in current_text]
    if found:
        raise RuntimeError(f"Obsolete current-document claims detected: {found}")

    for phrase in ("开始 Attach", "中断当前流程", "关闭无线", "系统重置"):
        if phrase not in manual:
            raise RuntimeError(f"README-说明书 missing current runtime control: {phrase}")
    security_doc = (docs_dir / "Security实现与测试.md").read_text(encoding="utf-8")
    for phrase in ("run_standalone_core_checks", "Security Core 本身不依赖 Web、HTTP、UDP、Attach", "cryptography/OpenSSL", "StandaloneSrtpModule", "security-demo.cmd", "不再为了这一功能额外构建第三个 Security Demo EXE", "SRTCP", "32-bit NAS COUNT", "128-EEA2", "128-EIA2", "re-key", "AES-GCM"):
        if phrase not in security_doc:
            raise RuntimeError(f"Security documentation missing current implementation detail: {phrase}")

    flowcharts = [
        "00-system-flow-overview.png", "01-lte-attach-11-step-state-machine.png",
        "02-mib-sib-validation-branches.png", "03-authentication-res-xres-decision.png",
        "04-control-plane-timer-timeout-path.png", "05-fault-injection-runtime-consumption.png",
        "06-modem-four-tasks-taskbus.png", "07-system-architecture-three-entities.png",
        "08-srtp-real-validation-path.png", "09-failure-diagnosis-closed-loop.png",
    ]
    missing_flows = [name for name in flowcharts if not (docs_dir / "images" / "flowcharts" / name).is_file()]
    if missing_flows:
        raise RuntimeError(f"Missing v6 flowcharts: {missing_flows}")

    index = (docs_dir / "README.md").read_text(encoding="utf-8")
    for name in required_docs[1:]:
        if name not in index and Path(name).name not in index:
            raise RuntimeError(f"docs/README.md does not index {name}")
    print(f"Current documentation contract PASS ({len(required_docs)} active docs)\n")

def main() -> int:
    generated_bytecode: list[Path] = []
    run_token = uuid4().hex[:8]
    supplied_temp = os.environ.get("LTE_SIM_TEST_TEMP")
    supplied_pytest = os.environ.get("LTE_SIM_PYTEST_BASETEMP")
    temp_dir = Path(supplied_temp) if supplied_temp else ROOT.parent / f"lte-v44-temp-{run_token}"
    pytest_dir = Path(supplied_pytest) if supplied_pytest else ROOT.parent / f"lte-v44-pytest-{run_token}"
    try:
        # Use an explicit writable sibling because Windows user-temp and some
        # synced project subdirectories can have stale ACLs.
        temp_dir.mkdir(parents=True, exist_ok=True)
        pytest_dir.mkdir(parents=True, exist_ok=True)
        test_env = os.environ.copy()
        test_env["TEMP"] = str(temp_dir)
        test_env["TMP"] = str(temp_dir)
        test_env["PYTHONDONTWRITEBYTECODE"] = "1"
        # Keep delivery validation deterministic even when the host Python has
        # unrelated third-party pytest plugins installed.
        test_env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        test_env["PYTHONPATH"] = str(ROOT / "src")
        run([sys.executable, "-m", "compileall", "-q", "-b", str(ROOT / "src"), str(ROOT / "devtools" / "tests")], "[1/8] Python compileall", env=test_env)
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

        print("[7/8] Current documentation contract")
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
