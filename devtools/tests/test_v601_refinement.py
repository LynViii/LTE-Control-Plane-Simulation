from __future__ import annotations

from pathlib import Path

from lte_sim.diagnostics.engine import FailureDiagnosisEngine
from lte_sim.security_engine.standalone import run_standalone_demo

ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v601_version_and_release_docs():
    assert read("VERSION").strip() == "6.0.3"
    assert 'version = "6.0.3"' in read("pyproject.toml")
    assert '__version__ = "6.0.3"' in read("src/lte_sim/version.py")
    assert "## v6.0.3" in read("docs/版本记录.md")


def test_standalone_demo_is_real_raw_bytes_backend_boundary():
    result = run_standalone_demo("v601 standalone proof", sequence=321, master_key_and_salt=bytes(range(30)))
    assert result["ok"] is True and result["roundtrip"] is True
    assert result["inputSha256"] == result["recoveredSha256"]
    assert result["inputSha256"] != result["protectedSha256"]
    assert result["webStateRead"] is False
    assert result["lteAttachStateRead"] is False
    assert result["faultConfigRead"] is False
    assert result["state"]["protectCount"] == 1
    assert result["state"]["unprotectCount"] == 1


def test_standalone_demo_entrypoints_and_ui_proof_are_delivered():
    assert (ROOT / "scripts/windows/security-demo.cmd").is_file()
    assert (ROOT / "scripts/security_standalone_demo.py").is_file()
    assert (ROOT / "docs/reference/Security独立Demo.md").is_file()
    html = read("src/lte_sim/web/index.html")
    js = read("src/lte_sim/web/app.js")
    api = read("src/lte_sim/http_api.py")
    assert 'id="securityStandaloneDemoButton"' in html
    assert 'id="securityStandaloneResult"' in html
    assert "/api/security/standalone-demo" in js and "/api/security/standalone-demo" in api
    assert "Execution ID" in js and "后端落盘证据" in js


def test_blind_diagnosis_produces_digest_and_excludes_fault_event():
    tx = "tx-v601-blind"
    trace = [
        {"time": "2026-09-09T07:00:00Z", "transactionId": tx, "event": "FAULT_INJECTED", "field": "res", "before": "OK", "after": "BAD"},
        {"time": "2026-09-09T07:00:01Z", "transactionId": tx, "event": "SOCKET_PEER_RX", "primitive": "NAS_AUTHENTICATION_RESPONSE", "eventId": "peer-1", "payloadSha256": "A" * 64},
        {"time": "2026-09-09T07:00:02Z", "transactionId": tx, "event": "NETWORK_AUTH_DECISION", "primitive": "NAS_AUTHENTICATION_RESPONSE", "decision": "REJECT", "rejectCause": "RES_MISMATCH", "failedField": "res", "expectedValue": "SIMULATED_RES", "actualValue": "INVALID_RES", "checks": [{"name": "RES / XRES", "field": "res", "expected": "SIMULATED_RES", "actual": "INVALID_RES", "passed": False}], "inputMessage": {"type": "NAS_AUTHENTICATION_RESPONSE", "res": "INVALID_RES"}, "outputMessage": {"kind": "NAS_AUTHENTICATION_REJECT"}},
    ]
    report = FailureDiagnosisEngine().analyze(step="authentication", message="reject", transaction_id=tx, recent_trace=trace, scenario=None, blind=True)
    meta = report["diagnosisInput"]
    assert report["diagnosticVerdict"] == "RES_MISMATCH"
    assert meta["rawEventCount"] == 3 and meta["eventCount"] == 2
    assert meta["excludedFaultEventCount"] == 1
    assert len(meta["evidenceDigest"]) == 64
    assert all(row.get("event") != "FAULT_INJECTED" for row in report["evidence"])


def test_v601_diagnosis_ui_is_compact_chinese_and_fault_editor_hides_irrelevant_fields():
    html = read("src/lte_sim/web/index.html")
    js = read("src/lte_sim/web/app.js")
    css = read("src/lte_sim/web/ui.css")
    assert "证据隔离复算" in html and "证据隔离复算" in js
    assert "运行链路回放" in js and "Socket Hash 匹配" in js
    assert "Modem发送" in js and "eNB/MME接收" in js
    assert "诊断输入" not in html or "RUNTIME_EVIDENCE_ONLY" not in html
    assert "runtime-replay ol" in css and "repeat(2, minmax(0,1fr))" in css
    assert 'id="faultModifyWorkspace"' in html and 'id="faultTimingWorkspace"' in html
    assert "faultModifyWorkspace.hidden = !modify" in js
    assert ".fault-modify-workspace[hidden]" in css


def test_default_scenario_menu_is_reduced_to_five_phase_level_entries():
    api = read("src/lte_sim/http_api.py")
    block = api.split("quick_scenarios = [", 1)[1].split("]", 1)[0]
    assert block.count("(\"") == 5
    assert "RRC_CAUSE_UNSUPPORTED" not in block
    assert "SECURITY_ALGORITHM_MISMATCH" not in block
    assert "历史 scenario ID" not in block  # UI menu stays separate from backend compatibility.


def test_course_report_has_academic_structure_not_weekly_log_or_shortcomings_section():
    report = read("docs/LTE控制面系统仿真平台结题报告.md")
    for phrase in ("摘要", "关键词", "需求分析", "总体设计", "核心模块设计与实现", "测试与验收", "结论", "参考文献"):
        assert phrase in report
    for phrase in ("第一周", "第二周", "第三周", "存在的不足"):
        assert phrase not in report
    assert len(report) > 12000
