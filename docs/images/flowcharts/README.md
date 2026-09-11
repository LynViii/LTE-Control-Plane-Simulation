# 流程图索引

本目录保存项目架构、Attach、故障注入、诊断和 SRTP 的公开流程图。为降低仓库体积，GitHub 版本使用 WebP 格式。

| 文件 | 内容 |
|---|---|
| `00-system-flow-overview.webp` | 主要流程总览 |
| `01-lte-attach-11-step-state-machine.webp` | LTE Attach 11 步显式状态机 |
| `02-mib-sib-validation-branches.webp` | MIB/SIB 校验与异常分支 |
| `03-authentication-res-xres-decision.webp` | Authentication 网络侧 RES/XRES 判定 |
| `04-control-plane-timer-timeout-path.webp` | 控制面 Timer 超时路径 |
| `05-fault-injection-runtime-consumption.webp` | FaultConfig → Injector → Primitive/Socket → 消费者运行链 |
| `06-modem-four-tasks-taskbus.webp` | NAS/RRC/L2/L1 四 Task 与 TaskBus |
| `07-system-architecture-three-entities.webp` | AP、Modem、eNB/MME 三实体总体架构 |
| `08-srtp-real-validation-path.webp` | SRTP protect → UDP → verify/unprotect 验证链路 |
| `09-failure-diagnosis-closed-loop.webp` | 故障发生后的证据收集与诊断闭环 |
