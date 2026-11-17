param([Parameter(ValueFromRemainingArguments=$true)][string[]]$TestArguments)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
& (Join-Path $projectRoot 'backend\venv\Scripts\python.exe') -B `
    (Join-Path $projectRoot 'backend\fyp_test.py') @TestArguments
exit $LASTEXITCODE
