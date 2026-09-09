"""Validated fault contracts and one injector for queue and socket paths."""
from __future__ import annotations
import copy
import math
from dataclasses import dataclass, asdict
from uuid import uuid4
from ..control_plane.specs import timer_spec_for_stage

# Response primitive, destination, request message, expected values.
CATALOG = {
 'mib_sib_read': ('BCCH_DATA_IND','RRC','READ_MIB_SIB',{'kind':'SYSTEM_INFORMATION'}),
 'random_access': ('RA_RESPONSE_IND','L2','RA_PREAMBLE',{'kind':'RANDOM_ACCESS_RESPONSE','accepted':True}),
 'rrc_connection': ('RRC_SETUP_IND','RRC','RRC_CONNECTION_REQUEST',{'kind':'RRC_CONNECTION_SETUP','srb1':True}),
 'rrc_complete': ('RRC_COMPLETE_IND','RRC','RRC_CONNECTION_SETUP_COMPLETE',{'kind':'RRC_CONNECTION_COMPLETE_ACK'}),
 'nas_attach_request': ('AUTH_REQUEST_IND','NAS','NAS_ATTACH_REQUEST',{'kind':'NAS_AUTHENTICATION_REQUEST'}),
 'authentication': ('AUTH_RESPONSE_IND','NAS','NAS_AUTHENTICATION_RESPONSE',{'kind':'NAS_SECURITY_MODE_COMMAND','auth_result':'SUCCESS'}),
 'security_mode': ('SECURITY_RESPONSE_IND','NAS','NAS_SECURITY_MODE_COMPLETE',{'kind':'NAS_ATTACH_ACCEPT'}),
 'attach_complete': ('ATTACH_COMPLETE_IND','NAS','NAS_ATTACH_COMPLETE',{'kind':'NAS_ATTACH_COMPLETE_ACK'}),
}
# Editable response-field schema used by the custom fault builder.  These are
# fields that actually exist on the current eNB/MME Stub responses, not a tiny
# set of UI presets.  Keeping the schema here means the Web UI and backend use
# the same contract and expert users can type a field path directly.
FIELDS = {
 'mib_sib_read': {
     'kind':str, 'cellId':str, 'mib':dict, 'mib.dlBandwidth':str,
     'mib.systemFrameNumber':int, 'mib.phichConfig':str, 'sib':dict,
     'sib.cellBarred':bool, 'sib.qRxLevMin':int, 'sib.plmn':str,
     'sib.trackingAreaCode':str,
 },
 'random_access': {
     'kind':str, 'accepted':bool, 'temporaryCRNTI':str, 'timingAdvance':int,
 },
 'rrc_connection': {'kind':str, 'transactionIdentifier':int, 'srb1':bool},
 'rrc_complete': {'kind':str},
 'nas_attach_request': {'kind':str, 'rand':str, 'autn':str, 'xres':str},
 'authentication': {'kind':str, 'auth_result':str, 'integrity':str, 'cipher':str},
 'security_mode': {'kind':str, 'guti':str, 'defaultBearer':int},
 'attach_complete': {'kind':str},
}

