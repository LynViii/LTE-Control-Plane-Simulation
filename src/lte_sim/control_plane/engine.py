from __future__ import annotations

import copy
import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable
from uuid import uuid4

from ..models import AttachContext, SCENARIOS
from ..fault_injection.core import FaultInjector, CATALOG, PRESETS
from ..state import StateStore, utc_now
from ..runtime.taskbus import TaskBus
from ..security_engine.service import SecurityContext
from ..diagnostics.engine import FailureDiagnosisEngine
from ..runtime.timers import TimerManager
from ..runtime.clock import RealtimeClock, SimulationClock
from .specs import timer_spec_for_stage, flow_step_for_stage
from .network_context import NetworkControlPlaneContext


class AttachCancelled(RuntimeError):
    pass


class ProtocolFailure(RuntimeError):
    def __init__(self, message: str, step: str | None = None, *, root_cause: str | None = None,
                 primitive: str | None = None, field: str | None = None, expected=None, actual=None):
        super().__init__(message)
        self.step = step
        self.root_cause = root_cause
        self.primitive = primitive
        self.field = field
        self.expected = expected
        self.actual = actual


@dataclass
class EngineHooks:
    network_request: Callable[[dict], dict]
    run_finished: Callable[[dict], dict | None] | None = None


class SimulatorEngine:
    """LTE control-plane teaching simulator.

    The implementation intentionally models control flow, task interaction and
    failure handling rather than real PHY/MAC timing or ASN.1 messages.
    """

    def __init__(self, store: StateStore, hooks: EngineHooks, step_delay: float = 0.22, clock: SimulationClock | None = None):
        self.store = store
        self.hooks = hooks
        self.step_delay = step_delay
        self._ctx_lock = threading.RLock()
        self._current_ctx: AttachContext | None = None
        self._attach_thread: threading.Thread | None = None
        self.security = SecurityContext()
        self.store.mutate(lambda state: state.__setitem__("security", self.security.public_state()))
        self.diagnosis = FailureDiagnosisEngine()
        self.clock = clock or RealtimeClock()
        self.timers = TimerManager(self.store, clock=self.clock)
        self.bus = TaskBus(observer=self.store.record_task_event, queue_size=64)
        self.bus.register("NAS", self._nas_handler)
        self.bus.register("RRC", self._rrc_handler)
        self.bus.register("L2", self._l2_handler)
        self.bus.register("L1", self._l1_handler)
        self.bus.start()

    def close(self) -> None:
        self.cancel_attach("engine shutdown")
        self.timers.cancel_all("engine shutdown")
        self.bus.stop()

    def _active_ctx(self) -> AttachContext | None:
        with self._ctx_lock:
            return self._current_ctx

    def _checkpoint(self, ctx: AttachContext) -> None:
        with self._ctx_lock:
            if ctx.cancelled or self._current_ctx is not ctx:
                raise AttachCancelled("Attach transaction cancelled")

    def _delay(self, ctx: AttachContext, factor: float = 1.0) -> None:
        speed = float(self.store.snapshot().get("runtime", {}).get("speedMultiplier", 1.0) or 1.0)
        total = max(0.0, self.step_delay * factor / speed)
        self._checkpoint(ctx)
        self.clock.sleep(total)
        self._checkpoint(ctx)

    def cancel_attach(self, reason: str = "cancelled by user") -> bool:
        with self._ctx_lock:
            ctx = self._current_ctx
            if not ctx:
                return False
            ctx.cancel()
        self.store.log("System", "Attach", "CANCEL", reason, tx_id=ctx.transaction_id)
        return True

    def _wait_cancelled_attach(self, timeout: float = 0.6) -> None:
        """Give a cancelled orchestration thread a short chance to unwind.

        Reset/CFUN=0 should not return while the previous Attach is still
        occupying TaskBus workers when it can be drained quickly. The timeout
        keeps UI operations responsive if a lower layer is genuinely stuck.
        """
        with self._ctx_lock:
            thread = self._attach_thread
        if thread and thread is not threading.current_thread() and thread.is_alive():
            thread.join(timeout=max(0.0, timeout))

    def stop_attach(self, reason: str = "stopped by user") -> dict:
        """Stop only the active Attach transaction without resetting the session.

        This is intentionally different from reset() and CFUN=0.  It preserves
        completed steps, logs, trace and the current radio setting so the user
        can inspect what happened, while preventing the old orchestration thread
        from continuing to write state.
        """
        with self._ctx_lock:
            ctx = self._current_ctx
        if not ctx:
            return self.store.snapshot()
        self.cancel_attach(reason)
        self._wait_cancelled_attach(timeout=0.8)
        tx_id = ctx.transaction_id
        def update(state):
            if state.get("flow", {}).get("transactionId") != tx_id:
                return
            state["flow"]["running"] = False
            state["modem"]["attachStatus"] = "CANCELLED"
            state["modem"]["lastError"] = None
        self.store.mutate(update)
        return self.store.snapshot()

    def reset(self) -> dict:
        self.cancel_attach("reset requested")
        self._wait_cancelled_attach()
        self.timers.cancel_all("reset requested")
        self.security.disable()
        snap = self.store.reset_runtime(clear_logs=True)
        self.store.log("System", "All", "STATE", "Simulation state reset")
        return snap

    def set_cfun_zero(self) -> None:
        self.cancel_attach("AT+CFUN=0")
        self._wait_cancelled_attach()
        self.timers.cancel_all("AT+CFUN=0")
        self.security.disable()

        def update(state):
            state["modem"]["cfun"] = 0
            state["modem"]["attachStatus"] = "DETACHED"
            state["modem"]["cell"] = None
            state["modem"]["lastError"] = None
            state["security"] = self.security.public_state()
            state["flow"]["running"] = False
            state["flow"]["currentStep"] = None
            state["flow"]["finishedAt"] = utc_now()

        self.store.mutate(update)

    def start_attach(self) -> tuple[bool, str]:
        # A duplicate request must be rejected before touching timers/security
        # or waiting on the active orchestration thread.  The former ordering
        # could wait long enough for the first Attach to finish and then start a
        # surprising second transaction from the same double-click.
        with self._ctx_lock:
            if self._current_ctx and not self._current_ctx.cancelled:
                return False, "Attach flow is already running"

        self._wait_cancelled_attach(timeout=0.3)
        with self._ctx_lock:
            if self._current_ctx and not self._current_ctx.cancelled:
                return False, "Attach flow is already running"
            snapshot = self.store.snapshot()
            scenario = snapshot["scenario"]["id"]
            ctx = AttachContext(scenario=scenario, custom_fault=copy.deepcopy(snapshot["faultConfig"]))
            ctx.injector = FaultInjector(ctx.custom_fault, lambda e: self._event(ctx, "FAULT_INJECTED", **e))
            ctx.started_monotonic = self.clock.now()
            self._current_ctx = ctx

        self.timers.cancel_all("new Attach")
        self.security.disable()

        def update(state):
            state["faultEvidence"] = []
            state["runtimeEvents"] = []
            state["primitiveTrace"] = []
            state["taskEvents"] = []
            state["diagnosis"]["lastReport"] = None
            state["diagnosis"]["blindReport"] = None
            state["diagnosis"]["systemCheck"] = None
            state["modem"]["cfun"] = 1
            state["modem"]["attachStatus"] = "SEARCHING"
            state["modem"]["lastError"] = None
            state["modem"]["cell"] = None
            state["security"] = self.security.public_state()
            state["flow"].update(
                {
                    "transactionId": ctx.transaction_id,
                    "running": True,
                    "currentStep": "cfun_enable",
                    "completed": [],
                    "failedStep": None,
                    "startedAt": utc_now(),
                    "finishedAt": None,
                    "durationMs": None,
                    "stepTimingMs": {},
                }
            )
            state["metrics"]["attachAttempts"] += 1

        self.store.mutate(update)
        ctx.step_started_monotonic["cfun_enable"] = ctx.started_monotonic
        self._complete_step(ctx, "cfun_enable")
        self.store.log("AP", "Modem", "AT", "AT+CFUN=1 → enable LTE radio", tx_id=ctx.transaction_id)
        thread = threading.Thread(target=self._run_attach, args=(ctx,), name=f"Attach-{ctx.transaction_id}", daemon=True)
        with self._ctx_lock:
            self._attach_thread = thread
        thread.start()
        return True, ctx.transaction_id

    def _set_current_step(self, ctx: AttachContext, step: str) -> None:
        self._checkpoint(ctx)
        ctx.current_step = step
        ctx.step_started_monotonic.setdefault(step, self.clock.now())

        def update(state):
            if state["flow"].get("transactionId") == ctx.transaction_id:
                state["flow"]["currentStep"] = step
                state["flow"].setdefault("stepTimingMs", {}).setdefault(step, None)

        self.store.mutate(update)

    def _complete_step(self, ctx: AttachContext, step: str) -> None:
        self._checkpoint(ctx)
        started = ctx.step_started_monotonic.setdefault(step, ctx.started_monotonic)
        elapsed_ms = max(0, int((self.clock.now() - started) * 1000))

        def update(state):
            if state["flow"].get("transactionId") != ctx.transaction_id:
                return
            if step not in state["flow"]["completed"]:
                state["flow"]["completed"].append(step)
            state["flow"]["currentStep"] = step
            state["flow"].setdefault("stepTimingMs", {})[step] = elapsed_ms

        self.store.mutate(update)

    def _append_history(self, state: dict, ctx: AttachContext, result: str, duration_ms: int, failed_step: str | None = None, error: str | None = None) -> None:
        record = {
            "transactionId": ctx.transaction_id,
            "scenario": ctx.scenario,
            "result": result,
            "durationMs": duration_ms,
            "failedStep": failed_step,
            "error": error,
            "finishedAt": utc_now(),
            "stepTimingMs": copy.deepcopy(state.get("flow", {}).get("stepTimingMs", {})),
        }
        state.setdefault("runHistory", []).append(record)
        state["runHistory"] = state["runHistory"][-20:]

    def _archive_finished_run(self) -> None:
        callback = self.hooks.run_finished
        if callback is None:
            return
        try:
            archived = callback(self.store.snapshot()) or {}
            run_id = archived.get("runId")

            def update(state):
                state["runArchive"] = {
                    "status": "ARCHIVED",
                    "lastRunId": run_id,
                    "lastRunDir": archived.get("runDir"),
                    "error": None,
                }

            self.store.mutate(update, persist=True)
            self.store.log("Run", "Archive", "RESULT", f"Interactive run archived: {run_id}")
        except Exception as exc:
            def update_failed(state):
                state["runArchive"] = {
                    "status": "FAILED",
                    "lastRunId": None,
                    "lastRunDir": None,
                    "error": str(exc),
                }

            self.store.mutate(update_failed, persist=True)
            self.store.log("Run", "Archive", "ERROR", f"Interactive run archive failed: {exc}")

    def _finish_success(self, ctx: AttachContext) -> None:
        self._checkpoint(ctx)
        self.timers.cancel_all("Attach success")
        duration_ms = int((self.clock.now() - ctx.started_monotonic) * 1000)

        def update(state):
            if state["flow"].get("transactionId") != ctx.transaction_id:
                return
            state["modem"]["attachStatus"] = "ATTACHED"
            for evidence in state["faultEvidence"]:
                evidence.update(final_effect="DELIVERED_WITHOUT_FAILURE", root_cause=None)
            state["modem"]["lastError"] = None
            state["security"] = self.security.public_state()
            state["runArchive"] = {
                "status": "PENDING",
                "lastRunId": state.get("runArchive", {}).get("lastRunId"),
                "lastRunDir": state.get("runArchive", {}).get("lastRunDir"),
                "error": None,
            }
            state["flow"]["running"] = False
            state["flow"]["currentStep"] = "attach_complete"
            state["flow"]["finishedAt"] = utc_now()
            state["flow"]["durationMs"] = duration_ms
            state["metrics"]["attachSuccesses"] += 1
            state["metrics"]["lastDurationMs"] = duration_ms
            self._append_history(state, ctx, "SUCCESS", duration_ms)

        self.store.log("Modem", "AP", "RESULT", "+CGATT: 1, LTE attach complete", {"durationMs": duration_ms}, ctx.transaction_id)
        self.store.mutate(update, persist=True)
        self._archive_finished_run()

    def _finish_failure(self, ctx: AttachContext, exc: Exception, step: str | None) -> None:
        step = flow_step_for_stage(step)
        with self._ctx_lock:
            if self._current_ctx is not ctx:
                return
        duration_ms = int((self.clock.now() - ctx.started_monotonic) * 1000)

        def update(state):
            if state["flow"].get("transactionId") != ctx.transaction_id:
                return
            state["modem"]["attachStatus"] = "FAILED"
            state["modem"]["lastError"] = str(exc)
            state["runArchive"] = {
                "status": "PENDING",
                "lastRunId": state.get("runArchive", {}).get("lastRunId"),
                "lastRunDir": state.get("runArchive", {}).get("lastRunDir"),
                "error": None,
            }
            state["flow"]["running"] = False
            state["flow"]["failedStep"] = step or state["flow"].get("currentStep")
            state["flow"]["finishedAt"] = utc_now()
            state["flow"]["durationMs"] = duration_ms
            state["metrics"]["attachFailures"] += 1
            state["metrics"]["lastDurationMs"] = duration_ms
            self._append_history(state, ctx, "FAILED", duration_ms, step or state["flow"].get("currentStep"), str(exc))

        ctx.operation_stop.set()
        self.timers.cancel_all("Attach failed")
        snap = self.store.snapshot()
        report = self.diagnosis.analyze(
            step=step or snap.get("flow", {}).get("currentStep"),
            message=str(exc),
            transaction_id=ctx.transaction_id,
            scenario=ctx.scenario,
            recent_trace=snap.get("runtimeEvents", []),
        )
        self.store.log("Modem", "AP", "ERROR", f"Attach failed: {exc}", {"step": step}, ctx.transaction_id)
        self.store.log("Diagnosis", "Engineer", "ERROR", f"{report['code']}: {report['summary']}", report, ctx.transaction_id)

        def update_with_diagnosis(state):
            update(state)
            state["diagnosis"]["lastReport"] = copy.deepcopy(report)
            for evidence in state["faultEvidence"]:
                if evidence.get("correlation_id") == report.get("correlation_id"):
                    evidence.update(root_cause=report["root_cause"], final_effect="FAILED", elapsed=report.get("elapsed") if report.get("elapsed") is not None else evidence.get("elapsed"))
            state["diagnosis"]["history"].append(copy.deepcopy(report))
            state["diagnosis"]["history"] = state["diagnosis"]["history"][-30:]

        self.store.mutate(update_with_diagnosis, persist=True)
        self._archive_finished_run()

    def _finish_cancelled(self, ctx: AttachContext) -> None:
        self.timers.cancel_all("Attach cancelled")
        duration_ms = int((self.clock.now() - ctx.started_monotonic) * 1000)
        snap = self.store.snapshot()
        if snap["flow"].get("transactionId") != ctx.transaction_id:
            return

        def update(state):
            if state["flow"].get("transactionId") != ctx.transaction_id:
                return
            # Do not overwrite an explicit reset/CFUN=0 state.
            if state["flow"].get("running"):
                state["flow"]["running"] = False
                state["flow"]["finishedAt"] = utc_now()
                state["flow"]["durationMs"] = duration_ms
            state["metrics"]["attachCancelled"] += 1

        self.store.log("Attach", "System", "CANCELLED", "Attach transaction stopped safely", tx_id=ctx.transaction_id)
        self.store.mutate(update)

    def _event(self, ctx, event, **detail):
        detail.setdefault('correlation_id', ctx.correlation_id)
        detail.setdefault('transactionId', ctx.transaction_id)
        detail.setdefault('step', getattr(ctx,'current_step',None))
        self.store.record_runtime_event(dict(event=event, **detail))

    def _run_attach(self, ctx):
        try:
            self._delay(ctx, 0.5)
            self._set_current_step(ctx, 'nas_attach_req')
            self.bus.request('NAS','NAS_ATTACH_REQ',{'ctx':ctx},timeout=5)
            self._complete_step(ctx,'nas_attach_req')
            self._set_current_step(ctx,'mib_sib_read')
            info=self._exchange(ctx,'mib_sib_read',{'type':'READ_MIB_SIB','ueId':'UE-001'})
            self._complete_step(ctx,'mib_sib_read')
            self._set_current_step(ctx,'system_info_validate')
            self.bus.request('RRC','SYSTEM_INFO_VALIDATE_REQ',{'ctx':ctx,'data':info},timeout=5)
            self._complete_step(ctx,'system_info_validate')
            requests=[
                ('random_access',{'type':'RA_PREAMBLE','ueId':'UE-001','preambleIndex':7}),
                ('rrc_connection',{'type':'RRC_CONNECTION_REQUEST','ueId':'UE-001','cause':'mo-Signalling'}),
                ('nas_attach_request',{'type':'NAS_ATTACH_REQUEST','ueId':'UE-001','attachType':'EPS_ATTACH'}),
                ('authentication',{'type':'NAS_AUTHENTICATION_RESPONSE','ueId':'UE-001','res':'SIMULATED_RES','auth_result':'SUCCESS'}),
                ('security_mode',{'type':'NAS_SECURITY_MODE_COMPLETE','ueId':'UE-001','integrity':'EIA2','cipher':'EEA2'}),
                ('attach_complete',{'type':'NAS_ATTACH_COMPLETE','ueId':'UE-001'}),
            ]
            for stage,message in requests:
                self._delay(ctx)
                self._set_current_step(ctx,stage)
                # Procedure-level LTE timers are tracked separately from the
                # short per-message engineering guards used by _exchange().
                # T3410 is UE-side: Attach Request -> Attach Accept/Reject.
                if stage == 'nas_attach_request':
                    self.timers.start('T3410', 15.0, transaction_id=ctx.transaction_id, step=stage)
                    self._event(ctx, 'PROCEDURE_TIMER_STARTED', timer='T3410', timer_side='UE',
                                purpose='Attach Request → Attach Accept/Reject')
                response=self._exchange(ctx,stage,message)
                if stage=='rrc_connection':
                    self._exchange(ctx,'rrc_complete',{'type':'RRC_CONNECTION_SETUP_COMPLETE','ueId':'UE-001','transactionIdentifier':1})
                # T3460 is network-side in TS 24.301.  The controller tracks the
                # MME-stub procedure boundary honestly: start when a Command/Request
                # has just been produced, stop when the UE response is received.
                if stage == 'nas_attach_request' and response.get('kind') == 'NAS_AUTHENTICATION_REQUEST':
                    self.timers.start('T3460', 6.0, transaction_id=ctx.transaction_id, step='authentication')
                    self._event(ctx, 'PROCEDURE_TIMER_STARTED', timer='T3460', timer_side='MME_STUB',
                                purpose='Authentication Request → Authentication Response')
                if stage == 'authentication':
                    self.timers.stop('T3460', 'Authentication Response received by MME stub')
                    if response.get('kind') == 'NAS_SECURITY_MODE_COMMAND':
                        self.timers.start('T3460', 6.0, transaction_id=ctx.transaction_id, step='security_mode')
                        self._event(ctx, 'PROCEDURE_TIMER_STARTED', timer='T3460', timer_side='MME_STUB',
                                    purpose='Security Mode Command → Security Mode Complete/Reject')
                if stage=='security_mode':
                    self.timers.stop('T3460', 'Security Mode Complete received by MME stub')
                    self.security.mark_nas_negotiated()
                    self.store.mutate(lambda state:state.__setitem__('security',self.security.public_state()))
                self._complete_step(ctx,stage)
                if stage=='security_mode':
                    self._set_current_step(ctx,'attach_accept')
                    self._complete_step(ctx,'attach_accept')
                    self.timers.stop('T3410', 'Attach Accept received')
                    # T3450 is network-side: Attach Accept -> Attach Complete.
                    self.timers.start('T3450', 6.0, transaction_id=ctx.transaction_id, step='attach_complete')
                    self._event(ctx, 'PROCEDURE_TIMER_STARTED', timer='T3450', timer_side='MME_STUB',
                                purpose='Attach Accept → Attach Complete')
                if stage=='attach_complete':
                    self.timers.stop('T3450', 'Attach Complete received by MME stub')
            self._finish_success(ctx)
        except AttachCancelled: self._finish_cancelled(ctx)
        except Exception as exc:
            self._finish_failure(ctx,exc,getattr(exc,'step',None) or self.store.snapshot()['flow'].get('currentStep'))
        finally:
            ctx.operation_stop.set()
            with self._ctx_lock:
                if self._current_ctx is ctx: self._current_ctx=None
                if self._attach_thread is threading.current_thread(): self._attach_thread=None

    def _exchange(self, ctx, stage, message):
        self._checkpoint(ctx)
        primitive,target,_,expected=CATALOG[stage]
        ctx.correlation_id=f'{ctx.transaction_id}-{stage}'
        corr=ctx.correlation_id
        timer_meta = timer_spec_for_stage(stage)
        timer = timer_meta['name']
        limit=ctx.custom_fault.get('timeout_ms',3000)/1000
        expired=threading.Event()
        finished=queue.Queue()
        started=time.monotonic()
        ctx.operation_stop.clear()
        def on_expire(name):
            self._event(ctx,'TIMER_EXPIRED',correlation_id=corr,timer=name,timeout_limit=limit*1000,
                        start_time=start_wall,expiry_time=utc_now(),elapsed=(time.monotonic()-started)*1000,
                        waiting_primitive=primitive,last_primitive=message['type'],root_cause='TIMER_EXPIRED')
            self.store.mutate(lambda state: state['timers'][name].update(
                elapsed=(time.monotonic()-started)*1000,expiryTime=utc_now(),correlation_id=corr,
                waitingPrimitive=primitive,lastPrimitive=message['type']))
            expired.set()
        start_wall=utc_now()
        self._event(ctx,'TIMER_STARTED',timer=timer,timer_label=timer_meta['label'],timer_kind=timer_meta['kind'],
                    timeout_limit=limit*1000,start_time=start_wall,waiting_primitive=primitive)
        self.timers.start(timer,limit,transaction_id=ctx.transaction_id,step=stage,on_expire=on_expire)
        self.store.mutate(lambda state: state['timers'][timer].update(correlation_id=corr,
            waitingPrimitive=primitive,lastPrimitive=message['type'],timeoutLimit=limit*1000,startTime=start_wall))
        def deliver():
            try:
                response=self.bus.request('RRC','NAS_UL_DATA_REQ',{'ctx':ctx,'message':message,'stage':stage},timeout=limit+1)
                self._checkpoint(ctx)
                if ctx.operation_stop.is_set(): return
                after,delay,copies,evidence=ctx.injector.intercept(response,layer='primitive',stage=stage,
                    primitive=primitive,correlation_id=corr,transaction_id=ctx.transaction_id)
                self._event(ctx,'PRIMITIVE_CREATED',primitive=primitive,target_task=target,
                            original_parameters=response,before=response,after=after,expected=expected,
                            fault_type=evidence['fault_type'] if evidence else None)
                if delay and ctx.operation_stop.wait(delay): return
                if not copies:
                    self._event(
                        ctx, 'CONTROL_PLANE_DELIVERY_DECISION', primitive=primitive, target_task=target,
                        decisionType='原语交付判定', decision='DROP',
                        rule=f'{primitive} must be delivered to {target} before the stage timer expires',
                        checks=[
                            {'name':'网络响应已生成','field':'response','expected':'present','actual':'present','passed':True},
                            {'name':'原语交付','field':'delivery','expected':f'delivered to {target}','actual':'suppressed by FaultInjector','passed':False},
                        ],
                        rejectCause='PRIMITIVE_DELIVERY_SUPPRESSED', failedField='delivery',
                        expectedValue=f'delivered to {target}', actualValue='suppressed by FaultInjector',
                        inputMessage=copy.deepcopy(response), outputMessage={'kind':'NO_DELIVERY','targetTask':target},
                        root_cause='PRIMITIVE_MISSING',
                    )
                result=None
                for i in range(copies):
                    self._checkpoint(ctx)
                    if ctx.operation_stop.is_set(): return
                    result=self.bus.request(target,primitive,{'ctx':ctx,'data':after,'stage':stage,
                        'before':response,'after':after,'expected':expected,'related_timer':timer,
                        'fault_type':evidence['fault_type'] if evidence else None},timeout=limit+1)
                if copies: finished.put((True,result))
            except Exception as exc:
                finished.put((False,exc))
        threading.Thread(target=deliver,name='Exchange-'+corr,daemon=True).start()
        while True:
            self._checkpoint(ctx)
            if expired.is_set():
                ctx.operation_stop.set()
                raise ProtocolFailure(f'{timer} expired waiting for {primitive}',stage)
            try: ok,result=finished.get(timeout=0.005)
            except queue.Empty: continue
            if expired.is_set():
                ctx.operation_stop.set()
                raise ProtocolFailure(f'{timer} expired waiting for {primitive}',stage)
            self.store.mutate(lambda state: [e.update(elapsed=(time.monotonic()-started)*1000) for e in state['faultEvidence'] if e.get('correlation_id') == corr])
            self.timers.stop(timer,'response processed')
            if ok:
                self._event(ctx,'STATE_TRANSITION',primitive=primitive,actual=result,expected=expected)
                return result
            raise result

    def _network(self, ctx, message, source='L1', stage=None):
        self._checkpoint(ctx)
        request_id=uuid4().hex[:10]
        payload={**copy.deepcopy(message),'requestId':request_id,'transactionId':ctx.transaction_id,
                 'correlation_id':ctx.correlation_id}
        payload,delay,copies,evidence=ctx.injector.intercept(payload,layer='socket',stage=stage,
            primitive=message['type'],correlation_id=ctx.correlation_id,transaction_id=ctx.transaction_id)
        if delay and ctx.operation_stop.wait(delay): raise AttachCancelled('Socket delay cancelled')
        if not copies:
            self._event(ctx,'SOCKET_DROP',primitive=message['type'],root_cause='SOCKET_DROP',actual=None)
            self._event(
                ctx, 'CONTROL_PLANE_DELIVERY_DECISION', primitive=message['type'],
                decisionType='Modem-eNB Socket 交付判定', decision='DROP',
                rule='generated control-plane request must be transmitted to the eNB/MME peer',
                checks=[
                    {'name':'请求已生成','field':'request','expected':'present','actual':'present','passed':True},
                    {'name':'Socket 发送','field':'delivery','expected':'TX to peer','actual':'suppressed by FaultInjector','passed':False},
                ],
                rejectCause='SOCKET_MESSAGE_DROPPED', failedField='delivery',
                expectedValue='TX to peer', actualValue='suppressed by FaultInjector',
                inputMessage=copy.deepcopy(payload), outputMessage={'kind':'NO_WIRE_TX'},
                root_cause='SOCKET_DROP',
            )
            ctx.operation_stop.wait(ctx.custom_fault.get('timeout_ms',3000)/1000+1)
            raise AttachCancelled('Socket message was dropped')
        self._checkpoint(ctx)
        if ctx.operation_stop.is_set(): raise AttachCancelled('Operation expired')
        tx_transport = self.store.record_transport_event(
            'modemEnb','TX',request_id=request_id,transaction_id=ctx.transaction_id,
            message_type=message['type'],payload=payload)
        self.store.log(source,'eNB','SOCKET_TX',message['type'],payload,ctx.transaction_id)
        self._event(ctx,'SOCKET_TX',primitive=message['type'],actual=payload,
                    eventId=(tx_transport or {}).get('eventId'), requestId=request_id,
                    payloadSha256=(tx_transport or {}).get('payloadSha256'),
                    sizeBytes=(tx_transport or {}).get('sizeBytes'), source='Modem', destination='eNB/MME')
        started=time.monotonic()
        try: response=self.hooks.network_request(payload)
        except Exception as exc:
            code='SOCKET_TIMEOUT' if isinstance(exc,TimeoutError) else 'SOCKET_ERROR'
            self._event(ctx,code,root_cause=code,actual=str(exc),primitive=message['type'])
            self.store.record_transport_event('modemEnb','ERROR',request_id=request_id,message_type=message['type'])
            raise
        self._checkpoint(ctx)
        if ctx.operation_stop.is_set(): raise AttachCancelled('Late socket response discarded')
        if not isinstance(response,dict):
            self._event(ctx,'VALIDATION_FAILED',root_cause='PRIMITIVE_MALFORMED',actual=response,expected='object')
            raise ProtocolFailure('Malformed network response',stage)
        if response.get('requestId',request_id)!=request_id:
            self._event(ctx,'VALIDATION_FAILED',root_cause='UNEXPECTED_PRIMITIVE',actual=response.get('requestId'),expected=request_id)
            raise ProtocolFailure('Socket correlation mismatch',stage)
        rtt=round((time.monotonic()-started)*1000)
        rx_transport = self.store.record_transport_event(
            'modemEnb','RX',request_id=request_id,transaction_id=ctx.transaction_id,
            message_type=response.get('kind') or message['type'],rtt_ms=rtt,payload=response)
        self.store.log('eNB',source,'SOCKET_RX',response.get('kind','UNKNOWN'),response,ctx.transaction_id)
        self._event(ctx,'SOCKET_RX',primitive=response.get('kind') or message['type'],actual=response,
                    wireMessageKind=response.get('kind') or message['type'],
                    eventId=(rx_transport or {}).get('eventId'), requestId=request_id,
                    payloadSha256=(rx_transport or {}).get('payloadSha256'),
                    sizeBytes=(rx_transport or {}).get('sizeBytes'), rttMs=rtt,
                    source='eNB/MME', destination='Modem')
        decision = response.get('networkDecision') if isinstance(response, dict) else None
        if isinstance(decision, dict) and not decision.get('peerEvidenceRecorded'):
            event_name = 'NETWORK_AUTH_DECISION' if stage == 'authentication' else 'NETWORK_CONTROL_DECISION'
            self._event(
                ctx, event_name, primitive=message['type'],
                decisionType=decision.get('decisionType'), decision=decision.get('decision'), rule=decision.get('rule'),
                checks=copy.deepcopy(decision.get('checks') or []),
                rejectCause=decision.get('rejectCause'), failedField=decision.get('failedField'),
                expectedValue=decision.get('expectedValue'), actualValue=decision.get('actualValue'),
                decisionLayer=decision.get('decisionLayer'), policySource=decision.get('policySource'),
                procedure=decision.get('procedure'), decisionPoint=decision.get('decisionPoint'),
                checkCount=decision.get('checkCount'), failedCheck=copy.deepcopy(decision.get('failedCheck')),
                causeChain=copy.deepcopy(decision.get('causeChain') or []),
                inputMessage=copy.deepcopy(decision.get('inputMessage') or payload),
                outputMessage=copy.deepcopy(decision.get('outputMessage') or response),
                networkContextBefore=copy.deepcopy(decision.get('networkContextBefore')),
                networkContextAfter=copy.deepcopy(decision.get('networkContextAfter') or response.get('networkContext')),
                expectedSource=decision.get('expectedSource'), contextCreatedBy=decision.get('contextCreatedBy'),
                stateTransitions=copy.deepcopy(decision.get('stateTransitions') or []),
                responseGeneration=copy.deepcopy(decision.get('responseGeneration') or {}),
                pipeline=copy.deepcopy(decision.get('pipeline') or []),
                root_cause='NETWORK_REJECT' if decision.get('decision') == 'REJECT' else None,
            )
        return response

    def _consume_response(self, task, primitive, payload):
        ctx=payload['ctx']; self._checkpoint(ctx)
        if ctx.operation_stop.is_set(): raise AttachCancelled('Late primitive discarded')
        stage=payload['stage']; data=payload['data']
        expected=CATALOG[stage][3]
        self._event(ctx,'PRIMITIVE_CONSUMED',primitive=primitive,target_task=task,actual=data,
                    expected=expected,before=payload.get('before'),after=data,related_timer=payload.get('related_timer'),
                    fault_type=payload.get('fault_type'))
        key=(ctx.correlation_id,primitive)
        code=None; field=None; wanted=None; actual=None
        active_stage=getattr(ctx,'current_step',None)
        required_stage='rrc_connection' if stage=='rrc_complete' else stage
        if active_stage != required_stage:
            code='INVALID_STATE';field='current_step';wanted=required_stage;actual=active_stage
        elif key in ctx.response_seen: code='DUPLICATE_PRIMITIVE'
        elif primitive!=CATALOG[stage][0] or task!=CATALOG[stage][1]: code='UNEXPECTED_PRIMITIVE'
        elif not isinstance(data,dict): code='PRIMITIVE_MALFORMED'
        else:
            if data.get('network_reject'):
                code='NETWORK_REJECT'
                field='auth_result' if 'auth_result' in data else 'kind'
                wanted='SUCCESS' if field == 'auth_result' else expected.get('kind')
                actual=data.get(field)
            else:
                for name,value in expected.items():
                    if name not in data or type(data[name]) is not type(value):
                        code='PRIMITIVE_MALFORMED';field=name;wanted=value;actual=data.get(name);break
                    if data[name]!=value:
                        code='PRIMITIVE_PARAMETER_INVALID'
                        field=name;wanted=value;actual=data[name];break
        ctx.response_seen.add(key)
        if code:
            self._event(ctx,'VALIDATION_FAILED',root_cause=code,primitive=primitive,target_task=task,
                        field=field,expected=wanted,actual=actual)
            raise ProtocolFailure(f'{primitive}: {code}; {field}: expected {wanted}, actual {actual}',stage)
        return data

    def _nas_handler(self, primitive, payload):
        if primitive=='NAS_ATTACH_REQ':
            self._checkpoint(payload['ctx']); return {'ok':True}
        return self._consume_response('NAS',primitive,payload)
    def _rrc_handler(self, primitive, payload):
        ctx=payload['ctx']; self._checkpoint(ctx)
        if primitive=='NAS_UL_DATA_REQ':
            return self.bus.request('L2','UL_DCCH_DATA_REQ',payload,timeout=ctx.custom_fault.get('timeout_ms',3000)/1000+1)
        if primitive=='SYSTEM_INFO_VALIDATE_REQ':
            try:
                self._validate_system_info(ctx,payload['data'])
            except ProtocolFailure as exc:
                self._event(ctx,'VALIDATION_FAILED',root_cause=exc.root_cause or 'PRIMITIVE_PARAMETER_INVALID',
                            primitive=exc.primitive or 'BCCH_DATA_IND', field=exc.field,
                            actual=exc.actual, expected=exc.expected)
                raise
            return payload['data']
        return self._consume_response('RRC',primitive,payload)
    def _l2_handler(self, primitive, payload):
        if primitive=='UL_DCCH_DATA_REQ':
            return self.bus.request('L1','AIR_MESSAGE_REQ',payload,timeout=payload['ctx'].custom_fault.get('timeout_ms',3000)/1000+1)
        return self._consume_response('L2',primitive,payload)
    def _l1_handler(self, primitive, payload):
        if primitive!='AIR_MESSAGE_REQ': raise ProtocolFailure('Unexpected L1 primitive')
        return self._network(payload['ctx'],payload['message'],stage=payload['stage'])

    def _validate_system_info(self, ctx: AttachContext, payload: dict) -> None:
        """Run the UE/RRC-side camping decision from the received BCCH payload.

        A system-information fault is not reduced to a preset verdict.  The RRC
        worker evaluates the actual BCCH_DATA_IND object and emits the same
        structured decision evidence used by network-side policy checks.
        """
        expected_enb = self.store.snapshot()["enb"]
        payload_obj = payload if isinstance(payload, dict) else {}
        mib = payload_obj.get("mib") if isinstance(payload_obj, dict) else None
        sib = payload_obj.get("sib") if isinstance(payload_obj, dict) else None
        checks = [
            {
                "name": "消息类型", "field": "kind", "expected": "SYSTEM_INFORMATION",
                "actual": payload_obj.get("kind"),
                "passed": bool(payload_obj) and payload_obj.get("kind") == "SYSTEM_INFORMATION",
                "failureCode": "SYSTEM_INFORMATION_KIND_INVALID",
            },
            {
                "name": "MIB 结构", "field": "mib", "expected": "present object",
                "actual": "present object" if isinstance(mib, dict) and mib else mib,
                "passed": isinstance(mib, dict) and bool(mib),
                "failureCode": "MIB_MISSING",
            },
            {
                "name": "SIB 结构", "field": "sib", "expected": "present object",
                "actual": "present object" if isinstance(sib, dict) and sib else sib,
                "passed": isinstance(sib, dict) and bool(sib),
                "failureCode": "SIB_MISSING",
            },
        ]
        if isinstance(sib, dict) and sib:
            checks.extend([
                {
                    "name": "Cell Barred", "field": "sib.cellBarred", "expected": False,
                    "actual": sib.get("cellBarred"), "passed": sib.get("cellBarred") is False,
                    "failureCode": "CELL_BARRED",
                },
                {
                    "name": "PLMN", "field": "sib.plmn", "expected": expected_enb["plmn"],
                    "actual": sib.get("plmn"), "passed": sib.get("plmn") == expected_enb["plmn"],
                    "failureCode": "PLMN_MISMATCH",
                },
                {
                    "name": "TAC", "field": "sib.trackingAreaCode", "expected": expected_enb["tac"],
                    "actual": sib.get("trackingAreaCode"), "passed": sib.get("trackingAreaCode") == expected_enb["tac"],
                    "failureCode": "TAC_MISMATCH",
                },
            ])
        failed = next((item for item in checks if not item.get("passed")), None)
        decision = "REJECT" if failed else "ACCEPT"
        result_kind = "SYSTEM_INFO_REJECT" if failed else "SYSTEM_INFO_VALID"
        output = {
            "kind": result_kind,
            "accepted": failed is None,
            "rejectCause": failed.get("failureCode") if failed else None,
        }
        self._event(
            ctx, "UE_SYSTEM_INFO_DECISION", primitive="BCCH_DATA_IND",
            decisionType="RRC 驻留与系统信息判定", decision=decision,
            decisionLayer="UE / RRC", policySource="RRC system-information validation",
            procedure="SYSTEM_INFORMATION", decisionPoint="system_info_validate",
            rule="SYSTEM_INFORMATION valid AND MIB/SIB present AND cellBarred=false AND PLMN/TAC match",
            checks=copy.deepcopy(checks),
            rejectCause=failed.get("failureCode") if failed else None,
            failedField=failed.get("field") if failed else None,
            expectedValue=failed.get("expected") if failed else None,
            actualValue=failed.get("actual") if failed else None,
            inputMessage=copy.deepcopy(payload_obj), outputMessage=output,
            root_cause="PRIMITIVE_MALFORMED" if failed and failed.get("failureCode") in {
                "SYSTEM_INFORMATION_KIND_INVALID", "MIB_MISSING", "SIB_MISSING"
            } else ("PRIMITIVE_PARAMETER_INVALID" if failed else None),
        )
        if failed:
            malformed = failed.get("failureCode") in {"SYSTEM_INFORMATION_KIND_INVALID", "MIB_MISSING", "SIB_MISSING"}
            raise ProtocolFailure(
                f"System information rejected: {failed.get('failureCode')}", "system_info_validate",
                root_cause="PRIMITIVE_MALFORMED" if malformed else "PRIMITIVE_PARAMETER_INVALID",
                primitive="BCCH_DATA_IND", field=failed.get("field"),
                expected=failed.get("expected"), actual=failed.get("actual"),
            )

        def update(state):
            if state["flow"].get("transactionId") != ctx.transaction_id:
                return
            state["modem"]["attachStatus"] = "CAMPED"
            state["modem"]["cell"] = {
                "cellId": payload_obj["cellId"],
                "plmn": sib["plmn"],
                "tac": sib["trackingAreaCode"],
                "bandwidth": mib["dlBandwidth"],
                "qRxLevMin": sib.get("qRxLevMin"),
            }

        self.store.mutate(update)
        self.store.log("L1", "RRC", "PRIMITIVE", "BCCH_DATA_IND: MIB/SIB validation passed", payload_obj, ctx.transaction_id)


