# v6.1.2 Security Core

## 1. 模块概览

Security 包含媒体和 NAS 两个模块：

1. **媒体侧 Security Core**：SRTP AES-128-CM/HMAC-SHA1-80 + SRTCP + Replay/ROC + Session Lifecycle/Re-key；
2. **LTE NAS Security 实验**：Security Mode 协商实际连接到 32-bit NAS COUNT、128-EEA2 Ciphering、128-EIA2 Integrity 与保护后的 NAS PDU bytes。

媒体模块处理 RTP/RTCP，NAS 模块处理 Attach 中的受保护消息。两部分分别维护消息格式、计数器和密钥。当前鉴权和 NAS 内层字段采用项目模型，详见第 6 节。

## 2. 源码分层与外部复用

正式实现集中在：

```text
src/lte_sim/security_engine/
├─ core.py        # RTP/SRTP：KDF、Packet Index、ROC、Replay、protect/unprotect
├─ srtcp.py       # RTCP/SRTCP：31-bit index、E-bit、authentication、replay
├─ session.py     # Session lifecycle、re-key/restart、key reuse guard
├─ nas_security.py# 128-EEA2/128-EIA2、32-bit NAS COUNT、受保护 NAS PDU
├─ standalone.py  # 外部项目优先使用的 raw RTP/RTCP bytes SDK 风格接口
├─ service.py     # LTE 仿真平台适配层、Core self-test、NAS UE-side context
├─ vectors.py     # RFC 3711 / RFC 2202 标准向量
├─ udp_lab.py     # UDP 集成实验与 PCAP，不属于最小 SDK 核心
├─ cli.py         # 命令行入口
└─ errors.py      # 统一 Security 错误码
```

其他 Python 项目若只需要 SRTP/SRTCP，可直接安装本项目并使用：

```python
from lte_sim.security_engine import StandaloneSrtpModule

with StandaloneSrtpModule(master_key_and_salt) as security:
    srtp = security.protect_rtp(raw_rtp)
    rtp = security.unprotect_srtp(srtp)
    srtcp = security.protect_rtcp(raw_rtcp)
    rtcp = security.unprotect_srtcp(srtcp)
```

`StandaloneSrtpModule` 不导入 Attach、Web、HTTP、StateStore、FaultInjector 或 UDP Lab。`service.py` 是当前 LTE 仿真平台的适配服务，`udp_lab.py` 是集成验证工具；二者不应被误认为外部项目最小依赖。

## 3. SRTP

当前 SRTP Profile 为 **AES-128-CM/HMAC-SHA1-80，kdr=0，无 MKI**。项目代码自己维护 RTP parse/serialize、RFC 3711 Key Derivation、Packet Index、Sequence/ROC、128-packet Replay Window、AES-CM IV/Input、HMAC authentication input 与 80-bit tag。`cryptography/OpenSSL` 只提供 AES/HMAC 等密码原语。

v6.1.1 对已有实现增加以下可靠性约束：

- UDP 场景的最终 PASS 不再只看 accepted/rejected 数量；每个成功包都必须满足 wire bytes、一致的原始 RTP、恢复 RTP 与应用 payload，拒绝场景还必须匹配预期错误码；
- `SecurityContext` 外层使用会话级 `RLock`，Sequence 分配、protect 和计数更新在同一临界区完成，避免两个并发请求拿到同一序号；
- `unprotect()` 在 Core 提交 Replay 状态前先核对外部 sequence/timestamp/SSRC 和完整 packet bytes，metadata 错误不会消耗合法包的 Replay 状态；
- 篡改、认证失败、错误 Key 等失败路径不会错误推进 Replay/ROC；
- 多 SSRC、乱序、Sequence rollover、Replay Window 边界、RTP CSRC/Header Extension/Padding 等继续作为状态组合测试。

### 3.1 libSRTP 可选差分对照

`pylibsrtp/libSRTP` 是可选测试依赖。安装后，`run_optional_reference_crosscheck()` 提供六组对照：SRTP 的 `singlePacket`、`headerVariant`、`multiSsrc`、`rollover`，以及 SRTCP 的 `srtcpReceiverReport`、`srtcpCompound`。各组比较报文字节，并检查双方能否解密对方的报文。绑定未提供 RTCP 接口时，SRTCP 组返回 `UNSUPPORTED_BY_BINDING`；未安装参考库时返回 `NOT_INSTALLED`。

