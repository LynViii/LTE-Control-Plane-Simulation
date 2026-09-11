# LTE Control Plane Simulator v6.1.2 EXE 使用说明

本说明面向直接使用 Windows release 的普通用户。正常 Local/LAN 使用**不要求先设置 PowerShell 环境变量**。

## 1. 发布包

正式发布目录至少包含：

```text
LTE-Control-Plane-Simulator.exe
LTE-Modem-Node-Agent.exe
README.md
THIRD_PARTY_NOTICES.md
LICENSES/
```

电脑 A 的主应用使用 `LTE-Control-Plane-Simulator.exe`；只有 LAN Mode 的电脑 B 才需要启动 `LTE-Modem-Node-Agent.exe`。

## 2. 主应用启动：先选择 Local / LAN

双击主 EXE 后，程序先显示“请选择运行模式”。模式选择发生在 `SimulatorApplication.start()` 和协议 Socket 创建之前。

### Local Mode

适合单机开发、日常测试和功能验证。选择后：

- Web、AP、Modem、eNB、Security、Logs、Trace、Runs、PCAP 全部运行在本机；
- AP↔Modem 与 Modem↔eNB 都是真实 TCP Socket；
- 两条协议连接均使用 `127.0.0.1`；
- Local 默认被选中，但用户仍能看见并确认模式。

点击“启动 Local 模式”即可进入主界面。

## 3. LAN Mode：两台电脑完整操作流程

拓扑：

```text
电脑 A（主控）                         电脑 B（远端）
AP  ───────── AP-Modem TCP ─────────> Modem Agent
 eNB <──────── Modem-eNB TCP ───────── Modem Agent
Controller <──── Management TCP ─────> Modem Agent
Web / Security / Runs / PCAP 全部在电脑 A
```

两条协议 Socket 都必须经过真实局域网，不能出现一条跨机、另一条仍使用 localhost。

### 步骤 1：两台电脑连接同一局域网

两台电脑连接同一个路由器、交换机或 Wi-Fi。公司/校园网可能启用客户端隔离；如果两台电脑不能互相访问，需要换到允许设备互通的网络。

### 步骤 2：电脑 B 启动 Modem Agent

双击：

```text
LTE-Modem-Node-Agent.exe
```

Agent 配置窗口填写/确认：

- Controller IP：先填写电脑 A 的局域网 IPv4；
- Modem IP：点击“按 Controller IP 自动匹配电脑 B IPv4”，让系统按实际路由选择 Wi-Fi/Ethernet 地址；
- AP-Modem port；
- Modem-eNB port；
- Management port；
- Management token：至少 16 个字符。

端口和 token 必须与电脑 A 一致。默认端口通常可以直接使用：AP-Modem `5000`、Modem-eNB `5001`、Management `5002`；只要端口未被其他程序占用且防火墙允许即可。Management token 不是 SRTP 密钥，它只是 Controller ↔ Modem Agent 管理通道的鉴权字符串；自定义至少 16 个字符并确保两台电脑完全一致即可；建议为每次 LAN 联调自行设置独立 token。确认后启动 Agent，并保持程序运行。Modem Agent 使用 Windows 图形状态窗口，不额外打开黑色 CMD 控制台。Agent 启动时会再次按照 Controller IP 自动匹配电脑 B 的实际出口 IPv4，并在状态窗口日志中显示“电脑 A 的 Modem IP 应填写: x.x.x.x”。电脑 A 必须使用这个地址，避免把 VMware/Hyper-V/ICS/VPN 虚拟网卡地址填成 Modem IP。

在电脑 B 启动器中先点击 **“检查防火墙”**。如果显示 `RULES_MISSING`、`BLOCK_RULE_DETECTED` 或类似提示，点击 **“一键配置防火墙”** 并允许 UAC。程序只为本项目创建覆盖 Private/Public 的 TCP 5000/5002 入站规则，且 RemoteAddress 仅允许 Controller IP；不会关闭 Windows Defender Firewall。

### 步骤 3：电脑 A 选择 LAN Mode

双击主 EXE，选择 **LAN Mode**。主向导提供：

