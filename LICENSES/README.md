# 第三方许可证

本目录保存运行与 Windows 构建依赖的许可证副本，以及收集时生成的 `dependency-inventory.txt`。具体版本以清单为准。

发布时，`scripts/build/collect-third-party-licenses.py` 会从构建环境已安装的 Python 分发包中收集 LICENSE、COPYING 和 NOTICE。`scripts/windows/build-exe.ps1` 在生成发布 ZIP 前执行这一步，并将收集结果放入发布包。

SRTP 的协议代码位于 `src/lte_sim/security_engine/`；AES、HMAC 运算使用 `cryptography/OpenSSL`。`pylibsrtp` 仅用于可选的开发期对照测试。
