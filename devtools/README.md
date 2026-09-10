# 开发工具

`tests/` 保存 pytest 测试，`validation/` 保存项目自检、源码包校验和 Windows 发布检查脚本。仿真程序运行时不导入这些工具。只运行仿真程序时，`devtools/` 可整体删除；删除后不再执行开发和发布检查。

安装测试依赖：

```powershell
python -m pip install -e ".[dev]"
```

不依赖本地交付文档的核心测试：

```powershell
python -m pytest -q devtools/tests/test_core.py devtools/tests/test_security_core.py devtools/tests/test_srtp_udp.py
```

完整测试中的部分用例会检查 `docs/`、文档文字和完整交付结构。这个目录没有上传到 GitHub；运行全量测试或 `validation/self_test.py` 前需要本地交付包。历史测试名称中的版本号表示用例最初加入的版本。

`validation/verify-source-package.py` 用来校验源码 ZIP 的文件清单和哈希，并在解压目录运行自检。打包入口是：

```powershell
python scripts/build/package-source.py
```

传入 `--without-devtools` 可生成不含测试工具的源码包。Windows 构建脚本检测到 `validation/smoke-release.ps1` 时会执行发布检查；缺少它时会跳过该检查。

历史验收记录保存在本地的 `archive/`，不随本仓库上传。
