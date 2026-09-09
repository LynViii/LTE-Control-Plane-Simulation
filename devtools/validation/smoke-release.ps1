param(
    [Parameter(Mandatory=$true)][string]$MainExe,
    [Parameter(Mandatory=$true)][string]$AgentExe
)
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$smokeRoot = Join-Path $projectRoot "var\release-smoke"
if (-not $smokeRoot.StartsWith($projectRoot + "\")) { throw "Unsafe smoke path" }
Remove-Item -LiteralPath $smokeRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $smokeRoot | Out-Null

if (-not (Test-Path -LiteralPath $MainExe)) { throw "Main EXE missing: $MainExe" }
if (-not (Test-Path -LiteralPath $AgentExe)) { throw "Modem Agent EXE missing: $AgentExe" }
function Stop-SmokeProcess($Process) {
    if (-not $Process) { return }
    # PyInstaller onefile launches a child; stopping only the bootloader leaks it.
    function Stop-Descendants([int]$ParentId) {
        $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$ParentId" -ErrorAction SilentlyContinue)
        foreach ($child in $children) {
            Stop-Descendants $child.ProcessId
            Stop-Process -Id $child.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
    Stop-Descendants $Process.Id
    Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
}

function Get-FreePort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    $port = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
    $listener.Stop()
    return $port
}

function Get-FourPorts {
    $ports = @()
    while ($ports.Count -lt 4) {
        $candidate = Get-FreePort
        if ($ports -notcontains $candidate) { $ports += $candidate }
    }
    return $ports
}

function Wait-Health([string]$Base, [int]$TimeoutSec = 20) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $health = $null
    while ((Get-Date) -lt $deadline) {
        try {
            $health = Invoke-RestMethod -Uri "$Base/api/health" -TimeoutSec 1
            if ($health.ok) { return $health }
        } catch { Start-Sleep -Milliseconds 150 }
    }
    throw "Main EXE health smoke failed for $Base"
}

function Wait-Attach([string]$Base) {
    $deadline = (Get-Date).AddSeconds(20)
    do {
        Start-Sleep -Milliseconds 100
        $state = Invoke-RestMethod -Uri "$Base/api/state" -TimeoutSec 3
    } while ($state.flow.running -and (Get-Date) -lt $deadline)
    if ($state.flow.running) { throw "Attach timeout" }
    return $state
}

function Set-CommonPorts($ports) {
    $env:PORT = [string]$ports[0]
    $env:AP_MODEM_PORT = [string]$ports[1]
    $env:ENB_PORT = [string]$ports[2]
    $env:LTE_SIM_MANAGEMENT_PORT = [string]$ports[3]
    $env:SIM_STEP_DELAY = "0"
    $env:SOCKET_TIMEOUT = "1"
    $env:LTE_SIM_SKIP_MODE_SELECTOR = "1"
}

# ---------------------------------------------------------------------------
# A. Final main EXE Local smoke: bundled scenarios + Attach / Core APIs + SRTP
# ---------------------------------------------------------------------------
$localPorts = Get-FourPorts
Set-CommonPorts $localPorts
$env:LTE_SIM_MODE = "local"
$env:HOST = "127.0.0.1"
$env:LTE_SIM_BIND_HOST = "127.0.0.1"
$env:LTE_SIM_CONTROLLER_HOST = "127.0.0.1"
$env:LTE_SIM_MODEM_HOST = "127.0.0.1"
$env:LTE_SIM_MANAGEMENT_TOKEN = ""
$env:LTE_SIM_DATA_DIR = (Join-Path $smokeRoot "local-controller")
$localProc = Start-Process -FilePath $MainExe -PassThru -WindowStyle Hidden
try {
    $base = "http://127.0.0.1:$($localPorts[0])"
    $health = Wait-Health $base
    $expectedVersion = (Get-Content (Join-Path $projectRoot "VERSION") -Raw).Trim()
    if ($health.version -ne $expectedVersion) { throw "Unexpected final EXE version: $($health.version), expected $expectedVersion" }

    foreach ($scenario in @("NORMAL", "AUTH_PARAMETER_INVALID", "AUTH_RESPONSE_TIMEOUT")) {
        $body = @{scenario=$scenario} | ConvertTo-Json
        Invoke-RestMethod -Uri "$base/api/scenario" -Method Post -ContentType "application/json" -Body $body | Out-Null
        Invoke-RestMethod -Uri "$base/api/at-command" -Method Post -ContentType "application/json" -Body '{"command":"AT+CFUN=1"}' | Out-Null
        $finished = Wait-Attach $base
        if ($scenario -eq "NORMAL" -and $finished.flow.completed.Count -ne 11) { throw "NORMAL did not complete" }
        if ($scenario -eq "AUTH_PARAMETER_INVALID" -and $finished.diagnosis.lastReport.root_cause -ne "PRIMITIVE_PARAMETER_INVALID") { throw "Parameter evidence failed" }
        if ($scenario -eq "AUTH_RESPONSE_TIMEOUT" -and $finished.diagnosis.lastReport.root_cause -ne "TIMER_EXPIRED") { throw "Timer evidence failed" }
    }
    $srtp = Invoke-RestMethod -Uri "$base/api/security/self-test" -Method Post -ContentType "application/json" -Body '{}' -TimeoutSec 30
    if (-not $srtp.ok) { throw "Security Core/UDP self-test failed" }
    $runs = Invoke-RestMethod -Uri "$base/api/runs"
    if ($runs.runs.Count -lt 3) { throw "EXE smoke expected at least three persisted Runs" }
    Write-Output "Main EXE Local smoke PASS: v5.3 health + NORMAL + evidence-driven fault diagnosis + real timer expiry + Security Core/UDP cases + persisted Runs"
} finally {
    Stop-SmokeProcess $localProc
}

# ---------------------------------------------------------------------------
# B. Final main + Agent EXEs LAN smoke on distinct loopback host addresses.
# This is the packaged equivalent of the automated two-host topology test.
# ---------------------------------------------------------------------------
$lanPorts = Get-FourPorts
$controllerIp = "127.0.0.3"
$modemIp = "127.0.0.2"
$token = "v50-release-smoke-token"
Set-CommonPorts $lanPorts

# Start packaged Modem Agent first. It inherits its own environment snapshot.
$env:LTE_SIM_MODE = "lan-modem"
$env:HOST = $modemIp
$env:LTE_SIM_BIND_HOST = $modemIp
$env:LTE_SIM_CONTROLLER_HOST = $controllerIp
$env:LTE_SIM_MODEM_HOST = $modemIp
$env:LTE_SIM_MANAGEMENT_TOKEN = $token
$env:LTE_SIM_AGENT_DATA_DIR = (Join-Path $smokeRoot "lan-agent")
$agentProc = Start-Process -FilePath $AgentExe -PassThru -WindowStyle Hidden
$lanProc = $null
try {
    Start-Sleep -Milliseconds 500

    # Now start the packaged controller with a production-style 0.0.0.0 HTTP/eNB bind.
    $env:LTE_SIM_MODE = "lan-controller"
    $env:HOST = "127.0.0.1"
    $env:LTE_SIM_BIND_HOST = "0.0.0.0"
    $env:LTE_SIM_CONTROLLER_HOST = $controllerIp
    $env:LTE_SIM_MODEM_HOST = $modemIp
    $env:LTE_SIM_MANAGEMENT_TOKEN = $token
    $env:LTE_SIM_DATA_DIR = (Join-Path $smokeRoot "lan-controller")
    $lanProc = Start-Process -FilePath $MainExe -PassThru -WindowStyle Hidden

    $lanBase = "http://127.0.0.1:$($lanPorts[0])"
    $lanHealth = Wait-Health $lanBase
    $expectedVersion = (Get-Content (Join-Path $projectRoot "VERSION") -Raw).Trim()
    if ($lanHealth.version -ne $expectedVersion) { throw "Unexpected LAN controller EXE version: $($lanHealth.version), expected $expectedVersion" }

    $preflight = Invoke-RestMethod -Uri "$lanBase/api/lan/test" -Method Post -ContentType "application/json" -Body "{}" -TimeoutSec 3
    if (-not $preflight.check.ok) { throw "Packaged LAN preflight failed: $($preflight.check | ConvertTo-Json -Depth 8)" }
    if ($preflight.check.agent.status -ne "ONLINE" -or $preflight.check.management.status -ne "CONNECTED") {
        throw "Packaged Agent/Management did not become ONLINE/CONNECTED"
    }
    if ($preflight.check.apModem.status -ne "READY" -or $preflight.check.modemEnb.status -ne "READY") {
        throw "Packaged LAN protocol sockets were not READY"
    }

    $attachBody = @{command="AT+CFUN=1"} | ConvertTo-Json
    $attach = Invoke-RestMethod -Uri "$lanBase/api/at-command" -Method Post -ContentType "application/json" -Body $attachBody -TimeoutSec 3
    if ($attach.response -ne "OK") { throw "Packaged LAN AT+CFUN=1 failed: $($attach.response)" }

    $deadline = (Get-Date).AddSeconds(15)
    $state = $null
    do {
        Start-Sleep -Milliseconds 120
        $state = Invoke-RestMethod -Uri "$lanBase/api/state" -TimeoutSec 2
    } while ($state.modem.attachStatus -ne "ATTACHED" -and (Get-Date) -lt $deadline)
    if ($state.modem.attachStatus -ne "ATTACHED") { throw "Packaged LAN Attach did not reach ATTACHED" }
    if ($state.flow.completed.Count -ne 11) { throw "Packaged LAN Attach expected 11 completed steps, got $($state.flow.completed.Count)" }
    if ($state.lan.agentStatus -ne "ONLINE" -or $state.lan.managementStatus -ne "CONNECTED") {
        throw "Packaged LAN state lost Agent/Management connection during Attach"
    }

    $apLog = $state.logs | Where-Object { $_.message -eq "AP-Modem socket connected" } | Select-Object -First 1
    $enbLog = $state.logs | Where-Object { $_.message -eq "Modem-eNB socket connected" } | Select-Object -First 1
    if (-not $apLog -or $apLog.detail.localIp -ne $modemIp) {
        throw "Packaged AP-Modem socket did not show Modem-side IP $modemIp"
    }
    if (-not $enbLog -or $enbLog.detail.localIp -ne $controllerIp) {
        throw "Packaged Modem-eNB socket did not show Controller-side IP $controllerIp"
    }

    # Agent is allowed temporary state only; it must not create a formal Runs repo.
    if (Test-Path -LiteralPath (Join-Path $smokeRoot "lan-agent\runs-not-used-on-agent")) {
        throw "Packaged Agent unexpectedly created a formal Run Repository"
    }

    Stop-SmokeProcess $agentProc
    $offlineDeadline = (Get-Date).AddSeconds(8)
    do {
        Start-Sleep -Milliseconds 200
        $state = Invoke-RestMethod -Uri "$lanBase/api/state" -TimeoutSec 2
    } while ($state.lan.agentStatus -ne "OFFLINE" -and (Get-Date) -lt $offlineDeadline)
    if ($state.lan.agentStatus -ne "OFFLINE" -or $state.lan.managementStatus -ne "DISCONNECTED") {
        throw "Packaged controller did not detect Agent disconnect"
    }

    Write-Output "Main + Agent EXE LAN smoke PASS: preflight + Management + two protocol sockets + 11-step Attach + disconnect detection"
} finally {
    Stop-SmokeProcess $lanProc
    Stop-SmokeProcess $agentProc
    Remove-Item Env:LTE_SIM_AGENT_DATA_DIR -ErrorAction SilentlyContinue
    Remove-Item Env:LTE_SIM_SKIP_MODE_SELECTOR -ErrorAction SilentlyContinue
}
