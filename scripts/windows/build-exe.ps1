param(
    [string]$PythonExe = "",
    [switch]$Bootstrap,
    [switch]$SkipSmoke
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$version = (Get-Content -LiteralPath (Join-Path $projectRoot "VERSION") -Raw).Trim()
$buildRoot = Join-Path $projectRoot "var\embedded-build"
$distRoot = Join-Path $projectRoot "release"
$packageName = "LTE-Control-Plane-Simulator-v$version-win64"
$packageRoot = Join-Path $distRoot $packageName
$exeName = "LTE-Control-Plane-Simulator.exe"
$agentExeName = "LTE-Modem-Node-Agent.exe"
$licenseRoot = Join-Path $packageRoot "LICENSES"

function Write-Stage([string]$Message) {
    Write-Host ""
    Write-Host "=== $Message ===" -ForegroundColor Cyan
}

function Assert-SafeChildPath([string]$Child, [string]$Parent, [string]$Label) {
    $childFull = [IO.Path]::GetFullPath($Child)
    $parentFull = [IO.Path]::GetFullPath($Parent).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    $prefix = $parentFull + [IO.Path]::DirectorySeparatorChar
    if (-not $childFull.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe $Label path: $childFull is not under $parentFull"
    }
}

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [Parameter(Mandatory=$true)][string[]]$Arguments,
        [Parameter(Mandatory=$true)][string]$Stage
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Stage failed with exit code $LASTEXITCODE"
    }
}

function New-BuildVenv([string]$VenvPath) {
    Write-Stage "Creating isolated build environment"
    $pyLauncher = Get-Command "py.exe" -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        & $pyLauncher.Source -3.13 -m venv $VenvPath
        if ($LASTEXITCODE -ne 0) {
            & $pyLauncher.Source -3 -m venv $VenvPath
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to create build venv with py.exe. Install 64-bit Python 3.10+ (Python 3.13 recommended)."
        }
        return
    }

    $pythonCommand = Get-Command "python.exe" -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        $pythonCommand = Get-Command "python" -ErrorAction SilentlyContinue
    }
    if (-not $pythonCommand) {
        throw "Python was not found. Install 64-bit Python 3.10+ (Python 3.13 recommended)."
    }
    & $pythonCommand.Source -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to create build venv with $($pythonCommand.Source)."
    }
}

function Resolve-BuildPython {
    if (-not [string]::IsNullOrWhiteSpace($PythonExe)) {
        if (Test-Path -LiteralPath $PythonExe) {
            return (Resolve-Path -LiteralPath $PythonExe).Path
        }
        $explicit = Get-Command $PythonExe -ErrorAction SilentlyContinue
        if ($explicit) { return $explicit.Source }
        throw "Specified Python executable was not found: $PythonExe"
    }

    foreach ($candidate in @(
        (Join-Path $projectRoot ".venv-build\Scripts\python.exe"),
        (Join-Path $projectRoot ".venv\Scripts\python.exe")
    )) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    if ($Bootstrap) {
        $venv = Join-Path $projectRoot ".venv-build"
        New-BuildVenv $venv
        $candidate = Join-Path $venv "Scripts\python.exe"
        if (-not (Test-Path -LiteralPath $candidate)) {
            throw "Build venv was created but python.exe is missing: $candidate"
        }
        return (Resolve-Path -LiteralPath $candidate).Path
    }

    $pythonCommand = Get-Command "python.exe" -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        $pythonCommand = Get-Command "python" -ErrorAction SilentlyContinue
    }
    if ($pythonCommand) { return $pythonCommand.Source }

    throw "Python was not found. Run .\scripts\windows\build-exe.ps1 -Bootstrap, or install 64-bit Python 3.10+."
}

if ($env:OS -ne "Windows_NT") {
    throw "Windows EXE packaging must be run on Windows 10/11 x64."
}

Set-Location -LiteralPath $projectRoot
$python = Resolve-BuildPython
Write-Output "Build Python: $python"

if ($Bootstrap) {
    Write-Stage "Installing / validating build dependencies"
    Invoke-NativeChecked -FilePath $python -Stage "pip bootstrap" -Arguments @(
        "-m", "pip", "install", "-e", ("{0}[embedded-build]" -f $projectRoot)
    )
}