# Full response examples let the UI show a meaningful "before" value even for
# fields that are not part of the minimal state-machine contract checked by
# CATALOG.  They mirror build_enb_response() and are only explanatory; runtime
# evidence remains authoritative.
PRIMITIVE_EXAMPLES = {
 'mib_sib_read': {
     'kind':'SYSTEM_INFORMATION','cellId':'eNB-001',
     'mib':{'dlBandwidth':'20MHz','systemFrameNumber':128,'phichConfig':'normal'},
     'sib':{'cellBarred':False,'qRxLevMin':-65,'trackingAreaCode':'0001','plmn':'460-01'},
 },
 'random_access': {'kind':'RANDOM_ACCESS_RESPONSE','accepted':True,'temporaryCRNTI':'0x4A2B','timingAdvance':3},
 'rrc_connection': {'kind':'RRC_CONNECTION_SETUP','transactionIdentifier':1,'srb1':True},
 'rrc_complete': {'kind':'RRC_CONNECTION_COMPLETE_ACK'},
 'nas_attach_request': {'kind':'NAS_AUTHENTICATION_REQUEST','rand':'SIMULATED_CHALLENGE','autn':'SIMULATED_AUTN','xres':'SIMULATED_RES'},
 'authentication': {'kind':'NAS_SECURITY_MODE_COMMAND','auth_result':'SUCCESS','integrity':'EIA2','cipher':'EEA2'},
 'security_mode': {'kind':'NAS_ATTACH_ACCEPT','guti':'GUTI-46001-0001-01','defaultBearer':5},
 'attach_complete': {'kind':'NAS_ATTACH_COMPLETE_ACK'},
}

SOCKET_EXAMPLES = {
 'mib_sib_read': {'type':'READ_MIB_SIB','ueId':'UE-001'},
 'random_access': {'type':'RA_PREAMBLE','ueId':'UE-001','preambleIndex':7},
 'rrc_connection': {'type':'RRC_CONNECTION_REQUEST','ueId':'UE-001','cause':'mo-Signalling'},
 'rrc_complete': {'type':'RRC_CONNECTION_SETUP_COMPLETE','ueId':'UE-001','transactionIdentifier':1},
 'nas_attach_request': {'type':'NAS_ATTACH_REQUEST','ueId':'UE-001','attachType':'EPS_ATTACH'},
 'authentication': {'type':'NAS_AUTHENTICATION_RESPONSE','ueId':'UE-001','res':'SIMULATED_RES','auth_result':'SUCCESS'},
 'security_mode': {'type':'NAS_SECURITY_MODE_COMPLETE','ueId':'UE-001','integrity':'EIA2','cipher':'EEA2'},
 'attach_complete': {'type':'NAS_ATTACH_COMPLETE','ueId':'UE-001'},
}

SOCKET_FIELDS = {
 'mib_sib_read': {'type':str,'ueId':str},
 'random_access': {'type':str,'ueId':str,'preambleIndex':int},
 'rrc_connection': {'type':str,'ueId':str,'cause':str},
 'rrc_complete': {'type':str,'ueId':str,'transactionIdentifier':int},
 'nas_attach_request': {'type':str,'ueId':str,'attachType':str},
 'authentication': {'type':str,'ueId':str,'auth_result':str,'res':str},
 'security_mode': {'type':str,'ueId':str,'integrity':str,'cipher':str},
 'attach_complete': {'type':str,'ueId':str},
}

# Human-readable help for the expert fault editor.  This metadata describes the
# real object fields that FaultInjector can modify; it does not create a second
# UI-only fault model.
FIELD_HELP = {
    'kind': '响应消息类型；改成不符合当前步骤的类型可验证协议类型检查。',
    'cellId': '广播小区标识。',
    'mib': '完整 MIB 对象；适合结构缺失/畸形测试。',
    'mib.dlBandwidth': 'MIB 下行带宽字段。',
    'mib.systemFrameNumber': 'MIB 系统帧号，整数。',
    'mib.phichConfig': 'MIB PHICH 配置。',
    'sib': '完整 SIB 对象；置空可模拟结构缺失。',
    'sib.cellBarred': '小区是否禁止接入，布尔值。',
    'sib.qRxLevMin': '最小接收电平门限，整数。',
    'sib.plmn': '广播 PLMN。',
    'sib.trackingAreaCode': '广播 TAC。',
    'accepted': '随机接入是否被网络接受，布尔值。',
    'temporaryCRNTI': '随机接入返回的临时 C-RNTI。',
    'timingAdvance': '随机接入返回的 Timing Advance，整数。',
    'transactionIdentifier': 'RRC Transaction Identifier，整数。',
    'srb1': '是否建立 SRB1，布尔值。',
    'attachType': 'NAS Attach 类型；当前模型支持 EPS_ATTACH。',
    'rand': '网络侧 Authentication Request 的 RAND。',
    'autn': '网络侧 Authentication Request 的 AUTN。',
    'xres': '网络侧保存的期望鉴权响应 XRES。',
    'auth_result': '鉴权/安全过程的结果字段。',
    'integrity': 'NAS 完整性算法标识。',
    'cipher': 'NAS 加密算法标识。',
    'guti': 'Attach Accept 中分配的 GUTI。',
    'defaultBearer': 'Attach Accept 中的默认承载标识，整数。',
    'type': '准备通过 Socket 发送的消息类型。',
    'ueId': 'Socket 消息中的 UE 标识。',
    'preambleIndex': '随机接入 Preamble 索引，整数。',
    'cause': 'RRC Connection Request 的建立原因。',
    'res': 'UE 上报给网络侧的鉴权响应 RES；网络侧会与 XRES 比较。',
}
SOCKET_EXPECTED = {stage: dict(values) for stage, values in SOCKET_EXAMPLES.items()}

