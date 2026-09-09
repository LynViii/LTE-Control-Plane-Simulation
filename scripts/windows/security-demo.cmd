@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%\..\..") do set "PROJECT_ROOT=%%~fI"
set "OUT=%PROJECT_ROOT%\security-standalone-demo-result.json"
set "PYTHONPATH=%PROJECT_ROOT%\src"
set "PY="

cls
echo ============================================================
echo LTE 控制面系统仿真平台 - Standalone SRTP Demo
echo ============================================================
echo 此脚本只用于源码环境交叉复核：
echo - 不启动 LTE Attach
 echo - 不读取 Scenario / FaultConfig
 echo - 直接调用 StandaloneSrtpModule
 echo - 运行结束后会自动打开 JSON 结果
 echo.

if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" set "PY=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if not defined PY if exist "%PROJECT_ROOT%\.venv-build\Scripts\python.exe" set "PY=%PROJECT_ROOT%\.venv-build\Scripts\python.exe"
if not defined PY (
  where py.exe >nul 2>nul
  if not errorlevel 1 set "PY=py -3"
)
if not defined PY (
  where python.exe >nul 2>nul
  if not errorlevel 1 set "PY=python"
)

if not defined PY goto :no_python

echo [1/2] 正在执行独立 SRTP protect / unprotect...
%PY% -m lte_sim.security_engine.cli demo --payload "Standalone SRTP demo packet" --output "%OUT%"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto :failed

echo.
echo [2/2] PASS - 后端独立 Demo 完成。
echo 结果文件：%OUT%
echo.
start "" notepad.exe "%OUT%"
echo JSON 已用记事本打开；关闭记事本后可回到本窗口查看执行输出。
goto :finish

:no_python
echo [ERROR] 当前源码目录没有可用 Python 环境。
echo.
echo 推荐直接在软件 Security 页面点击“运行后端独立 Demo”；
echo 该按钮由程序后端直接调用 StandaloneSrtpModule，不会弹出额外 PowerShell/CMD。
echo.
echo 如需使用本脚本，请先在项目目录创建 .venv 或安装 Python 3.10+。
set "RC=9009"
goto :finish

:failed
echo.
echo [FAIL] Standalone SRTP Demo 执行失败，退出码 %RC%。
echo 请保留上方错误信息用于排查。

:finish
echo.
echo 按任意键关闭窗口...
pause >nul
exit /b %RC%
