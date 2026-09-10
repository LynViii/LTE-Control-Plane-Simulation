# 开发与验证工具

`tests/` 保存 pytest 回归测试，`validation/` 保存源码自检、完整交付自检、源码 ZIP 校验和 Windows 发布检查脚本。仿真程序运行时不导入这些工具。 只运行仿真程序时，`devtools/` 可整体删除；删除后只是不再具备开发与交付检查能力。

## 两类自检不要混用

### 1. 源码仓库自检

用于新 clone、CI、wheel 安装验证，不要求历史验收材料或完整交付文档：

```powershell
python -m pip install -e ".[dev]"
python devtools/validation/source_self_test.py
```

该入口执行 Python 编译、JavaScript 语法检查、核心运行回归，并实际构建 wheel、安装到隔离目录后从项目目录外加载 package-local `scenarios/`。如果 wheel 缺少场景资源，会在这里直接失败。

### 2. 完整交付自检

用于准备正式源码 ZIP。它在源码测试之外，还检查当前 `docs/`、前端/API 契约、流程图和完整回归：

```powershell
python devtools/validation/self_test.py
```

因此 `self_test.py` 属于交付验收入口；不要把它当成“没有 docs 的最小 Git checkout”测试。

## 其他入口

源码 ZIP：

```powershell
python scripts/build/package-source.py
python scripts/build/package-source.py --without-devtools
```

`--without-devtools` 用于已经完成验证、只需要较小运行源码包的情况。

`validation/verify-source-package.py` 校验源码 ZIP 清单/哈希并在 fresh extraction 中运行完整自检。

Windows 构建使用：

```powershell
scripts\windows\build-exe.ps1
```

构建脚本会在相应验证材料存在时执行发布检查；缺失可选的交付材料时应给出明确提示，而不是把它误报为运行代码错误。

历史测试文件名中的版本号只表示用例首次加入的版本，并不表示它们只适用于该版本。
