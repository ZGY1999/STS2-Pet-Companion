param(
    [ValidateSet("advise", "auto", "pause")]
    [string]$Mode = "advise",
    [int]$WaitTimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$srcDir = Join-Path $scriptDir "src"
$python = $env:STS2_PET_PYTHON
$pythonArgs = @()
if (-not $python) {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        $python = $pythonCmd.Source
    }
}
if (-not $python) {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        $python = $pyLauncher.Source
        $pythonArgs += "-3"
    }
}
if (-not $python) {
    throw "Python executable not found. Set STS2_PET_PYTHON or install python/py."
}
if (-not (Test-Path -LiteralPath $srcDir)) {
    throw "Orchestrator source directory not found: $srcDir"
}
$healthUrl = "http://127.0.0.1:15526/api/v1/pet/status"
$outLog = Join-Path $env:USERPROFILE "sts2-pet-orchestrator.out.log"
$errLog = Join-Path $env:USERPROFILE "sts2-pet-orchestrator.err.log"

Write-Host "Waiting for game bridge: $healthUrl"
$deadline = (Get-Date).AddSeconds($WaitTimeoutSeconds)
while ((Get-Date) -lt $deadline) {
    try {
        $null = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 2
        break
    }
    catch {
        Start-Sleep -Milliseconds 1000
    }
}

if ((Get-Date) -ge $deadline) {
    throw "Timed out waiting for the game bridge. Start the game with the mod enabled first."
}

Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object { $_.CommandLine -like "*sts2_pet.cli*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

if (Test-Path -LiteralPath $outLog) { Remove-Item -LiteralPath $outLog -Force }
if (Test-Path -LiteralPath $errLog) { Remove-Item -LiteralPath $errLog -Force }

if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$srcDir;$($env:PYTHONPATH)"
}
else {
    $env:PYTHONPATH = $srcDir
}

try {
    $process = Start-Process `
        -FilePath $python `
        -WorkingDirectory $scriptDir `
        -ArgumentList ($pythonArgs + @("-m", "sts2_pet.cli", "--mode", $Mode)) `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog `
        -PassThru
}
finally {
    if ($env:PYTHONPATH -eq $srcDir) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
    elseif ($env:PYTHONPATH -like "$srcDir;*") {
        $env:PYTHONPATH = $env:PYTHONPATH.Substring($srcDir.Length + 1)
    }
}

Write-Host "STS2 pet started."
Write-Host "Mode: $Mode"
Write-Host "PID: $($process.Id)"
Write-Host "Out log: $outLog"
Write-Host "Err log: $errLog"
