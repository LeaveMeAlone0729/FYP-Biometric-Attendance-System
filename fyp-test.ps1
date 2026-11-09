param([Parameter(ValueFromRemainingArguments=$true)][string[]]$TestArguments)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& (Join-Path $PSScriptRoot 'backend\venv\Scripts\python.exe') -B `
    (Join-Path $PSScriptRoot 'backend\fyp_test.py') @TestArguments
exit $LASTEXITCODE