- Controller IP；
- Modem IP；
- HTTP port；
- AP-Modem port；
- Modem-eNB port；
- Management port；
- Management token；
- “按 Modem IP 自动检测本机 IP”；
- “重新检测”；
- “检查防火墙”；
- “一键配置防火墙”；
- “测试连接”；
- “启动 LAN 模式”。

Modem IP 先填电脑 B 的 IPv4，再点击“按 Modem IP 自动检测本机 IP”。程序会让操作系统按“到电脑 B 的实际路由”选择 Controller IP，避免优先选到 VPN/TUN 虚拟网卡。若看到类似 `198.18.x.x` 而电脑 B 是 `192.168.x.x`，应重点检查是否误选了虚拟网络接口。

随后点击 **“检查防火墙”**。电脑 A 的 TCP 5001 入站规则仅允许当前 Modem IP；若希望同一局域网其他设备访问 LAN Web，还会配置 TCP 3000（LocalSubnet）。两者都覆盖 Private/Public。缺失时点击 **“一键配置防火墙”** 并允许 UAC。若检测到与当前项目 EXE 直接关联的旧 Block 规则，程序会清理后重建项目规则；不会删除通用/企业策略 Block 规则。

### 步骤 4：点击“测试连接”

成功时至少应看到：

```text
Modem Agent:        ONLINE
Management:         CONNECTED
AP-Modem Socket:    READY
Modem-eNB Socket:   READY
Heartbeat:          有更新时间
```

Modem-eNB 的 `READY` 由连接测试结果决定：主控会临时/实际监听 Modem-eNB 端口，并通过 Management 要求电脑 B Agent **真实发起一次 B→A TCP 连接**。只有反向链路实际可达才显示 READY；正式协议 TCP 仍在 Attach/协议消息发生时按需建立。

失败时不要只看“Connection Failed”，按界面 issue/advice 检查：

- 两台电脑是否同一局域网且可互通；
- 电脑 B 的 Agent 是否已启动；
- Controller IP / Modem IP 是否正确；若主控自动检测出 VPN/TUN 地址，按 Modem IP 重新检测实际局域网接口；
- Windows 防火墙是否阻止主 EXE、Agent 或端口；优先使用启动器内“检查防火墙/一键配置防火墙”，不要依赖系统是否自动弹出“允许访问网络”窗口；
- AP-Modem / Modem-eNB / Management 端口是否被占用；
- 两端 Management token 是否完全一致。

### 步骤 5：启动 LAN 模式

预检查通过后点击“启动 LAN 模式”。进入主应用后，LAN 状态区会持续显示：

- Controller IP / Modem IP；
- Modem Agent ONLINE/OFFLINE；
- AP-Modem READY/CONNECTED/FAILED；
- Modem-eNB READY/CONNECTED/FAILED；
- Management CONNECTED/DISCONNECTED；
- Heartbeat 最近更新时间。

然后再执行 `AT+CFUN=1` 或单次 Attach。

## 4. LAN 现场验收方法

2026-09-04 已完成一轮真实双机应用层联调：

- 电脑 A / Controller：`192.168.43.6`；
- 电脑 B / Modem Agent：`192.168.43.15`；
- Modem Agent：`ONLINE`；
- AP-Modem Socket：`READY`；
- Modem-eNB Socket：`READY`；
- Management：`CONNECTED`；
- 正常 Attach：`11 / 11`，终态 `ATTACHED`。

历史截图见 `images/lan-mode-success.png`。这是当时的双机应用层联调记录，未附对应 Wireshark 抓包。

若需要进一步保存链路级独立证据，可在电脑 A 运行 Wireshark 验证：

1. 存在 `电脑A IP → 电脑B IP` 的 AP-Modem TCP 数据；
2. 存在 `电脑B IP → 电脑A IP` 的 Modem-eNB TCP 数据。

这两条都存在时，可以进一步确认“两条协议 Socket 均经过真实网卡/局域网”。如需更强的链路证据，可使用 Wireshark 在两端抓取对应 TCP 端口。

然后直接关闭电脑 B 的 Agent。电脑 A 应在心跳/管理检测后显示：

```text
Agent OFFLINE
Management DISCONNECTED
AP-Modem OFFLINE/断开
```

后续 Attach 请求必须失败或中止，不能继续显示正常。

