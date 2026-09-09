import pytest
from lte_sim.fault_injection.core import FaultConfig
from lte_sim.runtime.clock import VirtualClock
from lte_sim.runtime.timers import TimerManager
from lte_sim.state import StateStore

@pytest.mark.parametrize('field',['stage','task','primitive','fault_type','field','layer','fault_id'])
def test_nonstring_fault_metadata_is_validation_error(field):
    with pytest.raises(ValueError): FaultConfig.parse({field: []})

def test_late_cancelled_timer_cannot_expire_replacement(tmp_path):
    clock=VirtualClock()
    store=StateStore(tmp_path/'state.json')
    manager=TimerManager(store,clock)
    calls=[]
    manager.start('T300',1,on_expire=lambda name:calls.append('old'))
    old_callback=clock._queue[0].callback
    manager.start('T300',2,on_expire=lambda name:calls.append('new'))
    old_callback()  # An already dispatched callback races with cancel/restart.
    assert manager.snapshot()['T300']['status']=='RUNNING'
    assert calls==[]
    clock.advance(2)
    assert calls==['new']


def test_response_in_wrong_state_produces_runtime_evidence(tmp_path):
    from types import SimpleNamespace
    import threading
    from lte_sim.control_plane.engine import SimulatorEngine, EngineHooks
    from lte_sim.control_plane.engine import ProtocolFailure
    store=StateStore(tmp_path/'state.json')
    engine=SimulatorEngine(store,EngineHooks(lambda request:{}),step_delay=0)
    ctx=SimpleNamespace(transaction_id='test-state',current_step='random_access',correlation_id='test-state-auth',
        cancelled=False,operation_stop=threading.Event(),response_seen=set())
    store.mutate(lambda state:state['flow'].update(transactionId=ctx.transaction_id,running=True))
    engine._current_ctx=ctx
    try:
        with pytest.raises(ProtocolFailure,match='INVALID_STATE'):
            engine.bus.request('NAS','AUTH_RESPONSE_IND',dict(ctx=ctx,stage='authentication',data={'kind':'NAS_SECURITY_MODE_COMMAND','auth_result':'SUCCESS'}))
        evidence=store.snapshot()['runtimeEvents'][-1]
        assert evidence['root_cause']=='INVALID_STATE'
        assert evidence['actual']=='random_access' and evidence['expected']=='authentication'
    finally:
        engine._current_ctx=None
        engine.close()
