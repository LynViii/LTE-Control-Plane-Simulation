# LTE 控制面系统仿真平台 v6.0.3

> **GitHub 源码仓库范围**：本仓库上传 v6.0.3 源码、测试、场景配置、构建脚本及第三方许可证；不包含本地交付的 `docs/`、`release/`、`var/`、历史验证归档和生成的源码清单。下文提到的交付文档和原交付验收结果属于完整本地交付包，不代表本次仓库重新验证结果。
>
> **开发与验证**：源码运行按下文命令进行。完整 `pytest`、`self_test.py` 及 Windows 发布目录组装包含文档检查或文档复制步骤，需要另外具备完整交付包的 `docs/`；本仓库未启用依赖这些文件的原 GitHub Actions 工作流。独立核心测试可运行 `python -m pytest -q devtools/tests/test_core.py devtools/tests/test_security_core.py devtools/tests/test_srtp_udp.py`。

v6.0.3 在 v6.0.1 已有 Blind Diagnosis、Runtime Replay、双端 Socket Hash、Stateful Network Context 和 Standalone SRTP Module 的基础上继续深化，重点解决“网络侧为什么生成 Reject”以及界面证据组织问题。当前异常链路能够显式追踪 **Context Read → Rule Evaluation → Decision → State Transition → Message Generation → Peer TX → Diagnosis**，并把期望值来源、上下文建立来源和状态变化作为 Runtime Evidence 保存。

## 主要工作区

```text
Attach | AT / Socket | Task / Trace | Security | 诊断
```

默认运行条件始终为 `NORMAL`。预设故障和自定义 FaultConfig 都作用于真实 Primitive / Socket / Timer 路径；Web 只展示后端状态和证据，不在前端决定 Attach 成败或诊断结论。

## v6.0.3 重点

- **Network Decision Pipeline 深化**：网络侧 Reject 前新增 `NETWORK_CONTEXT_READ`、`NETWORK_*_DECISION`、`NETWORK_STATE_TRANSITION`、`NETWORK_REJECT_GENERATED` 等运行事件，明确期望值来自哪个 transaction context、规则如何失败、状态如何变化以及 Reject 由哪个 Message Builder 生成。
- **Reject 生成链可追溯**：例如鉴权异常会显示 `Authentication Context.authenticationXres` 的来源、`CHALLENGE_SENT → REJECTED` 状态迁移、`NAS_AUTHENTICATION_REJECT` 生成以及随后的 `SOCKET_PEER_TX`，Diagnosis 只解释这些既有证据。
- **诊断页最终排版收口**：“相关计时器”只显示本次 transaction 实际启动/相关的计时器；关键证据链优先展示 Context/Decision/State/Message；“建议下一步”改为完整可换行文本，不再出现折行后省略号，高级调试保持独立紧凑区域。
- **系统检查生命周期修正**：切换场景、应用自定义故障或开始新 Attach 时清空上一轮 system-check 结果，避免旧检查记录被误认为当前运行状态。
- **Standalone Security Demo 交互收口**：Security 页按钮直接调用后端 `StandaloneSrtpModule` 并在页面显示/落盘证据，不再弹出额外 PowerShell/CMD；独立 `security-demo.cmd` 仅作为源码环境交叉复核入口，运行后会保存并自动打开 JSON 结果，不再单独构建第三个 Security Demo EXE。
- **Security Demo 页面重排**：独立执行入口、结果摘要和证据字段重新分组，Execution ID、三组 SHA-256、protect/unprotect、状态读取隔离和 JSON 路径按 3 列/响应式布局展示，长路径不再挤压页面。
- **保留证据隔离复算**：后端重新诊断时不提供 Scenario/FaultConfig，并排除 `FAULT_INJECTED`，生成新的 Diagnosis ID 和 Runtime Evidence SHA-256，用于证明诊断输入隔离。
- **Stateful eNB/MME Context**：RRC、Authentication、Security、Attach 的后续判定继续依赖同一 transaction 的前序消息和上下文，而不是逐消息无状态返回 JSON。
- **Standalone SRTP Module**：`StandaloneSrtpModule` 继续保持原始 RTP/SRTP bytes API，与 LTE Attach、Web、HTTP、StateStore、Diagnosis 和 FaultInjector 解耦。
- **文件与文档整理**：`docs/` 只保留现行交付/运行文档；长历史、流程图提示词和独立 Demo 补充说明移动到 `docs/reference/`；历史周报继续放在 `docs/weekly-reports/`，生成型 `SOURCE-MANIFEST.json` 不再作为工作区源码文件保留。