def build_enb_response(request, base_enb, socket_timeout=2.0, network_context: NetworkControlPlaneContext | None = None):
    """eNB/MME control-plane peer driven by received wire fields.

    With ``network_context`` this becomes a per-transaction stateful peer: later
    NAS/RRC decisions depend on earlier messages actually received on the TCP
    endpoint.  The optional argument keeps the pure stateless helper available
    for focused unit tests and third-party embedding.
    """
    kind = request.get("type")
    net_ctx = network_context.get(request) if network_context is not None else None
    context_before = copy.deepcopy(net_ctx.public()) if net_ctx is not None else None

    def ctx_check(name, field, expected, actual, passed):
        return {"name": name, "field": field, "expected": expected, "actual": actual, "passed": bool(passed)}

    def decision_response(*, decision_type, rule, checks, success_response, reject_kind, cause_map):
        failed = next((item for item in checks if not item.get("passed")), None)
        layer_map = {
            "READ_MIB_SIB": ("eNB / RRC", "eNB broadcast/context policy"),
            "RA_PREAMBLE": ("eNB / Random Access", "eNB random-access admission policy"),
            "RRC_CONNECTION_REQUEST": ("eNB / RRC", "eNB RRC admission policy"),
            "RRC_CONNECTION_SETUP_COMPLETE": ("eNB / RRC", "eNB RRC transaction policy"),
            "NAS_ATTACH_REQUEST": ("MME / NAS", "MME attach/context policy"),
            "NAS_AUTHENTICATION_RESPONSE": ("MME / NAS", "MME authentication policy"),
            "NAS_SECURITY_MODE_COMPLETE": ("MME / NAS Security", "MME security policy"),
            "NAS_ATTACH_COMPLETE": ("MME / NAS", "MME active-context policy"),
        }
        decision_layer, policy_source = layer_map.get(kind, ("Control Plane", "control-plane policy"))
        if failed is None:
            response = copy.deepcopy(success_response)
            decision = {
                "decisionType": decision_type, "decision": "ACCEPT", "rule": rule,
                "checks": copy.deepcopy(checks), "rejectCause": None, "failedField": None,
                "expectedValue": None, "actualValue": None,
            }
        else:
            reject_cause = cause_map.get(failed.get("field"), "NETWORK_POLICY_REJECT")
            response = {"kind": reject_kind, "network_reject": True,
                        "rejectCause": reject_cause, "failedField": failed.get("field")}
            decision = {
                "decisionType": decision_type, "decision": "REJECT", "rule": rule,
                "checks": copy.deepcopy(checks), "rejectCause": reject_cause,
                "failedField": failed.get("field"), "expectedValue": failed.get("expected"),
                "actualValue": failed.get("actual"),
            }
        decision.update({
            "decisionLayer": decision_layer, "policySource": policy_source,
            "procedure": kind, "decisionPoint": kind, "checkCount": len(checks),
            "failedCheck": copy.deepcopy(failed) if failed else None,
            "causeChain": ([failed.get("name"), decision.get("rejectCause"), reject_kind]
                           if failed else ["all checks passed", success_response.get("kind")]),
            "inputMessage": copy.deepcopy(request), "outputMessage": copy.deepcopy(response),
            "networkContextBefore": copy.deepcopy(context_before),
        })
        response["networkDecision"] = decision
        return response

    if kind == "READ_MIB_SIB":
        ue_id = request.get("ueId", "UE-001")
        checks = [
            ctx_check("UE Context", "ueId", "UE-001", ue_id, ue_id == "UE-001"),
            ctx_check("广播小区可用", "cellId", "configured cell", base_enb.get("cellId"), bool(base_enb.get("cellId"))),
        ]
        response = decision_response(
            decision_type="系统信息读取判定",
            rule="UE context exists AND configured broadcast cell is available",
            checks=checks,
            success_response={"kind": "SYSTEM_INFORMATION", "cellId": base_enb["cellId"],
                              "mib": copy.deepcopy(base_enb["mib"]), "sib": copy.deepcopy(base_enb["sib"])},
            reject_kind="SYSTEM_INFORMATION_REJECT",
            cause_map={"ueId": "UE_CONTEXT_UNKNOWN", "cellId": "CELL_CONTEXT_UNAVAILABLE"},
        )
        if net_ctx is not None:
            net_ctx.cell_state = "CAMPED" if not response.get("network_reject") else "REJECTED"

    elif kind == "RA_PREAMBLE":
        preamble = request.get("preambleIndex")
        ue_id = request.get("ueId", "UE-001")
        cell_barred = bool((base_enb.get("sib") or {}).get("cellBarred"))
        checks = [ctx_check("UE Context", "ueId", "UE-001", ue_id, ue_id == "UE-001")]
        if net_ctx is not None:
            checks.append(ctx_check("Cell Context", "network.cellState", "CAMPED", net_ctx.cell_state, net_ctx.cell_state == "CAMPED"))
        checks += [
            ctx_check("小区允许随机接入", "cellBarred", False, cell_barred, not cell_barred),
            ctx_check("Preamble 类型", "preambleIndex", "integer", type(preamble).__name__, type(preamble) is int),
            ctx_check("Preamble 范围", "preambleIndex", "0..63", preamble, type(preamble) is int and 0 <= preamble <= 63),
        ]
        response = decision_response(
            decision_type="随机接入准入判定",
            rule="UE/cell context valid AND cell allows access AND preambleIndex is integer in 0..63",
            checks=checks,
            success_response={"kind": "RANDOM_ACCESS_RESPONSE", "accepted": True, "temporaryCRNTI": "0x4A2B", "timingAdvance": 3},
            reject_kind="RANDOM_ACCESS_REJECT",
            cause_map={"ueId": "UE_CONTEXT_UNKNOWN", "network.cellState": "CELL_CONTEXT_NOT_READY",
                       "cellBarred": "CELL_BARRED", "preambleIndex": "INVALID_PREAMBLE_INDEX"},
        )
        if net_ctx is not None:
            if response.get("network_reject"):
                net_ctx.random_access_state = "REJECTED"
            else:
                net_ctx.random_access_state = "COMPLETE"
                net_ctx.temporary_crnti = response.get("temporaryCRNTI")

    elif kind == "RRC_CONNECTION_REQUEST":
        cause = request.get("cause")
        ue_id = request.get("ueId", "UE-001")
        allowed = {"mo-Signalling", "mo-Data"}
        checks = [ctx_check("UE Context", "ueId", "UE-001", ue_id, ue_id == "UE-001")]
        if net_ctx is not None:
            checks.append(ctx_check("Random Access Context", "network.randomAccessState", "COMPLETE", net_ctx.random_access_state, net_ctx.random_access_state == "COMPLETE"))
        checks += [
            ctx_check("建立原因字段", "cause", "string", type(cause).__name__, isinstance(cause, str)),
            ctx_check("RRC 准入原因", "cause", "mo-Signalling / mo-Data", cause, cause in allowed),
        ]
        response = decision_response(
            decision_type="RRC 准入判定",
            rule="UE/RA context valid AND establishmentCause is supported",
            checks=checks,
            success_response={"kind": "RRC_CONNECTION_SETUP", "transactionIdentifier": 1, "srb1": True},
            reject_kind="RRC_CONNECTION_REJECT",
            cause_map={"ueId": "UE_CONTEXT_UNKNOWN", "network.randomAccessState": "RA_CONTEXT_NOT_READY",
                       "cause": "UNSUPPORTED_ESTABLISHMENT_CAUSE"},
        )
        if net_ctx is not None:
            if response.get("network_reject"):
                net_ctx.rrc_state = "REJECTED"
            else:
                net_ctx.rrc_state = "SETUP_SENT"
                net_ctx.rrc_transaction_id = int(response["transactionIdentifier"])

    elif kind == "RRC_CONNECTION_SETUP_COMPLETE":
        ue_id = request.get("ueId", "UE-001")
        transaction_id = request.get("transactionIdentifier", 1)
        expected_rrc_tx = net_ctx.rrc_transaction_id if net_ctx is not None and net_ctx.rrc_transaction_id is not None else 1
        checks = [ctx_check("UE Context", "ueId", "UE-001", ue_id, ue_id == "UE-001")]
        if net_ctx is not None:
            checks.append(ctx_check("RRC Context", "network.rrcState", "SETUP_SENT", net_ctx.rrc_state, net_ctx.rrc_state == "SETUP_SENT"))
        checks.append(ctx_check("RRC Transaction", "transactionIdentifier", expected_rrc_tx, transaction_id, transaction_id == expected_rrc_tx))
        response = decision_response(
            decision_type="RRC Setup Complete 关联判定",
            rule="UE context valid AND active RRC setup exists AND transactionIdentifier matches",
            checks=checks,
            success_response={"kind": "RRC_CONNECTION_COMPLETE_ACK"},
            reject_kind="RRC_CONNECTION_COMPLETE_REJECT",
            cause_map={"ueId": "UE_CONTEXT_UNKNOWN", "network.rrcState": "RRC_CONTEXT_NOT_READY",
                       "transactionIdentifier": "RRC_TRANSACTION_MISMATCH"},
        )
        if net_ctx is not None:
            net_ctx.rrc_state = "CONNECTED" if not response.get("network_reject") else "REJECTED"

    elif kind == "NAS_ATTACH_REQUEST":
        ue_id = request.get("ueId", "UE-001")
        attach_type = request.get("attachType", "EPS_ATTACH")
        checks = [ctx_check("UE Context", "ueId", "UE-001", ue_id, ue_id == "UE-001")]
        if net_ctx is not None:
            checks.append(ctx_check("RRC Connected", "network.rrcState", "CONNECTED", net_ctx.rrc_state, net_ctx.rrc_state == "CONNECTED"))
        checks.append(ctx_check("Attach Type", "attachType", "EPS_ATTACH", attach_type, attach_type == "EPS_ATTACH"))
        response = decision_response(
            decision_type="NAS Attach 上下文判定",
            rule="UE context exists AND RRC is connected AND attach type is supported",
            checks=checks,
            success_response={"kind": "NAS_AUTHENTICATION_REQUEST", "rand": "SIMULATED_CHALLENGE",
                              "autn": "SIMULATED_AUTN", "xres": "SIMULATED_RES"},
            reject_kind="NAS_ATTACH_REJECT",
            cause_map={"ueId": "UE_CONTEXT_UNKNOWN", "network.rrcState": "RRC_NOT_CONNECTED",
                       "attachType": "ATTACH_TYPE_UNSUPPORTED"},
        )
        if net_ctx is not None:
            net_ctx.attach_type = str(attach_type)
            if response.get("network_reject"):
                net_ctx.attach_state = "REJECTED"
            else:
                net_ctx.attach_state = "ATTACHING"
                net_ctx.authentication_xres = str(response["xres"])
                net_ctx.authentication_state = "CHALLENGE_SENT"

    elif kind == "NAS_AUTHENTICATION_RESPONSE":
        expected_xres = net_ctx.authentication_xres if net_ctx is not None and net_ctx.authentication_xres else "SIMULATED_RES"
        checks = [ctx_check("UE Context", "ueId", "UE-001", request.get("ueId"), request.get("ueId") == "UE-001")]
        if net_ctx is not None:
            checks.append(ctx_check("Authentication Context", "network.authenticationState", "CHALLENGE_SENT",
                                    net_ctx.authentication_state, net_ctx.authentication_state == "CHALLENGE_SENT"))
        checks += [
            ctx_check("UE auth_result", "auth_result", "SUCCESS", request.get("auth_result"), request.get("auth_result") == "SUCCESS"),
            ctx_check("RES / XRES", "res", expected_xres, request.get("res"), request.get("res") == expected_xres),
        ]
        response = decision_response(
            decision_type="NAS 鉴权判定",
            rule="UE/authentication context valid AND auth_result == SUCCESS AND RES == stored XRES",
            checks=checks,
            success_response={"kind": "NAS_SECURITY_MODE_COMMAND", "auth_result": "SUCCESS", "integrity": "EIA2", "cipher": "EEA2"},
            reject_kind="NAS_AUTHENTICATION_REJECT",
            cause_map={"ueId": "UE_CONTEXT_MISMATCH", "network.authenticationState": "AUTH_CONTEXT_NOT_READY",
                       "auth_result": "UE_AUTH_RESULT_REJECT", "res": "RES_MISMATCH"},
        )
        if response.get("network_reject"):
            response["auth_result"] = "REJECT"
            if net_ctx is not None:
                net_ctx.authentication_state = "REJECTED"
        elif net_ctx is not None:
            net_ctx.authentication_state = "AUTHENTICATED"

    elif kind == "NAS_SECURITY_MODE_COMPLETE":
        ue_id = request.get("ueId", "UE-001")
        integrity = request.get("integrity")
        cipher = request.get("cipher")
        checks = [ctx_check("UE Context", "ueId", "UE-001", ue_id, ue_id == "UE-001")]
        if net_ctx is not None:
            checks.append(ctx_check("Authentication State", "network.authenticationState", "AUTHENTICATED",
                                    net_ctx.authentication_state, net_ctx.authentication_state == "AUTHENTICATED"))
        checks += [
            ctx_check("Integrity 算法", "integrity", "EIA2", integrity, integrity == "EIA2"),
            ctx_check("Cipher 算法", "cipher", "EEA2", cipher, cipher == "EEA2"),
        ]
        response = decision_response(
            decision_type="NAS Security Policy 判定",
            rule="UE authenticated AND Security Mode Complete confirms EIA2 AND EEA2",
            checks=checks,
            success_response={"kind": "NAS_ATTACH_ACCEPT", "guti": "GUTI-46001-0001-01", "defaultBearer": 5},
            reject_kind="NAS_SECURITY_MODE_REJECT",
            cause_map={"ueId": "UE_CONTEXT_UNKNOWN", "network.authenticationState": "AUTHENTICATION_NOT_COMPLETE",
                       "integrity": "INTEGRITY_ALGORITHM_MISMATCH", "cipher": "CIPHER_ALGORITHM_MISMATCH"},
        )
        if net_ctx is not None:
            if response.get("network_reject"):
                net_ctx.security_state = "REJECTED"
            else:
                net_ctx.integrity, net_ctx.cipher = str(integrity), str(cipher)
                net_ctx.security_state = "ACTIVE"
                net_ctx.attach_state = "ACCEPTED"

    elif kind == "NAS_ATTACH_COMPLETE":
        ue_id = request.get("ueId", "UE-001")
        checks = [ctx_check("UE Context", "ueId", "UE-001", ue_id, ue_id == "UE-001")]
        if net_ctx is not None:
            checks += [
                ctx_check("Security Context", "network.securityState", "ACTIVE", net_ctx.security_state, net_ctx.security_state == "ACTIVE"),
                ctx_check("Attach Context", "network.attachState", "ACCEPTED", net_ctx.attach_state, net_ctx.attach_state == "ACCEPTED"),
            ]
        response = decision_response(
            decision_type="Attach Complete 上下文判定",
            rule="Attach Complete belongs to active UE with established security context",
            checks=checks,
            success_response={"kind": "NAS_ATTACH_COMPLETE_ACK"},
            reject_kind="NAS_ATTACH_COMPLETE_REJECT",
            cause_map={"ueId": "UE_CONTEXT_UNKNOWN", "network.securityState": "SECURITY_CONTEXT_NOT_ACTIVE",
                       "network.attachState": "ATTACH_CONTEXT_NOT_ACCEPTED"},
        )
        if net_ctx is not None:
            net_ctx.attach_state = "ATTACHED" if not response.get("network_reject") else "REJECTED"
    else:
        response = {"kind": "ERROR", "message": "Unsupported request"}

    if isinstance(response.get("networkDecision"), dict) and net_ctx is not None:
        decision = response["networkDecision"]
        context_after = copy.deepcopy(net_ctx.public())
        decision["networkContextAfter"] = context_after
        response["networkContext"] = copy.deepcopy(context_after)

        # v6.0.2: make the network decision itself auditable.  The UI/diagnosis
        # can now show where an expected value came from, which transaction
        # context was read, which state changed, and which network message was
        # generated as a consequence.  These fields are derived from the peer's
        # own state and rule evaluation, never from Scenario/FaultConfig.
        failed_field = decision.get("failedField")
        expected_sources = {
            ("NAS_AUTHENTICATION_RESPONSE", "res"): ("Authentication Context.authenticationXres", "NAS_ATTACH_REQUEST → NAS_AUTHENTICATION_REQUEST"),
            ("NAS_AUTHENTICATION_RESPONSE", "network.authenticationState"): ("Authentication Context.authenticationState", "NAS_ATTACH_REQUEST → NAS_AUTHENTICATION_REQUEST"),
            ("NAS_SECURITY_MODE_COMPLETE", "network.authenticationState"): ("Authentication Context.authenticationState", "NAS_AUTHENTICATION_RESPONSE accepted"),
            ("NAS_SECURITY_MODE_COMPLETE", "integrity"): ("MME Security Policy.integrity", "NAS_SECURITY_MODE_COMMAND"),
            ("NAS_SECURITY_MODE_COMPLETE", "cipher"): ("MME Security Policy.cipher", "NAS_SECURITY_MODE_COMMAND"),
            ("NAS_ATTACH_COMPLETE", "network.securityState"): ("UE Security Context.securityState", "NAS_SECURITY_MODE_COMPLETE accepted"),
            ("NAS_ATTACH_COMPLETE", "network.attachState"): ("UE Attach Context.attachState", "NAS_SECURITY_MODE_COMPLETE accepted"),
            ("RRC_CONNECTION_SETUP_COMPLETE", "transactionIdentifier"): ("RRC Context.rrcTransactionId", "RRC_CONNECTION_SETUP"),
            ("RA_PREAMBLE", "preambleIndex"): ("eNB Random Access Policy.preambleRange", "configured cell policy"),
            ("READ_MIB_SIB", "cellId"): ("eNB Broadcast Context.cellId", "eNB configuration"),
        }
        source, created_by = expected_sources.get((kind, failed_field), (decision.get("policySource"), "current network policy/context"))
        decision["expectedSource"] = source
        decision["contextCreatedBy"] = created_by

        transitions = []
        before_state = context_before or {}
        for key, label in (
            ("cellState", "Cell"), ("randomAccessState", "Random Access"),
            ("rrcState", "RRC"), ("authenticationState", "Authentication"),
            ("securityState", "Security"), ("attachState", "Attach"),
        ):
            before_value = before_state.get(key)
            after_value = context_after.get(key)
            if before_value != after_value:
                transitions.append({"field": key, "label": label, "before": before_value, "after": after_value})
        decision["stateTransitions"] = transitions
        decision["responseGeneration"] = {
            "builder": "Network NAS/RRC Message Builder",
            "message": response.get("kind"),
            "cause": decision.get("rejectCause"),
            "generatedFromDecision": decision.get("decision"),
        }
        decision["pipeline"] = [
            {"stage": "CONTEXT_READ", "label": "读取网络上下文", "detail": source or decision.get("policySource")},
            {"stage": "RULE_EVALUATION", "label": "执行协议/策略规则", "detail": decision.get("rule")},
            {"stage": "DECISION", "label": "得到网络侧判定", "detail": decision.get("rejectCause") or decision.get("decision")},
            {"stage": "STATE_TRANSITION", "label": "更新网络侧状态", "detail": ", ".join(f"{x['label']} {x['before']} → {x['after']}" for x in transitions) or "状态保持"},
            {"stage": "MESSAGE_GENERATION", "label": "生成网络响应", "detail": response.get("kind")},
        ]

    for key in ("requestId", "correlation_id", "transactionId"):
        if key in request:
            response[key] = request[key]
            if isinstance(response.get("networkDecision"), dict):
                response["networkDecision"]["outputMessage"][key] = request[key]
    return response

