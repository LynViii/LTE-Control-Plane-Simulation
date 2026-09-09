param(
    [Parameter(Mandatory = $true)]
    [string[]]$Files,
    [string]$Thumbprint = $env:LTE_SIM_CODESIGN_THUMBPRINT,
    [string]$PfxPath = $env:LTE_SIM_CODESIGN_PFX,
    [string]$PfxPassword = $env:LTE_SIM_CODESIGN_PFX_PASSWORD,
    [string]$TimestampUrl = $env:LTE_SIM_TIMESTAMP_URL,
    [switch]$Required
)

$ErrorActionPreference = "Stop"

if (-not $Required -and $env:LTE_SIM_CODESIGN_REQUIRED -eq "1") {
    $Required = $true
}

$hasThumbprint = -not [string]::IsNullOrWhiteSpace($Thumbprint)
$hasPfx = -not [string]::IsNullOrWhiteSpace($PfxPath)

if (-not $hasThumbprint -and -not $hasPfx) {
    if ($Required) {
        throw "Code signing is required, but neither LTE_SIM_CODESIGN_THUMBPRINT nor LTE_SIM_CODESIGN_PFX is configured."
    }
    Write-Output "Code signing skipped: no certificate configured."
    return
}
if ($hasThumbprint -and $hasPfx) {
    throw "Configure only one code-signing source: certificate thumbprint OR PFX path."
}

function Find-SignTool {
    $cmd = Get-Command "signtool.exe" -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $kitsRoot = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
    if (Test-Path -LiteralPath $kitsRoot) {
        $candidate = Get-ChildItem -LiteralPath $kitsRoot -Filter "signtool.exe" -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match "\\x64\\signtool\.exe$" } |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($candidate) { return $candidate.FullName }
    }
    throw "signtool.exe was not found. Install the Windows SDK Signing Tools component or add signtool.exe to PATH."
}

$signtool = Find-SignTool

foreach ($file in $Files) {
    if (-not (Test-Path -LiteralPath $file)) {
        throw "Cannot sign missing file: $file"
    }

    $args = @("sign", "/fd", "SHA256")
    if ($hasThumbprint) {
        $args += @("/sha1", $Thumbprint)
    } else {
        $resolvedPfx = (Resolve-Path -LiteralPath $PfxPath).Path
        $args += @("/f", $resolvedPfx)
        if (-not [string]::IsNullOrEmpty($PfxPassword)) {
            $args += @("/p", $PfxPassword)
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($TimestampUrl)) {
        $args += @("/tr", $TimestampUrl, "/td", "SHA256")
    }
    $args += $file

    & $signtool @args
    if ($LASTEXITCODE -ne 0) { throw "signtool sign failed for $file" }

    & $signtool verify /pa /v $file
    if ($LASTEXITCODE -ne 0) { throw "signtool verify failed for $file" }

    Write-Output "Signed and verified: $file"
}