### 3.2 v6.1.2 SRTCP 参考索引对齐

SRTCP 发送端首包使用 `index=0`。参考对照先读取 libSRTP 报文中的索引，再将独立测试会话推进到相同索引，比较完整报文并执行双向解密。结果中的 `projectNativeInitialIndex` 和 `referenceNativeInitialIndex` 保留双方原始首包索引；`alignedComparisonIndex`、`byteEqualAtAlignedIndex` 和 `nativeInitialIndexEqual` 说明对齐及比较结果。对照测试不修改正在使用的业务会话。

## 4. SRTCP

`srtcp.py` 提供以下 SRTCP 功能：

- 31-bit SRTCP index；
- E-bit；
- AES-128-CM payload encryption；
- HMAC-SHA1-80 authentication；
- 128-packet Replay Window；
- 多 SSRC 独立 index/replay state；
- RTCP Receiver Report / Sender Report 与 Compound RTCP 基本结构解析；
- authentication/replay 失败后状态不提交；
- re-key 后保留 SRTCP index/replay state。

SRTCP 与 SRTP 共用会话换钥管理，各自保存包索引和重放状态。解析器检查 RTCP 版本、组合包各成员的长度和常见类型的最小正文长度。Padding 只能出现在最后一个成员，长度须合法；类型检查使用 `logical_len = packet_len - pad_count`，防止填充字节掩盖正文不足。其他 RTCP 类型字段和扩展格式尚未全部覆盖。

SRTCP 固定回归用例覆盖 E-bit=1、E-bit=0 和组合 RTCP。这些期望字节由项目保存，用于检查实现变化，不属于 RFC 3711 发布的已知答案向量。参考实现对照另行执行。

## 5. Session Lifecycle 与 Re-key

`session.py` 显式区分两种操作：

- **re-key**：更换新 master key+salt，同时保留 SRTP ROC/Replay 与 SRTCP index/Replay；`generation` 和 `rekeyCount` 推进；
- **restart / session recreation**：重新创建 packet state，Packet Index 从新会话状态开始，因此默认禁止复用当前或历史上已经用过的 master key+salt。

`SessionLifecycle` 保存当前对象使用过的全部密钥指纹，拒绝重复换钥或使用旧密钥重建会话，错误码为 `REKEY_KEY_REUSE` 或 `KEY_STREAM_REUSE_RISK`。界面的 `previousKeyFingerprints` 只显示最近 8 条，内部 `_used_fingerprints` 保留完整记录。

防复用记录属于当前 `SessionLifecycle` 对象。跨进程（cross-process）或重建对象后，需要由上层密钥管理保存使用历史，并分配新的密钥与盐，避免重复使用同一 key、salt、SSRC 和包索引组合。模块不负责持久化这份历史。

`close()` 关闭对象后，`protect/unprotect/re-key/restart` 均被拒绝。`public_state()` 和 `stats()` 仍可读取关闭时的最终快照。RTP/RTCP 解析失败也计入 `rejectCount`。

## 6. LTE NAS Security

Authentication 成功后，UE 与 MME 为当前 transaction 创建 NAS Security Context，后续 NAS 消息执行 128-EEA2 加解密和 128-EIA2 完整性检查。

### 6.1 32-bit NAS COUNT

本项目使用完整 32-bit COUNT，低 8 位为 sequence，高 24 位为 overflow，并为 Uplink/Downlink 分别维护 TX/RX 状态：

```text
COUNT = overflow(24 bit) || sequence(8 bit)
```

EIA2 输入包含 32-bit COUNT、5-bit BEARER、DIRECTION 和 MESSAGE；EEA2 的 CTR IV 同样由 COUNT/BEARER/DIRECTION 构造。接收端只有在 MAC、Replay 与解码/消息类型检查全部通过后才提交 RX COUNT/Replay 状态。

### 6.2 消息保护顺序

当前主流程为：

