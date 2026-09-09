from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from lte_sim.at import ATParser
from lte_sim.models import FLOW_STEPS
from lte_sim.control_plane.engine import EngineHooks, SimulatorEngine, build_enb_response
from lte_sim.state import StateStore, default_state
from lte_sim.runtime.taskbus import TaskBus


class ATParserTests(unittest.TestCase):
    def setUp(self):
        self.state = default_state()

    def test_at_ping(self):
        result = ATParser.parse("AT", self.state)
        self.assertTrue(result.ok)
        self.assertEqual(result.response, "OK")

    def test_cfun_query(self):
        self.state["modem"]["cfun"] = 1
        self.assertIn("+CFUN: 1", ATParser.parse("at+cfun?", self.state).response)

    def test_attach_query(self):
        self.state["modem"]["attachStatus"] = "ATTACHED"
        self.assertIn("+CGATT: 1", ATParser.parse("AT+CGATT?", self.state).response)

    def test_unknown_at_is_error(self):
        result = ATParser.parse("AT+NOPE", self.state)
        self.assertFalse(result.ok)
        self.assertEqual(result.action, "unsupported")

    def test_cfun_test_form_reports_supported_values(self):
        result = ATParser.parse("AT+CFUN=?", self.state)
        self.assertTrue(result.ok)
        self.assertIn("(0,1)", result.response)

    def test_invalid_cfun_value_is_rejected(self):
        result = ATParser.parse("AT+CFUN=7", self.state)
        self.assertFalse(result.ok)
        self.assertEqual(result.response, "ERROR: INVALID_CFUN_VALUE")

    def test_missing_at_prefix_is_rejected(self):
        result = ATParser.parse("+CFUN?", self.state)
        self.assertFalse(result.ok)
        self.assertEqual(result.response, "ERROR: MISSING_AT_PREFIX")

    def test_overlong_command_is_rejected(self):
        result = ATParser.parse("AT+" + "X" * 300, self.state)
        self.assertFalse(result.ok)
        self.assertEqual(result.response, "ERROR: COMMAND_TOO_LONG")

    def test_help_lists_project_command_subset(self):
        result = ATParser.parse("AT+HELP", self.state)
        self.assertTrue(result.ok)
        self.assertIn("CFUN", result.response)
        self.assertIn("CGATT", result.response)