## 5. WebView、本机访问和局域网访问

运行配置使用三个地址：

- Server bind address：HTTP 服务监听地址；
- Embedded WebView local access address：主 EXE 自己打开的地址；
- External LAN access address：其他局域网设备可访问的地址。

LAN 向导正常启动时 HTTP 监听 `0.0.0.0`，Embedded WebView 使用 `127.0.0.1:<HTTP port>`，外部设备可通过 `Controller IP:<HTTP port>` 访问。这样不会再出现“服务绑定到 LAN IP，但 WebView 仍错误访问没有监听的 localhost”的地址混用问题。

## Security / SRTP 使用

独立 Security Core 与真实 UDP 操作详见 [`SECURITY.md`](SECURITY.md)。页面把 Core 健康检查与实际链路验证分开：前者覆盖 11 项独立检查与 3 组 RFC 标准向量，不发送 UDP；后者执行 9 类真实 UDP 场景。NORMAL 实际链路为 1 包，MULTI_PACKET 为 5 包。

## 8. 常见错误

**UDP bind failed**：端口被占用或绑定 IP 不属于本机。关闭占用程序、改端口或检查网卡地址。

**Modem Agent offline**：确认电脑 B Agent、Modem IP、Management port、防火墙和 token。

**Authentication failed**：SRTP 包或 Tag 被修改，或收发端 key/profile 不一致。异常场景中这是预期拒绝。

**Replay detected**：同一个 SRTP packet index 已被接受过，Security Core 的重放窗口拒绝该包。Replay 实验中这是预期结果。


**WebView2 启动失败**：确认 Windows 10/11 64 位已安装 Microsoft Edge WebView2 Runtime。

## 9. 数据位置

主 Embedded EXE 默认把可写数据放在当前用户的 LocalAppData `LTEControlPlaneSimulator` 目录，而不是 PyInstaller 临时解包目录。Modem Agent 的临时诊断状态使用独立的 LocalAppData `LTEControlPlaneSimulatorModemAgent` 目录。LAN 模式所有**正式** Run、Trace、Logs、Statistics 和 PCAP 仍集中在电脑 A；Agent 不建立第二套正式 Run Repository。

## 10. 自动化/开发者环境变量

`LTE_SIM_MODE`、`LTE_SIM_BIND_HOST`、`LTE_SIM_CONTROLLER_HOST`、`LTE_SIM_MODEM_HOST`、端口和 token 环境变量仍保留给自动化测试/开发，不是普通用户的主操作流程。`LTE_SIM_SKIP_MODE_SELECTOR=1` 仅用于自动化 smoke，正式交互启动不会跳过模式选择。


---

## 构建说明

### Windows 构建与代码签名

## 1. 推荐构建方式

在 Windows 10/11 x64 上，从源码根目录直接运行正式 PowerShell 构建脚本：

```powershell
.\scripts\windows\build-exe.ps1 -Bootstrap
```

`-Bootstrap` 会优先复用项目中的 `.venv-build` / `.venv`；如果都不存在，会在项目根目录创建 `.venv-build`，并安装 `.[embedded-build]` 所需的 PyInstaller、pywebview、Pillow 等构建依赖。构建环境已准备好时可省略 `-Bootstrap`。

建议 Python 3.13 x64；最低要求 Python 3.10 x64。

正常完成后会生成：

- `LTE-Control-Plane-Simulator.exe`
- `LTE-Modem-Node-Agent.exe`
- `BUILD-MANIFEST.json`
- `THIRD_PARTY_NOTICES.md`
- `LICENSES/`
- 最终 release ZIP

输出目录：

```text
release/LTE-Control-Plane-Simulator-v<VERSION>-win64/
release/LTE-Control-Plane-Simulator-v<VERSION>-win64.zip
```

构建完成前会对最终 EXE 执行 packaged smoke test，因此“PyInstaller 已经生成 EXE”与“最终发布验收通过”是两个不同阶段。脚本现在会明确打印当前阶段，失败时也会说明究竟是依赖、PyInstaller、许可证收集还是 EXE smoke 出错。

## 2. 手工构建

如果希望自己管理虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[embedded-build]"
 .\scripts\windows\build-exe.ps1