```text
Authentication PASS
    ↓
建立 transaction 级 K_NASenc / K_NASint（项目模拟派生）
    ↓
NAS_SECURITY_MODE_COMMAND
    EIA2 完整性保护；不加密；DL COUNT 推进
    ↓
UE 验证 NAS-MAC
    ↓
NAS_SECURITY_MODE_COMPLETE
    EEA2 Ciphering + EIA2 Integrity；UL COUNT 推进
    ↓
MME 验证 MAC / Replay，EEA2 解密，恢复 inner NAS PDU bytes
    ↓
NAS_ATTACH_ACCEPT
    EEA2 + EIA2；DL COUNT 推进
    ↓
NAS_ATTACH_COMPLETE
    EEA2 + EIA2；UL COUNT 推进
```

Runtime Evidence 会留下 `NAS_SECURITY_PDU_PROTECTED`、`NAS_SECURITY_PDU_VERIFIED`、`NAS_SECURITY_PDU_FAILED`，记录 direction、COUNT、sequence、ciphered、MAC、plain/protected SHA-256 等可公开证据；不会记录 K_NASenc/K_NASint 原始字节。

`NAS_SECURITY_MODE_COMMAND` 与 `NAS_ATTACH_ACCEPT` 必须携带非空的 `nasSecurityPduB64`，并通过严格 Base64 解码。缺失或空值返回 `NAS_SECURITY_PDU_MISSING`，格式错误进入安全校验失败流程。

接收端在提交 COUNT 和重放状态前检查保护模式：Security Mode Command 只做完整性保护，Security Mode Complete、Attach Accept 和 Attach Complete 同时加密。模式不符时返回 `NAS_PROTECTION_MODE_MISMATCH`，该 COUNT 仍可用于接收后续合法报文。

### 6.3 密钥、编码与输入限制

`nas_security.py` 的 EEA2/EIA2 是实际 bytes 运算，但本项目仍有以下限制：

- `derive_simulated_nas_keys()` 使用 transaction ID 生成一致的项目模拟 K_NASenc/K_NASint，**未实现完整 EPS AKA / KASME 密钥层级及 3GPP KDF**；
- 外层 NAS security header、MAC、sequence 和 ciphered payload 用真实 bytes 处理；inner NAS message 使用 `NasPlainPduCodec` 的简化稳定编码，**未覆盖完整 TS 24.301 IE 编码**；
- 当前 EEA2/EIA2 API 面向 **byte-aligned / octet-aligned inputs**。现有 EEA2 known-answer 采用标准测试数据的字节对齐部分，EIA2 采用字节对齐用例；这不能外推为任意非整字节 bit-length 3GPP 输入都已覆盖。`public_state().bitLengthBoundary` 会明确报告这一边界。

这些接口用于验证仿真消息的保护与接收状态，尚不能直接编解码完整 LTE NAS 报文。

## 7. 独立 Core Self-test

Security Core 本身不依赖 Web、HTTP、UDP、Attach 状态机或 LAN。可以运行：

```powershell
python -m lte_sim.security_engine.cli self-test
```

`run_standalone_core_checks()` 直接运行协议核心，当前覆盖 **17 项**：SRTP roundtrip、篡改状态、Replay、乱序、Replay Window 边界、ROC rollover、多 SSRC、并发 SSRC、Header Variant、固定种子 malformed fuzz、close 后拒绝、re-key 状态保持、SRTCP roundtrip/replay、NAS EEA2/EIA2 byte roundtrip、3GPP EIA2 known-answer、32-bit NAS COUNT rollover，以及 SRTCP E-bit/compound 固定回归向量。

标准向量还包含 RFC 3711 / RFC 2202 既有 3 组 known-answer；NAS EIA2 又增加 3GPP TS 33.401 Annex C.2.2 的 byte-aligned test set，期望 `MAC-I = B93787E6`。

## 8. UDP 集成实验

```text
Application Payload
→ RTP bytes
→ SRTP protect
→ socket.sendto()
→ OS UDP
→ socket.recvfrom()
→ SRTP unprotect
→ exact RTP/payload comparison
```

NORMAL、MULTI_PACKET、HEADER_VARIANTS、Tamper、Wrong Key、Replay、Out-of-order、Rollover 等场景继续使用本机真实 OS UDP Socket。v6.1.1 的 `ok=true` 必须由逐包 `packetVerificationOk` 汇总得到；如果人为让解密函数返回错误恢复内容，即使 accepted/rejected 数量看起来正确，最终实验也必须 FAIL。