FIELD_SUGGESTIONS = {
    "mib_sib_read": {"kind":"INVALID_KIND","cellId":"eNB-999","mib.dlBandwidth":"5MHz","mib.systemFrameNumber":999,"mib.phichConfig":"invalid","sib.cellBarred":True,"sib.qRxLevMin":-120,"sib.plmn":"001-01","sib.trackingAreaCode":"00FF"},
    "random_access": {"kind":"RANDOM_ACCESS_REJECT","accepted":False,"temporaryCRNTI":"0xFFFF","timingAdvance":99},
    "rrc_connection": {"kind":"RRC_REJECT","transactionIdentifier":7,"srb1":False},
    "rrc_complete": {"kind":"INVALID_ACK"},
    "nas_attach_request": {"kind":"INVALID_AUTH_REQUEST","rand":"BAD_RAND","autn":"BAD_AUTN","xres":"BAD_XRES"},
    "authentication": {"kind":"NAS_AUTHENTICATION_REJECT","auth_result":"REJECT","integrity":"EIA0","cipher":"EEA0"},
    "security_mode": {"kind":"SECURITY_REJECT","guti":"INVALID_GUTI","defaultBearer":99},
    "attach_complete": {"kind":"INVALID_ACK"},
}
SOCKET_SUGGESTIONS = {
    stage: {field: ("INVALID_MESSAGE_TYPE" if field == "type" else None) for field in fields}
    for stage, fields in SOCKET_FIELDS.items()
}
SOCKET_SUGGESTIONS['mib_sib_read'].update({'ueId':'UE-999'})
SOCKET_SUGGESTIONS['random_access'].update({'ueId':'UE-999','preambleIndex':99})
SOCKET_SUGGESTIONS['rrc_connection'].update({'ueId':'UE-999','cause':'unsupported'})
SOCKET_SUGGESTIONS['rrc_complete'].update({'ueId':'UE-999','transactionIdentifier':7})
SOCKET_SUGGESTIONS['nas_attach_request'].update({'ueId':'UE-999','attachType':'UNSUPPORTED_ATTACH'})
SOCKET_SUGGESTIONS['authentication'].update({'ueId':'UE-999','auth_result':'REJECT','res':'INVALID_RES'})
SOCKET_SUGGESTIONS['security_mode'].update({'ueId':'UE-999','integrity':'EIA0','cipher':'EEA0'})
SOCKET_SUGGESTIONS['attach_complete'].update({'ueId':'UE-999'})

TYPES = {'MODIFY_FIELD','DELAY','DROP','DUPLICATE','TIMER_TIMEOUT','SOCKET_DELAY','SOCKET_DROP'}

