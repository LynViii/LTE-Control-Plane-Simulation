from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v603_version_contract():
    assert read("VERSION").strip() == "6.0.3"
    assert 'version = "6.0.3"' in read("pyproject.toml")
    assert '__version__ = "6.0.3"' in read("src/lte_sim/version.py")


def test_v603_next_step_full_text_is_not_ellipsized():
    js = read("src/lte_sim/web/app.js")
    css = read("src/lte_sim/web/ui.css")
    assert 'class="diagnosis-advice"' in js
    assert '.diagnosis-followup .diagnosis-advice span' in css
    assert 'white-space:normal !important' in css
    assert 'text-overflow:clip !important' in css
    assert 'overflow:visible !important' in css


def test_v603_security_demo_is_backend_first_without_third_exe():
    html = read("src/lte_sim/web/index.html")
    js = read("src/lte_sim/web/app.js")
    build = read("scripts/windows/build-exe.ps1")
    cmd = read("scripts/windows/security-demo.cmd")
    assert "运行后端独立 Demo" in html and "/api/security/standalone-demo" in js
    assert "不会额外弹出 PowerShell/CMD" in html
    assert "LTE-SRTP-Security-Demo.exe" not in build
    assert not (ROOT / "packaging/security_demo_entry.py").exists()
    assert 'start "" notepad.exe' in cmd


def test_v603_socket_rx_replay_uses_response_message_kind():
    engine = read("src/lte_sim/control_plane/engine.py")
    js = read("src/lte_sim/web/app.js")
    assert "wireMessageKind=response.get('kind')" in engine
    assert "row.outputMessage?.kind || row.wireMessageKind" in js


def test_v603_docs_are_grouped_and_generated_manifest_is_valid_when_packaged():
    index = read("docs/README.md")
    assert "当前交付文档" in index and "历史与参考材料" in index
    assert (ROOT / "docs/reference/Security独立Demo.md").is_file()
    assert (ROOT / "docs/reference/流程图提示词.md").is_file()
    assert (ROOT / "docs/reference/完整更新记录.md").is_file()
    assert not (ROOT / "docs/Security独立Demo.md").exists()
    assert not (ROOT / "docs/流程图提示词.md").exists()
    assert not (ROOT / "docs/完整更新记录.md").exists()

    # package-source.py deliberately keeps generated manifests out of the
    # working tree, then injects one into the final source ZIP.  Therefore a
    # fresh extraction may legitimately contain the manifest; if present it
    # must describe the shipped source snapshot and must not inventory itself.
    manifest_path = ROOT / "packaging/SOURCE-MANIFEST.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "packaging/SOURCE-MANIFEST.json" not in manifest
        for rel in ("VERSION", "README.md", "src/lte_sim/version.py"):
            item = manifest[rel]
            data = (ROOT / rel).read_bytes()
            assert item["bytes"] == len(data)
            assert item["sha256"] == hashlib.sha256(data).hexdigest()