UDP Lab 使用本机端点验证收发；跨进程、物理双机和持续媒体压力测试需要单独执行。

## 9. Security 页面

Security 页面同时显示：

- NAS：`EIA2 / AES-CMAC-32` 与 `EEA2 / AES-128-CTR`；
- NAS Byte Protection：UE/MME UL/DL COUNT、最近一次 protected/verified PDU、MAC 与 SHA-256 摘要；
- SRTP Profile：AES-128-CM/HMAC-SHA1-80；
- SRTCP 状态：index/E-bit/replay；
- Session Lifecycle：generation、re-key/restart count 与 key fingerprint；
- Core Self-test、RFC/3GPP known-answer、可选 libSRTP differential；
- UDP 端到端场景；
- 后端独立 Demo。

页面只是读取和展示后端状态。推荐的软件演示入口仍为 Security 页“运行后端独立 Demo”；`scripts\windows\security-demo.cmd` 只作为源码环境交叉复核。v6.0.3 起不再为了这一功能额外构建第三个 Security Demo EXE。

## 10. Standalone Demo

```powershell
python -m lte_sim.security_engine.cli demo
python scripts/security_standalone_demo.py
scripts\windows\security-demo.cmd
```

Demo 同时执行 SRTP 与 SRTCP roundtrip，输出 RTP/SRTP、RTCP/SRTCP 的 SHA-256、protect/unprotect count、ROC/SRTCP state 与 lifecycle 信息，并明确：

```text
webStateRead = false
lteAttachStateRead = false
faultConfigRead = false
```

Demo 直接调用后端模块，并输出本次执行的报文和状态摘要。

## 11. AES-GCM 与当前不实现范围

当前未实现 AES-GCM profile。增加该 profile 还需要单独实现和测试 IV、AAD、Tag、SRTP/SRTCP 帧格式及 nonce 复用检查。

当前仍不实现：MKI、DTLS-SRTP、完整外部密钥协商、完整 EPS AKA/KASME KDF、完整 TS 24.301 codec、所有 RTCP 扩展/互操作 profile、商用协议一致性认证与安全审计。若未来把 Security Core 发展为独立产品，再按独立 profile 增加 AEAD AES-GCM 更合适。

## 12. 测试入口与解释

`source_self_test.py` 检查运行代码、协议和安装资源，无需 `docs/`。Security 文档检查位于 `test_v611_security_delivery_contract.py`，由完整 `self_test.py` 执行。源码测试通过后，再继续构建和安装 wheel。

```powershell
python -m pytest devtools/tests/test_v610_security_upgrade.py -q
python -m pytest devtools/tests/test_v611_security_hardening.py -q
python -m pytest devtools/tests/test_v611_security_delivery_contract.py -q
python -m pytest devtools/tests/test_security_core.py -q
python -m pytest devtools/tests/test_srtp_udp.py -q
python devtools/validation/source_self_test.py
python devtools/validation/self_test.py
```

攻击/重放测试显示 PASS 的含义是“按预期拒绝”；正常场景 PASS 才表示字节 roundtrip 与状态均满足条件。当前公开仓库的持续集成状态以 GitHub Actions 为准，正式 Release 的构建与哈希信息以对应 Release 记录和 `BUILD-MANIFEST.json` 为准。

## Windows 审查记录与 v6.1.2 处理

2026-09-10 的 v6.1.1 Windows / pylibsrtp 1.0.0 审查曾观察到：项目首个 SRTCP index=0、参考实现首包 index=1，直接首包对比返回 `MISMATCH`；同时发现 RTCP 类型长度检查使用包含 padding 的总长度。这两项均被确认。v6.1.2 保持生产首包 index=0，只修正差分测试的显式 index 对齐，并将类型长度检查改为扣除 padding 后再判断。

本次 Windows / pylibsrtp 1.0.0 复测中，四组 SRTP 和两组 SRTCP 对照均通过，独立 Core 为 17 / 17。此结果不包含原生窗口、物理双机或长时间压力测试。
