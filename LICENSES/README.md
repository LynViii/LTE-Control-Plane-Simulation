# Release license bundle

此目录中的固定文本用于核对当前 v5.4.0 运行与 Windows 构建相关的第三方许可边界，重点包括 cryptography/OpenSSL、pywebview、PyInstaller 及其间接依赖。当前运行路径不包含 pylibsrtp / 完整 libSRTP engine。

Windows 正式发布时，`scripts/build/collect-third-party-licenses.py` 还会从**实际构建环境**的已安装 distribution 中复制运行时依赖的 LICENSE/COPYING/NOTICE，并生成 `dependency-inventory.txt`。`scripts/windows/build-exe.ps1` 在压缩 release 前会执行该步骤；若关键依赖缺失则构建失败，避免只在源码仓库里保留声明而 release 漏掉许可证。

- `proxy_tools-BSD.txt`：pywebview 传递依赖 proxy_tools 0.1.0 的上游 LICENSE。
