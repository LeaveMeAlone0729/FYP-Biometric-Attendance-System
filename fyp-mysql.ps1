param([Parameter(ValueFromRemainingArguments=$true)][string[]]$TestArguments)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$mysqlTestPython = Join-Path $PSScriptRoot 'backend\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $mysqlTestPython)) { throw 'Create backend\venv with Python 3.12 and install backend\requirements.txt first. See docs/MYSQL_TESTING.md.' }
& $mysqlTestPython -B (Join-Path $PSScriptRoot 'backend\mysql_testing.py') @TestArguments
exit $LASTEXITCODE
