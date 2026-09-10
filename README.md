# LTE 控制面仿真

用 Python 模拟 LTE 终端的 Attach 流程，观察消息在 AP、Modem 和 eNB/MME 之间如何传递，以及流程在哪一步出错。当前版本为 v6.0.3。

AP 通过 AT 指令控制 Modem。Modem 内部有 NAS、RRC、L2、L1 四个工作线程，通过队列传递原语；AP–Modem 和 Modem–eNB/MME 使用 TCP 通信。浏览器页面可以查看流程状态、消息记录、计时器和故障诊断，也可以修改消息字段、延迟或丢弃消息，观察后续响应。

这里使用简化的 JSON 消息和网络侧模型，适合学习、调试 Attach 控制流程；运行时不需要基站、射频设备或 USIM。鉴权中的 RES/XRES 是模型字段。Security 页面另有独立的 SRTP 数据包实验。

## 运行

需要 Python 3.10 或以上版本。在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m lte_sim.web_app
```

浏览器打开 <http://127.0.0.1:3000>。保持“正常网络”，点击“开始 Attach”，完成后应显示 `11 / 11` 和 `ATTACHED`。在终端按 `Ctrl+C` 停止服务。

Linux/macOS 的虚拟环境 Python 路径为 `.venv/bin/python`，其余参数相同。

默认端口：

| 用途 | TCP 端口 |
|---|---:|
| Web 页面 | 3000 |
| AP → Modem | 5000 |
| Modem → eNB/MME | 5001 |
| LAN 管理通道 | 5002 |

端口和数据目录可以通过环境变量配置，见 [config.py](src/lte_sim/config.py)。源码运行生成的数据默认保存在 `var/` 下。

## 使用

Attach 按以下顺序运行：

```text
开启无线 → NAS 发起 Attach → 读取并校验 MIB/SIB
        → 随机接入 → RRC 建链 → 发送 Attach Request
        → 鉴权 → Security Mode → Attach Accept → Attach Complete
```

页面分为 Attach、AT / Socket、Task / Trace、Security 和诊断五个工作区。排查失败时，先看失败步骤，再查看同一流程关联 ID 下的收发消息、消费者实收值和计时器记录。

“中断当前流程”保留本次运行记录；“关闭无线”执行 `CFUN=0`；“系统重置”清理当前运行状态。再次开始 Attach 会创建新的事务。

故障配置分为预设和自定义两种。自定义配置只能修改目录中列出的字段，并按字段类型校验；延迟、丢弃、重复等动作在消息交付位置执行。普通诊断会使用运行事件中的注入记录。“证据隔离复算”会排除 `FAULT_INJECTED` 事件，但仍使用网络侧判定和校验事件。

## SRTP 实验

SRTP 模块在 [security_engine](src/lte_sim/security_engine/) 中，可以直接处理 RTP/SRTP 字节，也可以通过 UDP 实验检查正常收发、篡改、重放、乱序和序号回绕。

协议处理采用 AES-128-CM/HMAC-SHA1-80，`kdr=0`。项目代码负责 RTP 解析、密钥派生、包索引、ROC 和重放窗口，`cryptography/OpenSSL` 提供 AES、HMAC 运算。目前没有实现 SRTCP、MKI 或密钥协商。

安装项目后可单独执行：

```powershell
.\.venv\Scripts\python.exe -m lte_sim.security_engine.cli self-test
.\.venv\Scripts\python.exe -m lte_sim.security_engine.cli demo
```

UDP 实验在主控电脑本机收发。它与 Attach 中的 NAS Security Mode 分开运行。

## 源码

| 目录 | 内容 |
|---|---|
| `src/lte_sim/control_plane/` | Attach 编排、网络侧状态和消息判定 |
| `src/lte_sim/runtime/` | 工作线程、队列、计时器和 Trace |
| `src/lte_sim/fault_injection/` | 故障配置、字段目录及注入动作 |
| `src/lte_sim/diagnostics/` | 运行事件分析与诊断报告 |
| `src/lte_sim/security_engine/` | SRTP 实现、测试向量和 UDP 实验 |
| `src/lte_sim/web/` | 浏览器与 Windows 客户端共用的页面 |
| `scenarios/` | YAML 场景及格式定义 |
| `devtools/` | 测试和交付检查工具 |
| `scripts/`、`packaging/` | 运行、打包脚本和 Windows 图标资源 |

## 测试

下面这组核心测试可在仓库内直接运行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q devtools/tests/test_core.py devtools/tests/test_security_core.py devtools/tests/test_srtp_udp.py
```

安装 Node.js 后，可以检查前端语法：

```powershell
node --check src/lte_sim/web/app.js
```

完整测试还包含交付文档检查，需要本地的 `docs/`。该目录、历史验收记录和编译产物没有提交到此仓库。

## Windows 和双机运行

Windows 客户端用 WebView2 打开同一套页面。Local 模式在一台电脑运行；LAN 模式由电脑 A 运行主控和 eNB/MME，电脑 B 运行 Modem Agent。两端填写相同的端口、管理 token，并完成连接测试后再开始 Attach。

构建入口为 `scripts/windows/build-exe.ps1 -Bootstrap`。发布目录组装会复制 `docs/` 中的使用说明、依赖说明和图片，构建完整发布包前需要补齐这些本地文件。

第三方许可证保存在 [LICENSES](LICENSES/README.md)。构建时会从实际安装的依赖中重新收集许可证。