STAGE_LABELS = {
 'mib_sib_read': '读取 MIB/SIB',
 'random_access': '随机接入',
 'rrc_connection': '建立 RRC 连接',
 'rrc_complete': 'RRC Setup Complete',
 'nas_attach_request': '发送 Attach Request',
 'authentication': '鉴权',
 'security_mode': 'NAS 安全模式',
 'attach_complete': 'Attach Complete',
}
FAULT_LABELS = {
 'MODIFY_FIELD': '修改字段', 'DELAY': '延迟原语', 'DROP': '丢弃原语',
 'DUPLICATE': '重复原语', 'TIMER_TIMEOUT': '触发等待超时',
 'SOCKET_DELAY': '延迟 Socket 消息', 'SOCKET_DROP': '丢弃 Socket 消息',
}

FAULT_MECHANISMS = {
    ("primitive", "MODIFY_FIELD"): ("PRIMITIVE_PARAMETER_OVERRIDE", "在目标 Task 消费原语前直接修改原语字段，目标 Worker 消费到的就是修改后的参数。"),
    ("primitive", "DROP"): ("PRIMITIVE_DELIVERY_SUPPRESSED", "抑制目标原语交付，目标 Task 不会消费该原语，等待保护计时器随后实际到期。"),
    ("primitive", "TIMER_TIMEOUT"): ("PRIMITIVE_RESPONSE_WITHHELD", "故意不交付响应原语，让对应等待保护计时器真实走到 EXPIRED。"),
    ("primitive", "DELAY"): ("PRIMITIVE_DELIVERY_DELAYED", "在原语交付前加入真实延迟，延迟超过等待上限时由实际计时器判定超时。"),
    ("primitive", "DUPLICATE"): ("PRIMITIVE_DELIVERY_DUPLICATED", "将同一原语真实交付两次，由目标 Worker/状态机发现重复输入。"),
    ("socket", "MODIFY_FIELD"): ("SOCKET_MESSAGE_PARAMETER_OVERRIDE", "在真实 TCP Socket 发送前修改消息字段，对端 eNB/MME Stub 收到的就是修改后的 wire value。"),
    ("socket", "SOCKET_DROP"): ("SOCKET_SEND_SUPPRESSED", "在实际 Socket request() 调用前抑制发送，对端不会收到该消息。"),
    ("socket", "SOCKET_DELAY"): ("SOCKET_SEND_DELAYED", "在实际 Socket request() 调用前加入真实延迟，并由运行时记录延迟/超时证据。"),
}

