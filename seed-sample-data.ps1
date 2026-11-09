param([string]$AsOf, [string]$AccountsFile)
$ErrorActionPreference = 'Stop'
$attendancePython = Join-Path $PSScriptRoot 'backend\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $attendancePython)) {
    throw 'Create backend\venv with Python 3.12 and install backend\requirements.txt first.'
}
if (-not $AccountsFile) {
    $downloadSetting = (Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders').'{374DE290-123F-4565-9164-39C4925E467B}'
    $AccountsFile = Join-Path ([Environment]::ExpandEnvironmentVariables($downloadSetting)) 'FYP_Biometric_Test_Accounts.txt'
}
$seedArguments = @((Join-Path $PSScriptRoot 'backend\seed_sample.py'), '--accounts-file', $AccountsFile)
if ($AsOf) { $seedArguments += @('--as-of', $AsOf) }
& $attendancePython @seedArguments
if ($LASTEXITCODE -ne 0) { throw 'Sample data seeding failed; check the error above.' }