class ENBResponseTests(unittest.TestCase):
    def response(self, request, base, *args, **kwargs):
        from lte_sim.fault_injection.core import PRESETS, CATALOG, FaultInjector
        cfg=PRESETS.get(request.get('scenario','NORMAL'),PRESETS['NORMAL'])
        evidence=[]
        injector=FaultInjector(cfg,evidence.append)
        if cfg['layer']=='socket':
            request,_,_,_=injector.intercept(dict(request,auth_result='SUCCESS'),layer='socket',stage=cfg['stage'],
                primitive=request['type'],correlation_id='unit-corr',transaction_id='unit-tx')
        response=build_enb_response(request,base,*args,**kwargs)
        if cfg['layer']=='primitive':
            original=response
            response,_,_,_=injector.intercept(response,layer='primitive',stage=cfg['stage'],primitive=CATALOG[cfg['stage']][0],
                correlation_id='unit-corr',transaction_id='unit-tx')
            if cfg['enabled']:
                assert evidence[0]['original_parameters']==original
                assert evidence[0]['after_parameters']==response
                assert evidence[0]['correlation_id']=='unit-corr'
        return response

    def setUp(self):
        self.enb = default_state()["enb"]

    def test_normal_system_info(self):
        response = self.response({"type": "READ_MIB_SIB", "scenario": "NORMAL"}, self.enb, 0.01)
        self.assertEqual(response["kind"], "SYSTEM_INFORMATION")
        self.assertFalse(response["sib"]["cellBarred"])

    def test_cell_barred_injection(self):
        response = self.response({"type": "READ_MIB_SIB", "scenario": "CELL_BARRED"}, self.enb, 0.01)
        self.assertTrue(response["sib"]["cellBarred"])

    def test_plmn_mismatch_injection_does_not_mutate_base(self):
        response = self.response({"type": "READ_MIB_SIB", "scenario": "PLMN_MISMATCH"}, self.enb, 0.01)
        self.assertNotEqual(response["sib"]["plmn"], self.enb["plmn"])
        self.assertEqual(self.enb["sib"]["plmn"], "460-01")

    def test_ra_reject(self):
        response = self.response({"type": "RA_PREAMBLE", "scenario": "RA_REJECT"}, self.enb, 0.01)
        self.assertFalse(response["accepted"])

    def test_rrc_reject(self):
        response = self.response({"type": "RRC_CONNECTION_REQUEST", "scenario": "RRC_REJECT"}, self.enb, 0.01)
        self.assertEqual(response["kind"], "RRC_REJECT")

    def test_auth_reject(self):
        response = self.response({"type": "NAS_AUTHENTICATION_RESPONSE", "scenario": "AUTH_REJECT"}, self.enb, 0.01)
        self.assertEqual(response["kind"], "NAS_AUTHENTICATION_REJECT")

    def test_request_id_is_echoed(self):
        response = self.response({"type": "READ_MIB_SIB", "scenario": "NORMAL", "requestId": "abc123"}, self.enb, 0.01)
        self.assertEqual(response["requestId"], "abc123")

    def test_malformed_system_information_omits_sib(self):
        response = self.response({"type": "READ_MIB_SIB", "scenario": "SYSTEM_INFO_MALFORMED"}, self.enb, 0.01)
        self.assertEqual(response["kind"], "SYSTEM_INFORMATION")
        self.assertIsNone(response["sib"])

    def test_security_reject(self):
        response = self.response({"type": "NAS_SECURITY_MODE_COMPLETE", "scenario": "SECURITY_REJECT"}, self.enb, 0.01)
        self.assertEqual(response["kind"], "SECURITY_REJECT")
        self.assertEqual(response["kind"], "SECURITY_REJECT")


class StateStoreRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = StateStore(Path(self.temp.name) / "state.json", max_logs=100)

    def tearDown(self):
        self.temp.cleanup()

    def test_speed_multiplier_accepts_supported_values(self):
        self.store.set_speed(2.0)
        self.assertEqual(self.store.snapshot()["runtime"]["speedMultiplier"], 2.0)

    def test_speed_multiplier_rejects_unsupported_value(self):
        with self.assertRaises(ValueError):
            self.store.set_speed(3.0)

    def test_task_runtime_event_is_recorded(self):
        self.store.record_task_event({"task": "RRC", "phase": "PROCESSING", "queueDepth": 2, "primitive": "TEST_REQ", "correlationId": "corr1", "queueWaitMs": 4})
        self.store.record_task_event({"task": "RRC", "phase": "COMPLETED", "queueDepth": 1, "primitive": "TEST_REQ", "correlationId": "corr1", "processingMs": 7})
        task = self.store.snapshot()["taskRuntime"]["RRC"]
        self.assertEqual(task["status"], "READY")
        self.assertEqual(task["processed"], 1)
        self.assertEqual(task["lastPrimitive"], "TEST_REQ")
        self.assertEqual(task["lastProcessingMs"], 7)

    def test_transport_metrics_are_recorded(self):
        self.store.record_transport_event("apModem", "COMMAND", command="AT")
        self.store.record_transport_event("modemEnb", "TX", request_id="req1", message_type="READ_MIB_SIB")
        self.store.record_transport_event("modemEnb", "RX", request_id="req1", message_type="READ_MIB_SIB", rtt_ms=12)
        snap = self.store.snapshot()["transportMetrics"]
        self.assertEqual(snap["apModem"]["commands"], 1)
        self.assertEqual(snap["modemEnb"]["tx"], 1)
        self.assertEqual(snap["modemEnb"]["rx"], 1)
        self.assertEqual(snap["modemEnb"]["lastRttMs"], 12)

    def test_primitive_trace_records_task_interaction_phases(self):
        self.store.record_task_event({"task": "L2", "phase": "ENQUEUED", "queueDepth": 1, "primitive": "MAC_RA_REQ", "correlationId": "corr-ra"})
        self.store.record_task_event({"task": "L2", "phase": "COMPLETED", "queueDepth": 0, "primitive": "MAC_RA_REQ", "correlationId": "corr-ra", "queueWaitMs": 2, "processingMs": 5})
        trace = self.store.snapshot()["primitiveTrace"]
        self.assertEqual([item["phase"] for item in trace], ["ENQUEUED", "COMPLETED"])
        self.assertEqual(trace[-1]["task"], "L2")
        self.assertEqual(trace[-1]["primitive"], "MAC_RA_REQ")
        self.assertEqual(trace[-1]["correlationId"], "corr-ra")
        self.assertEqual(trace[-1]["processingMs"], 5)

    def test_primitive_trace_is_bounded(self):
        for index in range(125):
            self.store.record_task_event({"task": "NAS", "phase": "ENQUEUED", "queueDepth": 0, "primitive": f"P{index}", "correlationId": f"c{index}"})
        trace = self.store.snapshot()["primitiveTrace"]
        self.assertEqual(len(trace), 120)
        self.assertEqual(trace[0]["primitive"], "P5")
        self.assertEqual(trace[-1]["primitive"], "P124")


