# devtools — 可整体删除的开发 / 验收工具

`devtools/` **不属于仿真平台运行时依赖**。它只保存开发期测试、源包验收、Windows 发布 Smoke Test 和历史验收记录。

目录：

```text
devtools/
├── tests/        pytest 回归测试
├── validation/   self_test / source ZIP / Windows release 检查
└── archive/      历史 validation 记录
```

如果代码已经验收完成、后续只想保留源码运行或自己构建 EXE，可以直接删除整个 `devtools/`。

删除后仍可使用：

- `python -m lte_sim.web_app`
- `scripts/windows/run-web.ps1`
- `scripts/windows/build-exe.ps1`（Windows EXE 构建入口）
- Local / LAN Attach
- Fault Injection / Trace / Diagnosis
- Security Core / SRTP UDP

区别只有：`scripts/windows/build-exe.ps1` 找不到 `devtools/validation/smoke-release.ps1` 时会跳过发布后的自动 Smoke Test，并给出 Warning；不会阻止 EXE 构建。

如果希望直接生成不包含该目录的源码包：

```powershell
python .\scripts\build\package-source.py --without-devtools
```

完整开发源码包仍可执行：

```powershell
python .\scripts\build\package-source.py
```