```

如果虚拟环境已经装好依赖，也可直接：

```powershell
.\scripts\windows\build-exe.ps1
```

注意：普通 `requirements.txt` 只覆盖运行/测试依赖，**不包含完整 Windows EXE 构建工具链**。构建必须安装 `.[embedded-build]`，或直接使用 `scripts/windows/build-exe.ps1`。

## 3. 仅诊断 PyInstaller 构建

正常发布不建议跳过 smoke。如果已经成功生成两个 EXE，但最终失败信息明确来自 WebView2/端口/packaged smoke，可临时执行：

```powershell
 .\scripts\windows\build-exe.ps1 -SkipSmoke
```

这只用于确认“打包本身是否成功”。生成的 `BUILD-MANIFEST.json` 会记录 `smokeSkipped=true`，这种包不能当作完整验收通过的正式发布包。

如果清理旧构建目录失败，请先关闭正在运行的：

```text
LTE-Control-Plane-Simulator.exe
LTE-Modem-Node-Agent.exe
```

再重新构建。

## 4. 代码签名是可选步骤

项目默认**不要求**代码签名，因此没有证书也能正常构建。若配置证书，`scripts/windows/build-exe.ps1` 会在 smoke 前自动调用 `scripts/windows/sign-windows.ps1` 对两个 EXE 签名并执行 `signtool verify`。

代码签名主要解决发布者身份、完整性和 SmartScreen/企业策略信任问题，**不会代替 Windows 防火墙规则**。

### 方式 A：Windows 证书存储区中的代码签名证书

```powershell
$env:LTE_SIM_CODESIGN_THUMBPRINT = "你的证书Thumbprint"
$env:LTE_SIM_TIMESTAMP_URL = "你的CA提供的RFC3161时间戳地址"
.\scripts\windows\build-exe.ps1
```

### 方式 B：内部测试 PFX

```powershell
$env:LTE_SIM_CODESIGN_PFX = "C:\path\to\codesign.pfx"
$env:LTE_SIM_CODESIGN_PFX_PASSWORD = "PFX密码"
$env:LTE_SIM_TIMESTAMP_URL = "你的时间戳地址"
.\scripts\windows\build-exe.ps1
```

如果需要强制“没有有效签名就不允许发布”：

```powershell
$env:LTE_SIM_CODESIGN_REQUIRED = "1"
```

## 5. SignTool

`scripts/windows/sign-windows.ps1` 会优先从 PATH 查找 `signtool.exe`，找不到时再搜索 Windows SDK 的 x64 Signing Tools。若仍找不到，需要在 Visual Studio Installer / Windows SDK 中安装 Signing Tools 组件。

## 6. 最终验证

构建完成后可额外手工检查：

```powershell
$version = (Get-Content .\VERSION -Raw).Trim()
$release = ".\release\LTE-Control-Plane-Simulator-v$version-win64"
Get-AuthenticodeSignature "$release\LTE-Control-Plane-Simulator.exe"
Get-AuthenticodeSignature "$release\LTE-Modem-Node-Agent.exe"
Get-Content "$release\BUILD-MANIFEST.json"
```

签名成功时 `Status` 应为 `Valid`。没有配置签名证书时出现 `NotSigned` 是预期行为。`BUILD-MANIFEST.json` 会记录两个 EXE 的 SHA-256、签名状态、构建时间、Python、PyInstaller 版本以及是否跳过 smoke。
## 7. v6.1.2 Windows 工具链核查

- “打开 runs 目录”的 Windows 实现调用 `os.startfile(path)`；对应测试也 mock 这一真实接口。macOS/Linux 分支仍通过 `subprocess.Popen` 调用系统文件管理器。
- `devtools/validation/verify-frozen-source.py` 位于 `devtools/validation/` 两级目录之下，项目根目录使用 `Path(__file__).resolve().parents[2]` 定位；不再错误把 `devtools/` 当成项目根后读取不到 `VERSION`。
- 这两项可以由源码回归检查。源码 CI 可以覆盖 Windows 兼容性测试，但正式发布前仍建议在原生 Windows 10/11 x64 环境完成 EXE 构建、启动和 smoke 验证。