class TaskBusTests(unittest.TestCase):
    def test_request_reply(self):
        bus = TaskBus()
        bus.register("ECHO", lambda primitive, payload: {"primitive": primitive, **payload})
        bus.start()
        try:
            result = bus.request("ECHO", "PING", {"value": 7}, timeout=1)
            self.assertEqual(result, {"primitive": "PING", "value": 7})
        finally:
            bus.stop()

    def test_observer_receives_correlation_and_completion(self):
        events = []
        bus = TaskBus(observer=events.append)
        bus.register("ECHO", lambda primitive, payload: payload)
        bus.start()
        try:
            self.assertEqual(bus.request("ECHO", "PING", {"value": 3}, timeout=1)["value"], 3)
        finally:
            bus.stop()
        phases = [event["phase"] for event in events]
        self.assertIn("ENQUEUED", phases)
        self.assertIn("PROCESSING", phases)
        self.assertIn("COMPLETED", phases)
        completed = next(event for event in events if event["phase"] == "COMPLETED")
        self.assertTrue(completed["correlationId"])


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = StateStore(Path(self.temp.name) / "state.json", max_logs=300)

        def fake_network(request):
            return build_enb_response(request, self.store.snapshot()["enb"], 0.01)

        self.engine = SimulatorEngine(self.store, EngineHooks(fake_network), step_delay=0.002)

    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()

    def wait_terminal(self, timeout=2):
        deadline = time.time() + timeout
        while time.time() < deadline:
            snap = self.store.snapshot()
            if not snap["flow"]["running"] and snap["flow"]["transactionId"]:
                return snap
            time.sleep(0.005)
        self.fail("Attach did not reach terminal state")

    def test_normal_attach_completes_all_steps(self):
        started, _ = self.engine.start_attach()
        self.assertTrue(started)
        snap = self.wait_terminal()
        self.assertEqual(snap["modem"]["attachStatus"], "ATTACHED")
        self.assertEqual(snap["flow"]["completed"], [step["key"] for step in FLOW_STEPS])
        self.assertEqual(snap["metrics"]["attachSuccesses"], 1)
        self.assertEqual(len(snap["flow"]["stepTimingMs"]), len(FLOW_STEPS))
        self.assertEqual(snap["runHistory"][-1]["result"], "SUCCESS")
        self.assertEqual(snap["runHistory"][-1]["transactionId"], snap["flow"]["transactionId"])

    def test_plmn_mismatch_fails_at_validation(self):
        self.store.set_scenario("PLMN_MISMATCH")
        self.engine.start_attach()
        snap = self.wait_terminal()
        self.assertEqual(snap["modem"]["attachStatus"], "FAILED")
        self.assertEqual(snap["flow"]["failedStep"], "system_info_validate")
        self.assertIn("PLMN_MISMATCH", snap["modem"]["lastError"])

    def test_ra_reject_fails_at_random_access(self):
        self.store.set_scenario("RA_REJECT")
        self.engine.start_attach()
        snap = self.wait_terminal()
        self.assertEqual(snap["flow"]["failedStep"], "random_access")

    def test_reset_cancels_old_transaction_without_stale_attached_state(self):
        self.engine.step_delay = 0.04
        self.engine.start_attach()
        time.sleep(0.02)
        self.engine.reset()
        time.sleep(0.22)
        snap = self.store.snapshot()
        self.assertEqual(snap["modem"]["cfun"], 0)
        self.assertEqual(snap["modem"]["attachStatus"], "DETACHED")
        self.assertIsNone(snap["modem"]["cell"])
        self.assertFalse(snap["flow"]["running"])

    def test_cfun_zero_clears_security_state(self):
        self.engine.security.establish("temp")
        self.store.mutate(lambda state: state.__setitem__("security", self.engine.security.public_state()))
        self.assertTrue(self.store.snapshot()["security"]["active"])
        self.engine.set_cfun_zero()
        self.assertFalse(self.store.snapshot()["security"]["active"])

    def test_second_attach_while_running_returns_busy(self):
        self.engine.step_delay = 0.03
        started, _ = self.engine.start_attach()
        self.assertTrue(started)
        started2, reason = self.engine.start_attach()
        self.assertFalse(started2)
        self.assertIn("already running", reason)
        self.engine.reset()

    def test_malformed_system_info_fails_at_validation(self):
        self.store.set_scenario("SYSTEM_INFO_MALFORMED")
        self.engine.start_attach()
        snap = self.wait_terminal()
        self.assertEqual(snap["flow"]["failedStep"], "system_info_validate")
        self.assertIn("SIB_MISSING", snap["modem"]["lastError"])

    def test_security_reject_fails_at_security_mode(self):
        self.store.set_scenario("SECURITY_REJECT")
        self.engine.start_attach()
        snap = self.wait_terminal()
        self.assertEqual(snap["flow"]["failedStep"], "security_mode")
        self.assertEqual(snap["diagnosis"]["lastReport"]["actual"], "SECURITY_REJECT")
        self.assertTrue(snap["diagnosis"]["lastReport"]["evidence"])

    def test_task_and_transport_observability_updates_on_attach(self):
        self.engine.start_attach()
        snap = self.wait_terminal()
        self.assertGreater(snap["taskRuntime"]["NAS"]["processed"], 0)
        self.assertGreater(snap["taskRuntime"]["L1"]["processed"], 0)
        self.assertGreater(snap["transportMetrics"]["modemEnb"]["tx"], 0)
        self.assertEqual(snap["transportMetrics"]["modemEnb"]["tx"], snap["transportMetrics"]["modemEnb"]["rx"])
        self.assertTrue(snap["transportMetrics"]["modemEnb"]["lastRequestId"])


