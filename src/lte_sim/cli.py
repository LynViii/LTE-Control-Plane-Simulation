"""One actual Attach run, archived through the ordinary runtime."""
import argparse, json, time
from .config import Settings
from .web_app import SimulatorApplication
from .network import send_at_line
def main(argv=None):
    parser=argparse.ArgumentParser(description='Run one LTE Attach over actual TCP')
    parser.add_argument('--scenario',default='NORMAL')
    parser.add_argument('--fault-config',type=str,help='YAML file with id and fault object')
    args=parser.parse_args(argv)
    app=SimulatorApplication(Settings.from_env())
    try:
        app.start(block=False,enable_http=False)
        if args.fault_config:
            from pathlib import Path
            from .scenario import default_loader
            from .resources import resource_root
            app.store.set_custom_fault(default_loader(resource_root()).load(Path(args.fault_config)).data['fault'])
        else: app.store.set_scenario(args.scenario)
        print(send_at_line(app.settings.host,app.settings.ap_modem_port,'AT+CFUN=1',2))
        deadline=time.monotonic()+40
        while app.store.snapshot()['flow']['running'] and time.monotonic()<deadline: time.sleep(.05)
        state=app.store.snapshot()
        print(json.dumps({'flow':state['flow'],'diagnosis':state['diagnosis']},ensure_ascii=False,indent=2))
        return 0 if state['modem']['attachStatus']=='ATTACHED' else 1
    finally: app.stop()
