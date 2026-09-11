# 技术文档

本目录收录 LTE Control Plane Simulation 的公开技术文档。项目首页提供快速上手，本文档目录用于进一步理解架构、状态机、故障诊断、Security 和 Windows 构建。

| 文档 | 内容 |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | AP / Modem / eNB-MME 三实体、TaskBus、TCP、模块与源码结构 |
| [ATTACH_AND_DIAGNOSIS.md](ATTACH_AND_DIAGNOSIS.md) | 11 步 Attach 状态机、Fault Injection、Timer 与 Evidence-driven Diagnosis |
| [SECURITY.md](SECURITY.md) | SRTP/SRTCP、ROC、Replay Window、re-key、NAS EEA2/EIA2 与测试入口 |
| [TECHNICAL_DESIGN.md](TECHNICAL_DESIGN.md) | 系统实现范围、完整架构、运行链和发布验证的详细技术说明 |
| [WINDOWS_BUILD.md](WINDOWS_BUILD.md) | Windows Local/LAN 使用、EXE 构建、代码签名与发布检查 |
| [images/flowcharts/](images/flowcharts/) | 架构、Attach、TaskBus、Fault Injection、SRTP 与诊断流程图 |

## 流程图

![系统总体流程](images/flowcharts/00-system-flow-overview.webp)

![三实体总体架构](images/flowcharts/07-system-architecture-three-entities.webp)

![LTE Attach 11 步状态机](images/flowcharts/01-lte-attach-11-step-state-machine.webp)

> 本项目用于 LTE 控制流程的软件仿真、学习和调试，不实现真实 LTE 空口协议栈，也不用于替代商用 eNB / EPC / UE 协议实现。
