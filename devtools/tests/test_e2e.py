from __future__ import annotations

import json
import os
import socket
import subprocess
import shutil
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def free_ports(count: int) -> tuple[int, ...]:
    """Reserve sockets together so the OS cannot return the same port twice."""
    sockets: list[socket.socket] = []
    try:
        for _ in range(count):
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            sockets.append(sock)
        return tuple(sock.getsockname()[1] for sock in sockets)
    finally:
        for sock in sockets:
            sock.close()


def request_json(url, method="GET", payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http_port, cls.ap_port, cls.enb_port = free_ports(3)
        env = os.environ.copy()
        env.update({
            "PORT": str(cls.http_port),
            "AP_MODEM_PORT": str(cls.ap_port),
            "ENB_PORT": str(cls.enb_port),
            "SIM_STEP_DELAY": "0.004",
            "SOCKET_TIMEOUT": "0.8",
        })
        env["PYTHONPATH"] = str(ROOT / "src")
        # Keep E2E runtime data outside the source tree.  A source checkout may
        # be read-only (or mounted by CI/artifact tooling), and HTTP reset must
        # not fail merely because ROOT/var is not writable.
        cls.runtime_temp = tempfile.TemporaryDirectory(prefix="lte-e2e-")
        cls.runtime_dir = Path(cls.runtime_temp.name)
        cls.state_file = cls.runtime_dir / "e2e-state.json"
        cls.runs_dir = cls.runtime_dir / "e2e-runs"
        env["LTE_SIM_STATE_FILE"] = str(cls.state_file)
        env["LTE_SIM_RUNS_DIR"] = str(cls.runs_dir)
        cls.proc = subprocess.Popen(
            [sys.executable, "-m", "lte_sim.web_app"], cwd=ROOT, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        cls.base = f"http://127.0.0.1:{cls.http_port}"
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                status, payload = request_json(cls.base + "/api/health")
                if status == 200 and payload.get("ok"):
                    return
            except Exception:
                pass
            time.sleep(0.05)
        raise RuntimeError("E2E server failed to start")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            cls.proc.kill()
            cls.proc.wait(timeout=2)
        cls.state_file.unlink(missing_ok=True)
        shutil.rmtree(cls.runs_dir, ignore_errors=True)
        cls.runtime_temp.cleanup()

    def setUp(self):
        request_json(self.base + "/api/reset", method="POST")
        request_json(self.base + "/api/scenario", method="POST", payload={"scenario": "NORMAL"})

    def wait_terminal(self, timeout=5):
        deadline = time.time() + timeout
        while time.time() < deadline:
            _, state = request_json(self.base + "/api/state")
            if state["flow"]["transactionId"] and not state["flow"]["running"]:
                return state
            time.sleep(0.02)
        self.fail("E2E attach timeout")

    def test_health(self):
        status, payload = request_json(self.base + "/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])

    def test_speed_api_updates_runtime(self):
        status, payload = request_json(self.base + "/api/speed", method="POST", payload={"multiplier": 2})
        self.assertEqual(status, 200)
        self.assertEqual(payload["state"]["runtime"]["speedMultiplier"], 2.0)
        request_json(self.base + "/api/speed", method="POST", payload={"multiplier": 1})

    def test_unknown_at_returns_http_400(self):
        status, payload = request_json(self.base + "/api/at-command", method="POST", payload={"command": "AT+BAD"})
        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])

    def test_normal_attach(self):
        status, payload = request_json(self.base + "/api/at-command", method="POST", payload={"command": "AT+CFUN=1"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["response"], "OK")
        state = self.wait_terminal()
        self.assertEqual(state["modem"]["attachStatus"], "ATTACHED")
        self.assertEqual(len(state["flow"]["completed"]), 11)
        self.assertEqual(state["runHistory"][-1]["result"], "SUCCESS")
        status, history = request_json(self.base + "/api/history")
        self.assertEqual(status, 200)
        self.assertTrue(history["history"])
        deadline = time.time() + 2
        archived = []
        while time.time() < deadline:
            status, run_listing = request_json(self.base + "/api/runs")
            archived = [run for run in run_listing["runs"] if run.get("transactionId") == state["flow"]["transactionId"]]
            if archived:
                break
            time.sleep(0.02)
        self.assertEqual(status, 200)
        self.assertEqual(len(archived), 1)
        self.assertEqual(archived[0]["source"], "WEB_INTERACTIVE")
        for artifact in ("scenario-context.json", "manifest.json", "summary.json", "events.json", "fingerprint.txt"):
            self.assertTrue((Path(archived[0]["runDir"]) / artifact).is_file())

    def test_fault_injection_cell_barred(self):
        status, _ = request_json(self.base + "/api/scenario", method="POST", payload={"scenario": "CELL_BARRED"})
        self.assertEqual(status, 200)
        request_json(self.base + "/api/at-command", method="POST", payload={"command": "AT+CFUN=1"})
        state = self.wait_terminal()
        self.assertEqual(state["modem"]["attachStatus"], "FAILED")
        self.assertEqual(state["flow"]["failedStep"], "system_info_validate")

    def test_security_self_test_api(self):
        status, payload = request_json(self.base + "/api/security/self-test", method="POST")
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["tamperRejected"])
        self.assertTrue(payload["replayRejected"])

    def test_security_protect_api_roundtrip(self):
        status, payload = request_json(self.base + "/api/security/protect", method="POST", payload={"plaintext": "VoLTE demo"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["recovered"], "VoLTE demo")
        self.assertEqual(payload["packet"]["cipher"], "AES-128-CM")
        self.assertEqual(len(payload["packet"]["tagHex"]), 20)

    def test_security_udp_api_and_pcap_export(self):
        status, payload = request_json(self.base + "/api/security/udp", method="POST",
                                       payload={"scenario": "TAMPER_CIPHERTEXT", "payload": "wire-test"})
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["transport"], "UDP/socket.sendto+recvfrom")
        self.assertEqual(payload["rejected"], 1)
        self.assertTrue(payload["packets"][0]["udp"]["wireBytesMatch"])
        url = self.base + "/api/security/pcap?run=" + urllib.parse.quote(payload["runId"])
        with urllib.request.urlopen(url, timeout=3) as response:
            data = response.read()
        self.assertEqual(data[:4], b"\xd4\xc3\xb2\xa1")


    def test_reset_mid_attach_prevents_stale_write(self):
        request_json(self.base + "/api/at-command", method="POST", payload={"command": "AT+CFUN=1"})
        request_json(self.base + "/api/reset", method="POST")
        time.sleep(0.2)
        _, state = request_json(self.base + "/api/state")
        self.assertEqual(state["modem"]["attachStatus"], "DETACHED")
        self.assertEqual(state["modem"]["cfun"], 0)

    def test_at_test_form_over_real_ap_modem_socket(self):
        status, payload = request_json(self.base + "/api/at-command", method="POST", payload={"command": "AT+CFUN=?"})
        self.assertEqual(status, 200)
        self.assertIn("(0,1)", payload["response"])

    def test_runtime_observability_after_attach(self):
        request_json(self.base + "/api/at-command", method="POST", payload={"command": "AT+CFUN=1"})
        state = self.wait_terminal()
        self.assertGreater(state["taskRuntime"]["RRC"]["processed"], 0)
        self.assertGreater(state["transportMetrics"]["apModem"]["commands"], 0)
        self.assertGreater(state["transportMetrics"]["modemEnb"]["tx"], 0)
        self.assertEqual(state["transportMetrics"]["modemEnb"]["tx"], state["transportMetrics"]["modemEnb"]["rx"])

    def test_security_reject_scenario_fails_at_security_step(self):
        request_json(self.base + "/api/scenario", method="POST", payload={"scenario": "SECURITY_REJECT"})
        request_json(self.base + "/api/at-command", method="POST", payload={"command": "AT+CFUN=1"})
        state = self.wait_terminal()
        self.assertEqual(state["flow"]["failedStep"], "security_mode")

    def test_malformed_system_info_scenario_fails_at_validation(self):
        request_json(self.base + "/api/scenario", method="POST", payload={"scenario": "SYSTEM_INFO_MALFORMED"})
        request_json(self.base + "/api/at-command", method="POST", payload={"command": "AT+CFUN=1"})
        state = self.wait_terminal()
        self.assertEqual(state["flow"]["failedStep"], "system_info_validate")


    def test_v35_extended_at_commands_over_real_socket(self):
        for command, expected in [
            ("AT+COPS?", "+COPS:"),
            ("AT+SEC?", "+SEC:"),
            ("AT+TASK?", "+TASK:"),
        ]:
            status, payload = request_json(self.base + "/api/at-command", method="POST", payload={"command": command})
            self.assertEqual(status, 200)
            self.assertIn(expected, payload["response"])

    def test_v35_observability_apis_after_attach(self):
        request_json(self.base + "/api/at-command", method="POST", payload={"command": "AT+CFUN=1"})
        self.wait_terminal()
        for path, key in [
            ("/api/trace", "trace"),
            ("/api/timers", "timers"),
            ("/api/packets", "packets"),
            ("/api/at-history", "history"),
        ]:
            status, payload = request_json(self.base + path)
            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload[key])

    def test_v35_failure_diagnosis_api(self):
        request_json(self.base + "/api/scenario", method="POST", payload={"scenario": "RRC_REJECT"})
        request_json(self.base + "/api/at-command", method="POST", payload={"command": "AT+CFUN=1"})
        self.wait_terminal()
        status, payload = request_json(self.base + "/api/diagnosis")
        self.assertEqual(status, 200)
        report = payload["diagnosis"]["lastReport"]
        self.assertEqual(report["root_cause"], "PRIMITIVE_PARAMETER_INVALID")
        self.assertEqual(report["actual"], "RRC_REJECT")
        self.assertTrue(report["evidence"])
        self.assertTrue(report["checks"])
        self.assertTrue(report["suggestions"])

    def test_v35_at_history_duration_is_monotonic_elapsed_not_timestamp(self):
        status, _ = request_json(self.base + "/api/at-command", method="POST", payload={"command": "AT+CSQ"})
        self.assertEqual(status, 200)
        status, payload = request_json(self.base + "/api/at-history")
        self.assertEqual(status, 200)
        row = payload["history"][-1]
        self.assertEqual(row["command"], "AT+CSQ")
        self.assertGreaterEqual(row["durationMs"], 0)
        self.assertLess(row["durationMs"], 3000)


if __name__ == "__main__":
    unittest.main()