Write-Stage "Build environment preflight"
$preflight = @'
import struct, sys
assert sys.version_info >= (3, 10), f"Python 3.10+ required, got {sys.version}"
assert struct.calcsize("P") * 8 == 64, "64-bit Python is required for the win64 release"
import PyInstaller, PIL, cffi, cryptography, jsonschema, yaml, webview
print(f"Python {sys.version.split()[0]} | PyInstaller {PyInstaller.__version__}")
'@
try {
    Invoke-NativeChecked -FilePath $python -Stage "build dependency preflight" -Arguments @("-c", $preflight)
} catch {
    throw "Build dependencies are incomplete. Run .\scripts\windows\build-exe.ps1 -Bootstrap, or install them with: pip install -e `".[embedded-build]`". Details: $($_.Exception.Message)"
}

Write-Stage "Generating icon and Windows version metadata"
Invoke-NativeChecked -FilePath $python -Stage "app icon generation" -Arguments @((Join-Path $projectRoot "scripts\build\create-app-icon.py"))
Invoke-NativeChecked -FilePath $python -Stage "version metadata generation" -Arguments @((Join-Path $projectRoot "scripts\build\create-version-info.py"))

Assert-SafeChildPath -Child $buildRoot -Parent $projectRoot -Label "build"
Assert-SafeChildPath -Child $distRoot -Parent $projectRoot -Label "release"
Assert-SafeChildPath -Child $packageRoot -Parent $distRoot -Label "package"

Write-Stage "Cleaning previous build outputs"
try {
    Remove-Item -LiteralPath $buildRoot -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $packageRoot -Recurse -Force -ErrorAction SilentlyContinue
} catch {
    throw "Unable to clean previous build output. Close any running LTE simulator/agent EXE and retry. Details: $($_.Exception.Message)"
}
New-Item -ItemType Directory -Force -Path $buildRoot, $distRoot, $packageRoot, $licenseRoot | Out-Null

$webData = "$(Join-Path $projectRoot 'src\lte_sim\web');lte_sim\web"
$scenarioData = "$(Join-Path $projectRoot 'scenarios');scenarios"

Write-Stage "Building main Windows EXE"
$mainPyInstallerArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--windowed",
    "--onefile",
    "--name", "LTE-Control-Plane-Simulator",
    "--icon", (Join-Path $projectRoot "packaging\app-icon.ico"),
    "--version-file", (Join-Path $projectRoot "packaging\version-info.txt"),
    "--paths", (Join-Path $projectRoot "src"),
    "--add-data", $webData,
    "--add-data", $scenarioData,
    "--collect-all", "cryptography",
    "--hidden-import", "webview.platforms.edgechromium",
    "--exclude-module", "PyQt5",
    "--exclude-module", "PySide6",
    "--exclude-module", "qtpy",
    "--exclude-module", "gi",
    "--exclude-module", "cefpython3",
    "--distpath", (Join-Path $buildRoot "dist"),
    "--workpath", (Join-Path $buildRoot "work"),
    "--specpath", $buildRoot,
    (Join-Path $projectRoot "packaging\embedded_entry.py")
)
Invoke-NativeChecked -FilePath $python -Stage "Main PyInstaller build" -Arguments $mainPyInstallerArgs

Write-Stage "Building modem agent Windows EXE"
$agentPyInstallerArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--windowed",
    "--onefile",
    "--name", "LTE-Modem-Node-Agent",
    "--icon", (Join-Path $projectRoot "packaging\app-icon.ico"),
    "--version-file", (Join-Path $projectRoot "packaging\version-info.txt"),
    "--paths", (Join-Path $projectRoot "src"),
    "--distpath", (Join-Path $buildRoot "dist"),
    "--workpath", (Join-Path $buildRoot "work-agent"),
    "--specpath", $buildRoot,
    (Join-Path $projectRoot "packaging\modem_agent_entry.py")
)
Invoke-NativeChecked -FilePath $python -Stage "Agent PyInstaller build" -Arguments $agentPyInstallerArgs

$mainExe = Join-Path $packageRoot $exeName
$agentExe = Join-Path $packageRoot $agentExeName
$builtMainExe = Join-Path (Join-Path $buildRoot "dist") $exeName
$builtAgentExe = Join-Path (Join-Path $buildRoot "dist") $agentExeName
if (-not (Test-Path -LiteralPath $builtMainExe)) { throw "PyInstaller did not produce the main EXE: $builtMainExe" }
if (-not (Test-Path -LiteralPath $builtAgentExe)) { throw "PyInstaller did not produce the agent EXE: $builtAgentExe" }

Write-Stage "Assembling release directory"
Copy-Item -LiteralPath $builtMainExe -Destination $mainExe -Force
Copy-Item -LiteralPath $builtAgentExe -Destination $agentExe -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "docs\WINDOWS_BUILD.md") -Destination (Join-Path $packageRoot "README.md") -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "README.md") -Destination (Join-Path $packageRoot "PROJECT-README.md") -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "LICENSES\README.md") -Destination (Join-Path $packageRoot "THIRD_PARTY_NOTICES.md") -Force
$lanEvidence = Join-Path $projectRoot "docs\images\lan-mode-success.png"
if (Test-Path -LiteralPath $lanEvidence) {
    Copy-Item -LiteralPath $lanEvidence -Destination (Join-Path $packageRoot "LAN-mode-success.png") -Force
}
Copy-Item -Path (Join-Path $projectRoot "LICENSES\*") -Destination $licenseRoot -Recurse -Force

Write-Stage "Optional Authenticode signing"
& (Join-Path $projectRoot "scripts\windows\sign-windows.ps1") -Files @($mainExe, $agentExe)

Write-Stage "Collecting third-party licenses"
Invoke-NativeChecked -FilePath $python -Stage "third-party license collection" -Arguments @(
    (Join-Path $projectRoot "scripts\build\collect-third-party-licenses.py"),
    "--destination", $licenseRoot
)

foreach ($required in @(
    $mainExe,
    $agentExe,
    (Join-Path $packageRoot "README.md"),
    (Join-Path $packageRoot "PROJECT-README.md"),
    (Join-Path $packageRoot "THIRD_PARTY_NOTICES.md"),
    (Join-Path $licenseRoot "proxy_tools-BSD.txt"),
    (Join-Path $licenseRoot "dependency-inventory.txt")
)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required release artifact missing: $required" }
}

$smokeScript = Join-Path $projectRoot "devtools\validation\smoke-release.ps1"
if ($SkipSmoke) {
    Write-Warning "Release smoke was skipped by -SkipSmoke. Do not treat this package as fully release-validated until the EXEs are smoke-tested."
} elseif (Test-Path -LiteralPath $smokeScript) {
    Write-Stage "Running packaged EXE smoke tests"
    try {
        & $smokeScript -MainExe $mainExe -AgentExe $agentExe
    } catch {
        throw "EXE files were built, but the packaged release smoke failed. The built EXEs remain in '$packageRoot'. Fix the smoke/runtime issue and rerun; for build-only diagnosis you may use -SkipSmoke. Details: $($_.Exception.Message)"
    }
} else {
    Write-Warning "devtools is absent: packaged EXE smoke test skipped; EXE build continues."
}

Write-Stage "Writing build manifest"
$pythonVersion = (& $python --version 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw "Unable to read Python version" }
$pyInstallerVersion = (& $python -m PyInstaller --version 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw "Unable to read PyInstaller version" }
$mainSignature = Get-AuthenticodeSignature -LiteralPath $mainExe
$agentSignature = Get-AuthenticodeSignature -LiteralPath $agentExe
$manifest = [ordered]@{
    version = $version
    builtAtUtc = [DateTime]::UtcNow.ToString("o")
    python = $pythonVersion
    pyinstaller = $pyInstallerVersion
    smokeSkipped = [bool]$SkipSmoke
    mainExe = [ordered]@{
        file = $exeName
        sha256 = (Get-FileHash -LiteralPath $mainExe -Algorithm SHA256).Hash
        signatureStatus = [string]$mainSignature.Status
        signer = if ($mainSignature.SignerCertificate) { $mainSignature.SignerCertificate.Subject } else { $null }
    }
    modemAgentExe = [ordered]@{
        file = $agentExeName
        sha256 = (Get-FileHash -LiteralPath $agentExe -Algorithm SHA256).Hash
        signatureStatus = [string]$agentSignature.Status
        signer = if ($agentSignature.SignerCertificate) { $agentSignature.SignerCertificate.Subject } else { $null }
    }
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $packageRoot "BUILD-MANIFEST.json") -Encoding UTF8

Write-Stage "Creating final ZIP"
$zipPath = Join-Path $distRoot "$packageName.zip"
Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zipPath -CompressionLevel Optimal -Force
$sha = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash

Write-Host ""
Write-Output "BUILD SUCCESS"
Write-Output "EXE: $mainExe"
Write-Output "MODEM AGENT: $agentExe"
Write-Output "ZIP: $zipPath"
Write-Output "ZIP SHA256: $sha"
