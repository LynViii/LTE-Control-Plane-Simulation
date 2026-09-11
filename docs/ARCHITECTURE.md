# 项目架构与源码结构

适用版本：v6.1.2。

## 运行结构

`SimulatorApplication` 装配状态存储、Attach 引擎、TCP 服务和 HTTP 服务。浏览器及 Windows WebView2 客户端使用同一套 HTML、CSS、JavaScript，通过 HTTP/SSE 获取后端状态。

```text
AP / AT client ── TCP ──> Modem ── TCP ──> eNB/MME Stub
                          │                  │
                     NAS/RRC/L2/L1       transaction context
                          │                  │
                       TaskBus         message checks
                          └────────┬─────────┘
                            StateStore
                                 │
                            HTTP / SSE
                                 │
                           Web / WebView2
```

Local 模式中三个实体在一台电脑上运行。LAN 模式中 Modem 位于电脑 B，主控和 eNB/MME 位于电脑 A。管理通道负责快照、配置和心跳；AT 与协议消息使用各自的 TCP 通道。

![三实体结构](images/flowcharts/07-system-architecture-three-entities.webp)

## 模块

| 位置 | 职责 |
|---|---|
| `control_plane/engine.py` | Attach 编排、工作线程处理函数、消息交换和网络侧响应 |
| `control_plane/network_context.py` | 按 transactionId 保存网络侧上下文 |
| `control_plane/specs.py` | 步骤和计时器元数据 |
| `runtime/taskbus.py` | 有界队列、工作线程及请求响应 |
| `runtime/timers.py`、`runtime/clock.py` | 计时器与时钟 |
| `fault_injection/core.py` | FaultConfig、字段目录与注入动作 |
| `diagnostics/engine.py` | 运行事件分析、复算和系统检查 |
| `state.py` | 当前状态、事件缓存、订阅通知和持久化 |
| `network.py`、`transports.py` | TCP 服务、JSON 行消息与传输适配 |
| `lan.py`、`modem_agent.py` | 远端 Agent、管理快照和连接检查 |
| `run_archive.py`、`run_repository.py` | 单次运行归档、查询和导出 |
| `security_engine/` | SRTP/SRTCP、NAS 字节处理、测试向量及 UDP 实验 |
| `http_api.py`、`web_app.py` | HTTP/SSE 路由与服务启动 |
| `embedded_app.py`、`startup_ui.py` | Windows 客户端和模式选择 |
| `web/` | 页面、样式和浏览器交互 |

## Attach 与任务通信

11 个页面步骤由 `models.py` 定义。引擎创建事务后，通过 NAS、RRC、L2、L1 的工作队列处理请求和响应。`rrc_complete` 是第 6 步内部交换，不单列一个页面步骤。

每次事务有 transactionId，每个阶段有 correlation_id。消息、计时器和诊断用这些字段关联。重置或取消会设置取消事件，后续检查点拒绝旧事务继续推进。

网络侧通过 `NetworkControlPlaneContext` 保存小区、随机接入、RRC、Authentication、Security 和 Attach 状态。后续消息的判定会读取前序消息建立的上下文。

## 故障与诊断

预设和自定义配置都使用 FaultConfig。注入位置在原语投递或 Socket 发送前，动作包括字段修改、延迟、丢弃和重复。处理结果写入运行事件。

普通诊断会使用 `FAULT_INJECTED`、校验失败、网络侧判定、Socket 和 Timer 等事件。复算模式去掉 `FAULT_INJECTED`，保留其余事件；其中仍有运行组件产生的 root_cause、rejectCause 和检查结果。这种复算用于比较输入变化后的诊断结果。

T300、T3410、T3460、T3450 在项目中表示对应过程的计时语义。`G_*` 是消息等待保护计时器，配置和启停位置见 `control_plane/specs.py` 与引擎代码。

## Security

`security_engine/` 在 v6.1.1 分成“可独立复用的媒体安全 Core”和“LTE NAS Security byte path”两条路径。`core.py` 管理 RTP/SRTP 的 KDF、Packet Index、ROC、Replay 与 protect/unprotect；`srtcp.py` 管理 31-bit SRTCP index、E-bit、authentication 与 replay；`session.py` 管理 re-key/restart 和历史 key reuse guard；`standalone.py` 提供外部项目优先使用的 raw RTP/RTCP bytes 接口。`service.py` 是 LTE 仿真适配层，`udp_lab.py` 是真实 UDP/PCAP 集成实验。

NAS 侧由 `nas_security.py` 提供 32-bit NAS COUNT、128-EEA2 AES-CTR、128-EIA2 AES-CMAC-32 和受保护 NAS PDU framing。Authentication 成功后，Security Mode Command 以 EIA2 做完整性保护但不加密；Security Mode Complete、Attach Accept、Attach Complete 使用 EEA2 + EIA2，并维护独立 UL/DL COUNT。项目模拟 K_NASenc/K_NASint 派生和 inner NAS IE codec 仍是明确简化边界。当前媒体 Profile 为 AES-128-CM/HMAC-SHA1-80、kdr=0，已支持 SRTCP 与 re-key/session lifecycle；暂不支持 MKI、DTLS-SRTP 或 AES-GCM profile。

## 目录维护

业务实现放在 `src/lte_sim/`。新功能应放进对应模块，HTTP 和页面只接收参数、调用后端及显示结果。修改 SRTP 状态处理后，应运行向量、Core 和 UDP 测试；修改取消或消息交付后，应检查超时、重置和重复消息。

`devtools/tests/`、`devtools/validation/` 是开发工具；`devtools/archive/` 是本地历史记录。Windows 构建使用 `scripts/windows/build-exe.ps1`，源码打包使用 `scripts/build/package-source.py`。传入 `--without-devtools` 可排除开发工具。

`docs/` 中只公开面向使用者和开发者的架构、状态机、Security 与构建文档；内部历史验收记录、周报、缓存、运行数据和 EXE 不纳入源码仓库。

相关资料：[状态机与故障诊断](ATTACH_AND_DIAGNOSIS.md)、[Security 实现与测试](SECURITY.md)、[详细技术设计](TECHNICAL_DESIGN.md)。

## 设计参考

早期设计参考了 OpenAirInterface、srsRAN、ns-3 LTE/EPC 和 Open5GS 的模块划分、消息组织与运行观测方式。这里的 Python 仿真保留了任务通信和流程观测的结构，协议消息采用项目自定义格式。


## v6.0.4 维护约定补充

- `src/lte_sim/scenarios/` 是 wheel 中随包安装的场景资源副本；源码根目录 `scenarios/` 仍供项目源码、PyInstaller 和人工编辑使用。`resources.scenarios_root()` 会按 frozen / installed wheel / source fallback 顺序定位。
- `devtools/validation/source_self_test.py` 面向新 clone/CI，不依赖交付文档，并包含 wheel 构建与项目外加载场景验证；`self_test.py` 面向完整交付包，会额外检查 docs、UI/API 契约与全部回归。
- v6.0.4 修复了已复现的并发和传输问题，补充了相应验证。`web/styles.css`、`web/ui.css`、`web/app.js` 和 `control_plane/engine.py` 的大规模拆分留待后续处理。