## 真实执行链

```text
AP --TCP--> Modem
              │
              ├─ NAS / RRC / L2 / L1 Worker
              │       ↕ TaskBus / Queue / Primitive
              │
              └--TCP--> eNB/MME Stub

FaultConfig → FaultInjector
           → Primitive / Socket / Timer
           → Runtime Event / 流程关联 ID
           → Evidence-driven Diagnosis
```

例如 `AUTH_NETWORK_REJECT` 会在真实 Socket 发送前把上行 `NAS_AUTHENTICATION_RESPONSE.res` 从 `SIMULATED_RES` 修改为 `INVALID_RES`。eNB/MME Stub 收到后依次校验 UE Context、`auth_result == SUCCESS` 与 `RES == XRES`；前两项通过、RES/XRES 失败时，会生成 `NETWORK_AUTH_DECISION`，给出 `Reject Cause = RES_MISMATCH`，并输出 `NAS_AUTHENTICATION_REJECT`。诊断页面因此能展示 `SIMULATED_RES → INVALID_RES → eNB/MME Stub 实收 INVALID_RES`，同时单列协议期望 `SIMULATED_RES`。若故障类型是 Drop，则目标消费者不收到对应对象，诊断转而展示缺失对象和真实计时器到期证据。

## Security

LTE NAS Security 与 SRTP Security Core 是两件事。Attach 页面中的 NAS Security 是控制面协商状态；`src/lte_sim/security_engine/` 中的 SRTP Core 是可以脱离 UI/HTTP/Attach 独立单测的数据包安全实现。

SRTP 协议逻辑不依赖 libsrtp/pylibsrtp。项目自己维护 RTP 解析、RFC 3711 KDF、Packet Index/ROC、Replay Window、protect/unprotect 和认证输入，`cryptography/OpenSSL` 只提供 AES/HMAC 基础密码原语。准确性采用四层验证：3 组公开 RFC known-answer vectors、11 项 Core 状态/边界检查、开发环境可选 libSRTP 差分对照、以及 9 类真实 UDP 端到端场景。NORMAL 验证最小闭环，MULTI_PACKET 验证连续状态，HEADER_VARIANTS 验证 CSRC / Header Extension / Padding。

## 运行

开发环境：

```powershell
python -m pip install -e ".[dev]"
$env:PYTHONPATH = "src"
python -m lte_sim.web_app
```

Windows EXE 构建：

```powershell
.\scripts\windows\build-exe.ps1 -Bootstrap
```

如果构建环境已经准备好，可直接：

```powershell
.\scripts\windows\build-exe.ps1
```

默认端口为 HTTP 3000、AP-Modem 5000、Modem-eNB 5001、Management 5002。LAN 使用方法见 `docs/LAN模式使用与排查.md`，EXE 说明见 `docs/Windows构建与运行.md`。

## 自检

```powershell
python -m compileall -q src devtools/tests
python -m pytest -q
node --check src/lte_sim/web/app.js
python devtools/validation/self_test.py
```

源码包由 `scripts/build/package-source.py` 生成，并在 ZIP 内生成 `packaging/SOURCE-MANIFEST.json`；解压后的项目根目录也不放 Manifest。正式交付前还应在全新目录解压最终 ZIP，再运行包内 self-test。v6.0.3 当前源码全量自动化为 **388 / 388 PASS**，self-test 额外检查 19 个前端/API 路由和 16 份现行文档的一致性。

## 文档

只需要从 `docs/README.md` 开始阅读。新手/带教统一使用 `docs/README-说明书.md`。现行技术文档均使用中文文件名；历史周报和原始任务 PDF 仅作为历史证据保存。

## 能力边界

本项目是 LTE 控制面工程仿真/调试平台，不是完整商用 3GPP 协议栈：没有真实 PHY/空口、完整 ASN.1/S1AP/EPC、多 UE、TAU/Handover 或完整 IMS/VoLTE。项目内的随机接入、Primitive 和部分消息采用工程抽象。Security Core 覆盖项目声明的 RTP AES128-CM/HMAC-SHA1-80 子集，不声称通过商用协议一致性认证。

PPT/PPTX 不在当前源码包内，本版没有修改演示文件。
