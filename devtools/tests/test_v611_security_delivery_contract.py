from pathlib import Path


def test_v611_security_documentation_contract():
    root = Path(__file__).resolve().parents[2]
    doc = (root / "docs/Security实现与测试.md").read_text(encoding="utf-8")
    for token in (
        "SRTCP", "32-bit NAS COUNT", "128-EEA2", "128-EIA2", "re-key", "AES-GCM",
        "NAS_SECURITY_PDU_MISSING", "NAS_PROTECTION_MODE_MISMATCH",
        "byte-aligned", "cross-process",
    ):
        assert token in doc
