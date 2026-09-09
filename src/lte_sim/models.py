from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event
from time import monotonic
from uuid import uuid4


FLOW_STEPS = [
    {"key": "cfun_enable", "name": "启用无线功能", "detail": "AP 发送 AT+CFUN=1"},
    {"key": "nas_attach_req", "name": "NAS 发起 Attach", "detail": "NAS_ATTACH_REQ"},
    {"key": "mib_sib_read", "name": "读取 MIB/SIB", "detail": "RRC/L1 获取广播系统信息"},
    {"key": "system_info_validate", "name": "系统信息校验", "detail": "校验 Cell Barred、PLMN、TAC"},
    {"key": "random_access", "name": "随机接入", "detail": "RA Preamble / Random Access Response"},
    {"key": "rrc_connection", "name": "建立 RRC 连接", "detail": "Request / Setup / SetupComplete"},
    {"key": "nas_attach_request", "name": "发送 Attach Request", "detail": "NAS 注册请求进入 EPC"},
    {"key": "authentication", "name": "鉴权", "detail": "Authentication Request / Response"},
    {"key": "security_mode", "name": "安全模式", "detail": "Security Mode Command / Complete"},
    {"key": "attach_accept", "name": "网络接受 Attach", "detail": "Attach Accept"},
    {"key": "attach_complete", "name": "Attach 完成", "detail": "Attach Complete → ATTACHED"},
]

SCENARIOS = {
    "NORMAL": {"name": "正常网络", "description": "作为基线场景运行完整 Attach 流程，用于和异常场景做对照。"},
    "CELL_BARRED": {"name": "系统信息 · 小区禁止接入", "description": "系统信息广播存在接入限制，运行后结合 Trace / Diagnosis 定位具体限制项与失败原因。"},
    "RA_PREAMBLE_INVALID": {"name": "随机接入 · Preamble 超出范围", "description": "随机接入参数被扰动，需在运行后查看网络侧判定与计时器/响应证据。"},
    "RRC_CAUSE_UNSUPPORTED": {"name": "RRC · 建链原因不受支持", "description": "RRC 建链输入与网络侧准入策略存在偏差，需运行后再定位具体拒绝原因。"},
    "ATTACH_UE_UNKNOWN": {"name": "NAS · UE Context 不存在", "description": "NAS 注册阶段引入 UE 上下文相关异常，运行后可查看网络侧上下文判定链。"},
    "AUTH_NETWORK_REJECT": {"name": "鉴权 · RES/XRES 不一致", "description": "鉴权阶段存在网络侧校验异常，运行后查看 RES / XRES 与上下文判定证据。"},
    "SECURITY_ALGORITHM_MISMATCH": {"name": "Security · 完整性算法不一致", "description": "安全模式协商与网络安全策略存在不一致，运行后定位具体算法判定。"},
    "RRC_TRANSACTION_MISMATCH": {"name": "RRC · Transaction ID 不匹配", "description": "RRC 事务关联存在异常，运行后通过 Trace / Diagnosis 确认事务与响应对应关系。"},
    "ATTACH_TYPE_UNSUPPORTED": {"name": "NAS · Attach Type 不支持", "description": "NAS 接入参数与网络策略存在偏差，需运行后定位具体策略检查结果。"},
    "SECURITY_CIPHER_MISMATCH": {"name": "Security · 加密算法不一致", "description": "安全模式中的加密协商存在异常，需在运行后查看网络策略与实际上报值。"},
    "ATTACH_COMPLETE_UE_UNKNOWN": {"name": "NAS · Attach Complete UE Context 丢失", "description": "流程尾段存在上下文一致性异常，运行后结合诊断确认根因。"},
    "RRC_RESPONSE_TIMEOUT": {"name": "RRC · 建链等待超时", "description": "该场景重点观察等待/超时链路，运行后可查看计时器、交付证据与失败闭环。"},
    "SOCKET_MESSAGE_DROP": {"name": "Socket · 系统信息请求丢失", "description": "该场景重点观察 Socket 交付链路，运行后再查看发送/接收与超时证据。"},
    "AUTH_PARAMETER_INVALID": {"name": "鉴权 · 原语参数异常", "description": "同一网络响应在进入 Modem 内部处理链后被扰动，适合观察 Primitive 消费与根因诊断。"},
    "AUTH_RESPONSE_TIMEOUT": {"name": "鉴权 · 响应原语丢失", "description": "该场景重点观察鉴权等待链和超时证据，运行后定位缺失对象。"},
    # 兼容旧 API / 历史记录；当前快捷下拉只暴露上面的工程定位案例。
    "PLMN_MISMATCH": {"name": "系统信息 · PLMN 不匹配", "description": "系统信息广播参数存在网络选择相关异常，运行后查看 RRC 校验与诊断结论。"},
    "TAC_MISMATCH": {"name": "系统信息 · TAC 不匹配", "description": "系统信息广播参数存在位置区相关异常，运行后查看 RRC 校验与诊断结论。"},
    "RA_REJECT": {"name": "随机接入 · 响应拒绝", "description": "随机接入响应链路存在异常，运行后可结合 Task / Trace 观察真实消费结果。"},
    "RRC_REJECT": {"name": "RRC · Setup 响应异常", "description": "RRC 建链响应链路存在异常，运行后再查看消费者实收值与诊断。"},
    "AUTH_REJECT": {"name": "鉴权 · 网络明确拒绝（兼容名）", "description": "兼容旧场景名，底层仍转换为统一 FaultConfig。"},
    "SECURITY_REJECT": {"name": "NAS 安全模式 · 响应异常", "description": "安全模式响应链路存在异常，运行后再查看网络侧输出与诊断。"},
    "SYSTEM_INFO_MALFORMED": {"name": "系统信息 · SIB 结构缺失", "description": "系统信息结构被扰动，适合观察参数校验、Primitive 证据与失败定位。"},
    "ENB_TIMEOUT": {"name": "Socket · 系统信息消息丢失", "description": "兼容旧场景名；该场景用于观察系统信息获取链路的传输异常。"},
    "CUSTOM": {"name": "自定义故障", "description": "仅在用户明确“应用并启用”后生效；由同一 FaultInjector 执行。"},
}

from .fault_injection.core import PRESETS
for _name in PRESETS:
    SCENARIOS.setdefault(_name, {"name": _name, "description": "统一 FaultConfig 快捷模板"})

@dataclass
class AttachContext:
    transaction_id: str = field(default_factory=lambda: uuid4().hex[:12])
    cancel_event: Event = field(default_factory=Event)
    started_monotonic: float = field(default_factory=monotonic)
    scenario: str = "NORMAL"
    custom_fault: dict = field(default_factory=dict)
    step_started_monotonic: dict[str, float] = field(default_factory=dict)

    injector: object = field(default=None, repr=False)
    correlation_id: str = ""
    response_seen: set = field(default_factory=set)
    operation_stop: Event = field(default_factory=Event, repr=False)

    def cancel(self) -> None:
        self.cancel_event.set()

    @property
    def cancelled(self) -> bool:
        return self.cancel_event.is_set()
