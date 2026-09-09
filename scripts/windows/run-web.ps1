$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH = Join-Path $projectRoot "src"
Set-Location -LiteralPath $projectRoot
python -m lte_sim.web_app
