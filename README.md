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