@dataclass(frozen=True)
class FaultConfig:
    enabled: bool = False
    stage: str = 'authentication'
    task: str = 'NAS'
    primitive: str = 'AUTH_RESPONSE_IND'
    fault_type: str = 'MODIFY_FIELD'
    field: str = 'auth_result'
    value: object = 'REJECT'
    delay_ms: int = 0
    timeout_ms: int = 3000
    layer: str = 'primitive'
    fault_id: str = ''
    @classmethod
    def parse(cls, data):
        if not isinstance(data, dict): raise ValueError('FaultConfig must be an object')
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown: raise ValueError('Unknown FaultConfig fields: ' + ', '.join(sorted(unknown)))
        obj = cls(**data)
        for key in ('stage','task','primitive','fault_type','field','layer','fault_id'):
            if type(getattr(obj,key)) is not str: raise ValueError(f'{key} must be a string')
        if type(obj.enabled) is not bool: raise ValueError('enabled must be boolean')
        if obj.stage not in CATALOG: raise ValueError('Unsupported stage')
        primitive, task, message, _ = CATALOG[obj.stage]
        if obj.task != task: raise ValueError('Task does not match selected stage')
        if obj.layer not in {'primitive','socket'}: raise ValueError('Invalid fault layer')
        if obj.primitive != (message if obj.layer == 'socket' else primitive): raise ValueError('Primitive/message does not match stage/layer')
        if obj.fault_type not in TYPES: raise ValueError('Unsupported fault type')
        if obj.fault_type.startswith('SOCKET_') and obj.layer != 'socket': raise ValueError('Socket fault requires socket layer')
        if obj.layer == 'socket' and obj.fault_type not in {'MODIFY_FIELD','SOCKET_DELAY','SOCKET_DROP'}: raise ValueError('Unsupported socket operation')
        for key, limit in [('delay_ms',10000),('timeout_ms',4000)]:
            n=getattr(obj,key)
            if type(n) is not int or not 0 <= n <= limit: raise ValueError(f'{key} out of range')
        if obj.timeout_ms < 50: raise ValueError('timeout_ms must be 50..4000')
        if obj.fault_type in {'DELAY','SOCKET_DELAY'} and obj.delay_ms < 1: raise ValueError('Delay must be positive')
        if obj.fault_type == 'MODIFY_FIELD':
            expected_type = (SOCKET_FIELDS[obj.stage] if obj.layer == 'socket' else FIELDS[obj.stage]).get(obj.field)
            if expected_type is None:
                supported = ', '.join((SOCKET_FIELDS[obj.stage] if obj.layer == 'socket' else FIELDS[obj.stage]).keys())
                raise ValueError('该字段不属于当前消息；可修改的真实字段：' + supported)
            if obj.value is not None and type(obj.value) is not expected_type: raise ValueError('字段值类型不匹配；数字/布尔值请分别使用 42 / true / false')
            if isinstance(obj.value,str) and len(obj.value)>160: raise ValueError('Fault value too long')
        if len(obj.fault_id)>64: raise ValueError('Fault ID too long')
        return obj
    def to_dict(self): return asdict(self)

def template(stage='authentication', fault_type='MODIFY_FIELD', field='auth_result', value='REJECT', layer='primitive'):
    primitive, task, message, _ = CATALOG[stage]
    return FaultConfig.parse(dict(enabled=True,stage=stage,task=task,primitive=message if layer=='socket' else primitive,
                                  fault_type=fault_type,field=field,value=value,layer=layer)).to_dict()

PRESETS = {
 'NORMAL': FaultConfig().to_dict(),
 # Visible engineering presets: change an input that the simulated network or UE
 # must actually consume, then let its policy/state-machine determine the result.
 'CELL_BARRED': template('mib_sib_read',field='sib.cellBarred',value=True),
 'RA_PREAMBLE_INVALID': template('random_access',field='preambleIndex',value=99,layer='socket'),
 'RRC_CAUSE_UNSUPPORTED': template('rrc_connection',field='cause',value='unsupported',layer='socket'),
 'ATTACH_UE_UNKNOWN': template('nas_attach_request',field='ueId',value='UE-999',layer='socket'),
 'AUTH_NETWORK_REJECT': template(layer='socket', field='res', value='INVALID_RES'),
 'SECURITY_ALGORITHM_MISMATCH': template('security_mode',field='integrity',value='EIA0',layer='socket'),
 'RRC_TRANSACTION_MISMATCH': template('rrc_complete',field='transactionIdentifier',value=99,layer='socket'),
 'ATTACH_TYPE_UNSUPPORTED': template('nas_attach_request',field='attachType',value='EMERGENCY_ATTACH',layer='socket'),
 'SECURITY_CIPHER_MISMATCH': template('security_mode',field='cipher',value='EEA0',layer='socket'),
 'ATTACH_COMPLETE_UE_UNKNOWN': template('attach_complete',field='ueId',value='UE-999',layer='socket'),
 'RRC_RESPONSE_TIMEOUT': template('rrc_connection','TIMER_TIMEOUT'),
 'SOCKET_MESSAGE_DROP': template('mib_sib_read', fault_type='SOCKET_DROP',layer='socket'),
 # Compatibility / expert presets retained for archived runs and direct API use.
 'AUTH_PARAMETER_INVALID': template(),
 'AUTH_RESPONSE_TIMEOUT': template(fault_type='DROP'),
 'AUTH_REJECT': template(layer='socket', field='res', value='INVALID_RES'),
 'PLMN_MISMATCH': template('mib_sib_read',field='sib.plmn',value='001-01'),
 'TAC_MISMATCH': template('mib_sib_read',field='sib.trackingAreaCode',value='00FF'),
 'RA_REJECT': template('random_access',field='accepted',value=False),
 'RRC_REJECT': template('rrc_connection',field='kind',value='RRC_REJECT'),
 'SECURITY_REJECT': template('security_mode',field='kind',value='SECURITY_REJECT'),
 'SYSTEM_INFO_MALFORMED': template('mib_sib_read',field='sib',value=None),
 'ENB_TIMEOUT': template('mib_sib_read','SOCKET_DROP',layer='socket'),
}