if __name__ == "__main__":
    unittest.main()

class SecurityContextTests(unittest.TestCase):
    def test_aes_hmac_roundtrip_and_public_state(self):
        from lte_sim.security_engine.service import SecurityContext
        sec = SecurityContext()
        info = sec.establish("unit-test-label")
        self.assertTrue(info["active"])
        self.assertEqual(info["srtpCipher"], "AES-128-CM")
        self.assertEqual(info["srtpAuth"], "HMAC-SHA1-80")
        packet = sec.protect("hello-volte", ssrc=1234, sequence=9)
        self.assertEqual(sec.unprotect(packet), "hello-volte")
        self.assertEqual(len(packet["tagHex"]), 20)
        self.assertEqual(packet["implementation"], "Security Core / SRTP Engine")
        self.assertEqual(sec.public_state()["packetCount"], 1)

    def test_hmac_tamper_is_rejected(self):
        from lte_sim.security_engine.service import SecurityContext
        sec = SecurityContext(); sec.establish("tamper-test")
        packet = sec.protect("sensitive")
        packet["tagHex"] = "00" * 10
        with self.assertRaises(ValueError):
            sec.unprotect(packet)

    def test_security_self_test_passes(self):
        from lte_sim.security_engine.service import SecurityContext
        sec = SecurityContext()
        result = sec.self_test()
        self.assertTrue(result["ok"])
        self.assertTrue(result["tamperRejected"])
        self.assertTrue(result["replayRejected"])
