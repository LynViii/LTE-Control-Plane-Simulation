# LTE Control Plane Simulation

[![CI](https://github.com/LiYuansheng0209/LTE-Control-Plane-Simulation/actions/workflows/ci.yml/badge.svg)](https://github.com/LiYuansheng0209/LTE-Control-Plane-Simulation/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Version](https://img.shields.io/badge/version-6.1.2-green)

一个面向 LTE Attach 控制流程学习、调试与故障分析的工程化仿真平台。项目使用 Python 模拟 AP、Modem 与 eNB/MME 之间的控制面交互，将 NAS、RRC、L2、L1 四个 Task、TCP 通信、计时器、故障注入、运行证据诊断以及 Security 模块串成完整运行链。

> 当前版本：**v6.1.2**  
> 项目使用简化 JSON 消息与网络侧模型，不需要真实基站、射频设备或 USIM，适合控制流程实验与软件联调。

## 项目展示

![LTE Control Plane Simulator Main UI](assets/screenshots/main-ui.jpg)

主界面集中展示运行条件、Attach 控制、当前状态、11 步进度、Serving Cell、本次会话与系统拓扑；下方可切换 `Attach`、`AT / Socket`、`Task / Trace`、`Security` 和诊断工作区。AP–Modem 与 Modem–eNB/MME 的协议消息由后端 TCP 链路实际传递，页面主要负责控制、观察和故障分析。

## 核心能力

- **11 步 LTE Attach 状态机**：从 `CFUN`、系统信息、随机接入、RRC 建链，到 Authentication、Security Mode、Attach Accept 和 Attach Complete。
- **多 Task Modem 模型**：NAS / RRC / L2 / L1 使用独立工作线程，通过队列和 TaskBus 传递原语、关联 ID 和回复。
- **真实 TCP 控制消息链路**：AP–Modem 与 Modem–eNB/MME 通过 TCP 通信，而不是仅在前端切换状态。
- **Fault Injection**：支持字段修改、延迟、丢弃、重复和超时等动作，并作用到实际运行链路。
- **网络侧判定**：eNB/MME 保存 UE、鉴权和安全上下文，并根据当前事务状态和消息内容决定继续、Reject 或超时。
- **Evidence-driven Diagnosis**：记录原语、消费者实收、TCP 收发、计时器、状态迁移与网络判定；支持运行链回放和证据隔离复算。
- **NAS Security**：使用 32-bit COUNT、128-EEA2 AES-CTR 与 128-EIA2 AES-CMAC-32 对 Attach 中关键 NAS 消息进行字节级保护。
- **SRTP / SRTCP Security Core**：支持 AES-128-CM / HMAC-SHA1-80、ROC、Replay Window、SRTCP 31-bit index、re-key 与 restart。
- **Local / LAN 两种部署模式**：既可单机运行，也可让远端 Modem Agent 与 Controller 通过局域网协作。
- **Web UI + Windows WebView2 Client**：浏览状态、消息、Task / Trace、Security 和诊断结果。

## 快速开始

需要 Python 3.10 或以上版本。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m lte_sim.web_app
```

浏览器打开：

```text
http://127.0.0.1:3000
```

保持“正常网络”，点击“开始 Attach”。完整流程成功后应显示：

```text
11 / 11
ATTACHED
```

Linux / macOS 使用 `.venv/bin/python`，其余参数相同。

## Attach 流程

```text
开启无线 → NAS 发起 Attach → 读取并校验 MIB/SIB
        → 随机接入 → RRC 建链 → 发送 Attach Request
        → Authentication → Security Mode
        → Attach Accept → Attach Complete
```

正常完成后进入 `ATTACHED`；任一步失败会记录 `FAILED` 和 `failedStep`；执行 `CFUN=0` 或 Reset 后回到 `DETACHED`。

## 运行链与诊断

一次 Attach 中，关键事件都会携带关联 ID 写入运行记录：

```text
原语投递
  ↓
消费者实收
  ↓
TCP 发送 / 接收
  ↓
网络上下文读取与协议判定
  ↓
状态迁移 / Reject / Timeout
  ↓
Diagnosis
```

普通诊断直接分析本次运行证据；“证据隔离复算”会排除场景名称、`FaultConfig` 和 `FAULT_INJECTED` 事件，只使用消费者实收、TCP 收发、计时器、状态迁移和网络判定重新计算根因。证据不足时返回 `INSUFFICIENT_EVIDENCE`。

## Security Core

`src/lte_sim/security_engine/` 提供独立 RTP / RTCP 字节接口。

SRTP / SRTCP 支持：

- AES-128-CM / HMAC-SHA1-80
- `kdr=0`
- RTP Sequence + ROC → Packet Index
- SRTCP 31-bit index + E-bit
- 128-packet Replay Window
- protect / unprotect
- re-key
- session restart
- UDP Lab 真实 Socket 验证

独立运行：

```powershell
.\.venv\Scripts\python.exe -m lte_sim.security_engine.cli self-test
.\.venv\Scripts\python.exe -m lte_sim.security_engine.cli demo
```

外部程序可直接调用：

```python
from lte_sim.security_engine import StandaloneSrtpModule
```

Attach 内 NAS Security 则在 Authentication 通过后建立安全上下文，并对 Security Mode、Attach Accept 和 Attach Complete 等关键消息执行 EEA2 / EIA2 保护。

> 当前未实现 AES-GCM、MKI 和 DTLS-SRTP。

## 项目结构

| 路径 | 内容 |
|---|---|
| `src/lte_sim/control_plane/` | Attach 编排、网络上下文和消息判定 |
| `src/lte_sim/runtime/` | TaskBus、工作线程、队列、计时器和 Trace |
| `src/lte_sim/fault_injection/` | FaultConfig、字段目录和注入动作 |
| `src/lte_sim/diagnostics/` | 运行事件分析与诊断 |
| `src/lte_sim/security_engine/` | NAS Security、SRTP/SRTCP、Session、UDP Lab |
| `src/lte_sim/web/` | Web / Windows Client 共用页面 |
| `scenarios/` | YAML 场景和 Schema |
| `devtools/` | 测试与交付验证工具 |
| `scripts/` | 构建、运行和安全 Demo 脚本 |
| `packaging/` | Windows 打包资源 |
| `LICENSES/` | 第三方依赖许可证 |

## 默认端口

| 用途 | TCP 端口 |
|---|---:|
| Web 页面 | 3000 |
| AP → Modem | 5000 |
| Modem → eNB/MME | 5001 |
| LAN 管理通道 | 5002 |

端口和数据目录可通过环境变量配置，具体见 [`src/lte_sim/config.py`](src/lte_sim/config.py)。源码运行生成的数据默认保存在 `var/`。

## 测试与 CI

仓库的 GitHub Actions 会在 push / pull request 时执行源码验证：

```powershell
.\.venv\Scripts\python.exe devtools/validation/source_self_test.py
```

该检查包括：

1. Python `compileall`
2. JavaScript 语法检查
3. 核心 pytest 测试
4. Wheel 构建
5. 隔离目录安装与包内资源验证

准备正式交付包时，可执行更严格的完整检查：

```powershell
.\.venv\Scripts\python.exe devtools/validation/self_test.py
```

v6.1.2 在 Windows 环境已完成全量复测：**432 项通过**；源码测试 **163 项通过**；Wheel 构建与隔离安装通过。

## Windows / LAN

Windows Client 使用 WebView2 打开同一套前端页面。

- **Local**：AP、Modem、eNB/MME 在同一台电脑运行。
- **LAN**：Controller 运行 AP / Web / eNB/MME，另一台电脑运行 Modem Agent。

两种模式共用 Attach 引擎、TaskBus、故障注入、运行证据和诊断逻辑。协议通道传输控制面消息；管理通道用于状态同步、心跳和远端控制。

Windows 构建入口：

```powershell
scripts/windows/build-exe.ps1 -Bootstrap
```

## 说明

本项目用于 LTE 控制流程的软件仿真、学习和调试，不实现真实 LTE 空口协议栈，也不用于替代商用 eNB / EPC / UE 协议实现。

第三方许可证见 [`LICENSES/README.md`](LICENSES/README.md)。
