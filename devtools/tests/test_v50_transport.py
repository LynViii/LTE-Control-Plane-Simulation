import socket
import time
import pytest
from lte_sim import network
from lte_sim.config import Settings
from lte_sim.fault_injection.core import PRESETS
from lte_sim.web_app import SimulatorApplication

@pytest.mark.parametrize('kind,delay,expected,sent_auth',[
    ('SOCKET_DROP',0,'SOCKET_DROP',False),
    ('SOCKET_DELAY',50,None,True),
    ('SOCKET_DELAY',900,'TIMER_EXPIRED',False),
    ('MODIFY_FIELD',0,'NETWORK_REJECT',True),
])
def test_fault_on_actual_tcp_link(tmp_path,monkeypatch,kind,delay,expected,sent_auth):
    ports=[]
    while len(ports)<4:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        if port not in ports: ports.append(port)
    received=[]
    original=network.build_enb_response
    def capture(request,*args):
        received.append((time.monotonic(),request))
        return original(request,*args)
    monkeypatch.setattr(network,'build_enb_response',capture)
    settings=Settings(http_port=ports[0],ap_modem_port=ports[1],enb_port=ports[2],management_port=ports[3],
        state_file=tmp_path/'state.json',runs_dir=tmp_path/'runs',step_delay=0)
    app=SimulatorApplication(settings).start(block=False,enable_http=False)
    try:
        app.store.set_custom_fault(dict(PRESETS['AUTH_NETWORK_REJECT'],fault_type=kind,delay_ms=delay,timeout_ms=700))
        assert network.send_at_line('127.0.0.1',ports[1],'AT+CFUN=1',2)=='OK'
        deadline=time.monotonic()+5
        while app.store.snapshot()['flow']['running'] and time.monotonic()<deadline: time.sleep(.01)
        state=app.store.snapshot()
        auth=[request for _,request in received if request['type']=='NAS_AUTHENTICATION_RESPONSE']
        assert bool(auth)==sent_auth
        if expected:
            assert state['diagnosis']['lastReport']['root_cause']==expected
        else:
            assert state['modem']['attachStatus']=='ATTACHED'
            assert state['faultEvidence'][0]['elapsed']>=delay
        if kind=='MODIFY_FIELD': assert auth[0]['res']=='INVALID_RES' and auth[0]['auth_result']=='SUCCESS'
        assert state['runArchive']['status'] in {'PENDING','ARCHIVED'} or (tmp_path/'runs').exists()
    finally: app.stop()
