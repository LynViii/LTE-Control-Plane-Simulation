"""Human-readable control-plane metadata.

3GPP-named timers are used only where the simulator has the matching procedure
semantics.  Per-exchange watchdogs are deliberately labelled ``G_*`` so the UI
never presents engineering guards as standardized LTE timer values.
"""
from __future__ import annotations

STEP_LABELS = {
    "cfun_enable": "启用无线功能",
    "nas_attach_req": "NAS 发起 Attach",
    "mib_sib_read": "读取 MIB/SIB",
    "system_info_validate": "系统信息校验",
    "random_access": "随机接入",
    "rrc_connection": "建立 RRC 连接",
    "nas_attach_request": "发送 Attach Request",
    "authentication": "鉴权",
    "security_mode": "NAS 安全模式",
    "attach_accept": "网络接受 Attach",
    "attach_complete": "Attach 完成",
}

# UI metadata. Durations are configured by the simulator and are not claims
# about network-side production configuration.
TIMER_SPECS = {
    "T300": {
        "label": "T300 · RRC 建链等待",
        "purpose": "发送 RRC Connection Request 后等待连接建立结果",
        "kind": "3GPP procedure timer",
        "reference": "3GPP TS 36.331",
    },
    "T3410": {
        "label": "T3410 · Attach 过程等待",
        "purpose": "发送 Attach Request 后监督 Attach 响应过程",
        "kind": "3GPP procedure timer",
        "reference": "3GPP TS 24.301",
    },
    "T3460": {
        "label": "T3460 · 鉴权/安全过程监督",
        "purpose": "Authentication / Security Mode 控制过程的响应监督语义锚点",
        "kind": "3GPP procedure timer",
        "reference": "3GPP TS 24.301",
    },
    "T3450": {
        "label": "T3450 · Attach Complete 等待",
        "purpose": "Attach Accept 后监督 Attach Complete",
        "kind": "3GPP procedure timer",
        "reference": "3GPP TS 24.301",
    },
}

# The current simulator is UE-centric for some exchanges and network-stub-centric
# for others.  Generic guards make the actual implementation honest while still
# allowing a fault to expire a real timer.
_STAGE_GUARDS = {
    "mib_sib_read": ("G_SYSTEM_INFO", "广播系统信息响应保护"),
    "random_access": ("G_RANDOM_ACCESS", "随机接入响应保护"),
    "rrc_connection": ("T300", TIMER_SPECS["T300"]["purpose"]),
    "rrc_complete": ("G_RRC_COMPLETE", "RRC Setup Complete 确认保护"),
    "nas_attach_request": ("G_ATTACH_REQUEST", "Attach Request 后当前交换保护；T3410 另行监督整个 Attach 过程"),
    "authentication": ("G_AUTHENTICATION", "当前鉴权消息交换保护；T3460 为 3GPP 过程语义锚点"),
    "security_mode": ("G_SECURITY_MODE", "当前 Security Mode 消息交换保护；T3460 为 3GPP 过程语义锚点"),
    "attach_complete": ("G_ATTACH_COMPLETE", "Attach Complete 发送后的仿真 ACK 等待保护；3GPP T3450 由网络侧监督 Attach Complete"),
}


def timer_spec_for_stage(stage: str) -> dict:
    name, purpose = _STAGE_GUARDS.get(stage, (f"G_{stage.upper()}", "控制面消息等待保护"))
    meta = TIMER_SPECS.get(name, {
        "label": f"{name} · 工程保护计时器",
        "purpose": purpose,
        "kind": "engineering guard",
        "reference": "Simulator runtime",
    })
    return {"name": name, **meta, "purpose": purpose}


_STAGE_TO_FLOW_STEP = {"rrc_complete": "rrc_connection"}

def flow_step_for_stage(stage: str | None) -> str | None:
    """Map internal exchange stages back to one of the 11 user-visible flow steps."""
    if stage is None:
        return None
    return _STAGE_TO_FLOW_STEP.get(stage, stage)
