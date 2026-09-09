$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$testTemp = [IO.Path]::GetFullPath((Join-Path $projectRoot ("var\check-" + [Guid]::NewGuid().ToString("N"))))
if (-not $testTemp.StartsWith($projectRoot + "\")) { throw "Unsafe test path" }
New-Item -ItemType Directory -Path $testTemp -Force | Out-Null
$env:PYTHONPATH = Join-Path $projectRoot "src"
$env:TEMP = $testTemp
$env:TMP = $testTemp
Set-Location -LiteralPath $projectRoot
try {
    python -u (Join-Path $PSScriptRoot "self_test.py")
    $checkExitCode = $LASTEXITCODE
} finally {
    Remove-Item -LiteralPath $testTemp -Recurse -Force -ErrorAction SilentlyContinue
}
exit $checkExitCode
