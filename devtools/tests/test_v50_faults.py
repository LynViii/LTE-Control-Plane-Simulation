import time
import pytest
from lte_sim.fault_injection.core import FaultConfig, PRESETS
from lte_sim.control_plane.engine import SimulatorEngine, EngineHooks, build_enb_response
from lte_sim.control_plane.network_context import NetworkControlPlaneContext
from lte_sim.state import StateStore

def run_case(tmp_path, **changes):
    store=StateStore(tmp_path/'state.json',max_logs=800)
    config=dict(PRESETS['AUTH_PARAMETER_INVALID'],timeout_ms=500)
    config.update(changes)
    store.set_custom_fault(config)
    sent=[]
    network_context = NetworkControlPlaneContext()
    def network(request):
        sent.append(request)
        return build_enb_response(
            request,
            store.snapshot()['enb'],
            network_context=network_context,
        )
    engine=SimulatorEngine(store,EngineHooks(network),step_delay=0)
    try:
        engine.start_attach()
        deadline=time.monotonic()+4
        while store.snapshot()['flow']['running'] and time.monotonic()<deadline: time.sleep(.005)
        snap=store.snapshot()
        assert not snap['flow']['running']
        return snap,sent
    finally: engine.close()

def test_after_is_consumed_and_diagnosed(tmp_path):
    state,_=run_case(tmp_path)
    e=state['faultEvidence'][0]
    assert (e['before'],e['after'])==('SUCCESS','REJECT')
    consumed=[x for x in state['runtimeEvents'] if x['event']=='PRIMITIVE_CONSUMED' and x['primitive']=='AUTH_RESPONSE_IND']
    assert consumed[0]['actual']['auth_result']=='REJECT'
    assert consumed[0]['after']==e['after_parameters']
    report=state['diagnosis']['lastReport']
    assert report['root_cause']=='PRIMITIVE_PARAMETER_INVALID'
    assert report['correlation_id']==e['correlation_id']==consumed[0]['correlation_id']
    assert report['field']=='auth_result' and report['actual']=='REJECT'
    assert state['flow']['failedStep']=='authentication'

@pytest.mark.parametrize('kind',['DROP','TIMER_TIMEOUT'])
def test_drop_has_no_target_consumption_and_real_timer_expiry(tmp_path,kind):
    state,_=run_case(tmp_path,fault_type=kind)
    events=state['runtimeEvents']
    assert not any(e['event']=='PRIMITIVE_CONSUMED' and e['primitive']=='AUTH_RESPONSE_IND' for e in events)
    expiry=next(e for e in events if e['event']=='TIMER_EXPIRED')
    assert expiry['elapsed']>=expiry['timeout_limit']==500
    assert expiry['start_time']<expiry['expiry_time']
    assert state['timers']['G_AUTHENTICATION']['status']=='EXPIRED'
    expected_root = 'PRIMITIVE_MISSING' if kind == 'DROP' else 'TIMER_EXPIRED'
    assert state['diagnosis']['lastReport']['root_cause']==expected_root
    if kind == 'DROP':
        assert 'TIMER_EXPIRED' in state['diagnosis']['lastReport']['secondary_causes']
    else:
        assert 'PRIMITIVE_MISSING' in state['diagnosis']['lastReport']['secondary_causes']

def test_duplicate_reaches_target_twice(tmp_path):
    state,_=run_case(tmp_path,fault_type='DUPLICATE')
    consumed=[e for e in state['runtimeEvents'] if e['event']=='PRIMITIVE_CONSUMED' and e['primitive']=='AUTH_RESPONSE_IND']
    assert len(consumed)==2
    assert state['diagnosis']['lastReport']['root_cause']=='DUPLICATE_PRIMITIVE'

def test_delay_affects_timeline_and_can_succeed(tmp_path):
    state,_=run_case(tmp_path,fault_type='DELAY',delay_ms=40,timeout_ms=1000)
    assert state['modem']['attachStatus']=='ATTACHED'
    assert state['flow']['stepTimingMs']['authentication']>=40
    assert state['faultEvidence'][0]['final_effect']=='DELIVERED_WITHOUT_FAILURE'

def test_delay_beyond_deadline_expires(tmp_path):
    state,_=run_case(tmp_path,fault_type='DELAY',delay_ms=750)
    assert state['diagnosis']['lastReport']['root_cause']=='TIMER_EXPIRED'

def test_socket_drop_suppresses_actual_transport_call(tmp_path):
    state,sent=run_case(tmp_path,layer='socket',primitive='NAS_AUTHENTICATION_RESPONSE',fault_type='SOCKET_DROP')
    assert not any(x['type']=='NAS_AUTHENTICATION_RESPONSE' for x in sent)
    assert state['diagnosis']['lastReport']['root_cause']=='SOCKET_DROP'
    assert any(e['event']=='TIMER_EXPIRED' for e in state['runtimeEvents'])

def test_socket_delay_affects_real_send_timing(tmp_path):
    state,sent=run_case(tmp_path,layer='socket',primitive='NAS_AUTHENTICATION_RESPONSE',fault_type='SOCKET_DELAY',delay_ms=30,timeout_ms=1000)
    assert any(x['type']=='NAS_AUTHENTICATION_RESPONSE' for x in sent)
    assert state['flow']['stepTimingMs']['authentication']>=30

def test_network_reject_is_actual_wire_value(tmp_path):
    state,sent=run_case(tmp_path,layer='socket',primitive='NAS_AUTHENTICATION_RESPONSE')
    assert next(x for x in sent if x['type']=='NAS_AUTHENTICATION_RESPONSE')['auth_result']=='REJECT'
    assert state['diagnosis']['lastReport']['root_cause']=='NETWORK_REJECT'

def test_normal_has_no_fault_evidence(tmp_path):
    state,_=run_case(tmp_path,enabled=False)
    assert state['modem']['attachStatus']=='ATTACHED' and len(state['flow']['completed'])==11
    assert not state['faultEvidence'] and state['diagnosis']['lastReport'] is None

def test_preset_is_fault_config(tmp_path):
    store=StateStore(tmp_path/'state.json')
    store.set_scenario('AUTH_PARAMETER_INVALID')
    assert store.snapshot()['faultConfig']==PRESETS['AUTH_PARAMETER_INVALID']

@pytest.mark.parametrize('changes',[{'task':'L1'},{'field':'not_a_field'},{'value':123},{'delay_ms':-1},{'timeout_ms':0},{'enabled':'yes'}])
def test_invalid_config_rejected(changes):
    with pytest.raises(ValueError): FaultConfig.parse(dict(PRESETS['AUTH_PARAMETER_INVALID'],**changes))