class FaultInjector:
    def __init__(self, config, emit):
        self.config = FaultConfig.parse(config)
        self.emit = emit
        self.fired = False
    def intercept(self, value, *, layer, stage, primitive, correlation_id, transaction_id):
        before, after = copy.deepcopy(value), copy.deepcopy(value)
        cfg = self.config
        match = cfg.enabled and not self.fired and (cfg.layer,cfg.stage,cfg.primitive)==(layer,stage,primitive)
        evidence = None
        delay, copies = 0, 1
        if match:
            self.fired=True
            old = new = None
            if cfg.fault_type == 'MODIFY_FIELD':
                node=after
                parts=cfg.field.split('.')
                for part in parts[:-1]: node=node[part]
                old=copy.deepcopy(node.get(parts[-1]))
                node[parts[-1]]=copy.deepcopy(cfg.value)
                new=copy.deepcopy(cfg.value)
            elif cfg.fault_type in {'DROP','SOCKET_DROP','TIMER_TIMEOUT'}: copies=0
            elif cfg.fault_type in {'DELAY','SOCKET_DELAY'}: delay=cfg.delay_ms/1000
            elif cfg.fault_type == 'DUPLICATE': copies=2
            timer_meta = timer_spec_for_stage(stage)
            mechanism_code, mechanism_description = FAULT_MECHANISMS.get(
                (cfg.layer, cfg.fault_type),
                ("FAULT_INJECTION", "通过统一 FaultInjector 修改真实运行路径。"),
            )
            evidence=dict(
                          fault_id=cfg.fault_id or uuid4().hex[:12],
                          fault_type=cfg.fault_type, fault_label=FAULT_LABELS.get(cfg.fault_type,cfg.fault_type),
                          mechanism=mechanism_code, mechanism_description=mechanism_description,
                          target_step=stage, target_step_label=STAGE_LABELS.get(stage,stage),
                          injection_point='SOCKET_TX' if layer=='socket' else 'PRIMITIVE_DELIVERY',
                          source_task='L1 / Modem' if layer=='socket' else 'eNB/MME 响应适配层',
                          target_task='eNB/MME Stub' if layer=='socket' else cfg.task, configured_task=cfg.task,
                          primitive=primitive, correlation_id=correlation_id,
                          transactionId=transaction_id, layer=layer,
                          field=cfg.field if cfg.fault_type=='MODIFY_FIELD' else None,
                          before=old if cfg.fault_type=='MODIFY_FIELD' else before,
                          after=new if cfg.fault_type=='MODIFY_FIELD' else (None if copies==0 else after),
                          expected=old if cfg.fault_type=='MODIFY_FIELD' else before,
                          actual=new if cfg.fault_type=='MODIFY_FIELD' else (None if copies==0 else after),
                          original_parameters=before, after_parameters=after,
                          delay_ms=round(delay*1000), copies=copies,
                          related_timer=timer_meta['name'], timer_label=timer_meta['label'],
                          timer_kind=timer_meta['kind'], timer_limit=cfg.timeout_ms,
                          elapsed=None, final_effect='PENDING', root_cause=None)
            self.emit(evidence)
        return after, delay, copies, evidence
