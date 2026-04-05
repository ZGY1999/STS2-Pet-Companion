@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "GAME_DIR="
set "CONFIGURATION=Release"
set "SKIP_BUILD=0"
set "BACKUP_EXISTING=0"
set "NO_PAUSE=0"

:parse_args
if "%~1"=="" goto after_parse

if /I "%~1"=="-GameDir" (
    if "%~2"=="" (
        echo ERROR: -GameDir requires a path.
        goto fail
    )
    set "GAME_DIR=%~2"
    shift
    shift
    goto parse_args
)

if /I "%~1"=="-Configuration" (
    if "%~2"=="" (
        echo ERROR: -Configuration requires Debug or Release.
        goto fail
    )
    set "CONFIGURATION=%~2"
    shift
    shift
    goto parse_args
)

if /I "%~1"=="-SkipBuild" (
    set "SKIP_BUILD=1"
    shift
    goto parse_args
)

if /I "%~1"=="-BackupExisting" (
    set "BACKUP_EXISTING=1"
    shift
    goto parse_args
)

if /I "%~1"=="-NoPause" (
    set "NO_PAUSE=1"
    shift
    goto parse_args
)

if /I "%~1"=="-Help" goto usage
if /I "%~1"=="--help" goto usage
if /I "%~1"=="/?" goto usage

echo ERROR: Unknown argument %~1
goto fail

:after_parse
echo %* | findstr /I /C:"-SkipBuild" >nul && set "SKIP_BUILD=1"
echo %* | findstr /I /C:"-BackupExisting" >nul && set "BACKUP_EXISTING=1"
echo %* | findstr /I /C:"-NoPause" >nul && set "NO_PAUSE=1"

if not defined GAME_DIR set "GAME_DIR=%STS2_GAME_DIR%"

if not defined GAME_DIR (
    echo.
    set /P "GAME_DIR=Enter your Slay the Spire 2 install folder: "
)

if not defined GAME_DIR (
    echo ERROR: No game directory provided.
    goto fail
)

for %%I in ("%GAME_DIR%") do set "GAME_DIR=%%~fI"
set "GAME_DLL=%GAME_DIR%\data_sts2_windows_x86_64\sts2.dll"
set "MODS_DIR=%GAME_DIR%\mods"
set "OUT_DIR=%SCRIPT_DIR%out\STS2_MCP"
set "DLL_SOURCE=%OUT_DIR%\STS2_MCP.dll"
set "MANIFEST_SOURCE=%SCRIPT_DIR%mod_manifest.json"
set "ASSETS_SOURCE=%OUT_DIR%\STS2_MCP.assets"
set "DLL_TARGET=%MODS_DIR%\STS2_MCP.dll"
set "MANIFEST_TARGET=%MODS_DIR%\STS2_MCP.json"
set "ASSETS_TARGET=%MODS_DIR%\STS2_MCP.assets"

if /I not "!CONFIGURATION!"=="Debug" if /I not "!CONFIGURATION!"=="Release" (
    echo ERROR: -Configuration must be Debug or Release.
    goto fail
)

if not exist "%GAME_DLL%" (
    echo ERROR: Could not find sts2.dll in "%GAME_DIR%\data_sts2_windows_x86_64".
    echo Make sure -GameDir points to the Slay the Spire 2 installation root.
    goto fail
)

if "!SKIP_BUILD!"=="1" goto skip_build

where dotnet >nul 2>nul
if errorlevel 1 (
    echo ERROR: dotnet was not found. Install the .NET 9 SDK first.
    echo https://dotnet.microsoft.com/download/dotnet/9.0
    goto fail
)

if not exist "%SCRIPT_DIR%build.ps1" (
    echo ERROR: build.ps1 was not found next to install.cmd.
    goto fail
)

echo.
echo === Building STS2_MCP (%CONFIGURATION%) ===
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%build.ps1" -GameDir "%GAME_DIR%" -Configuration "%CONFIGURATION%"
if errorlevel 1 goto fail
goto after_build

:skip_build
echo.
echo Skipping build. Installing existing output from:
echo   %OUT_DIR%

:after_build

if not exist "%DLL_SOURCE%" (
    echo ERROR: Build output missing: "%DLL_SOURCE%"
    goto fail
)

if not exist "%MANIFEST_SOURCE%" (
    echo ERROR: Manifest missing: "%MANIFEST_SOURCE%"
    goto fail
)

echo.
echo === Installing to %MODS_DIR% ===

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ErrorActionPreference = 'Stop';" ^
    "$mods = [IO.Path]::GetFullPath('%MODS_DIR%');" ^
    "$dllSource = [IO.Path]::GetFullPath('%DLL_SOURCE%');" ^
    "$manifestSource = [IO.Path]::GetFullPath('%MANIFEST_SOURCE%');" ^
    "$assetsSource = [IO.Path]::GetFullPath('%ASSETS_SOURCE%');" ^
    "$backup = %BACKUP_EXISTING%;" ^
    "New-Item -ItemType Directory -Force -Path $mods | Out-Null;" ^
    "$stamp = Get-Date -Format 'yyyyMMdd-HHmmss';" ^
    "if ($backup -eq 1) {" ^
    "  $dllTarget = Join-Path $mods 'STS2_MCP.dll';" ^
    "  $jsonTarget = Join-Path $mods 'STS2_MCP.json';" ^
    "  $assetsTarget = Join-Path $mods 'STS2_MCP.assets';" ^
    "  if (Test-Path $dllTarget) { Copy-Item $dllTarget ($dllTarget + '.bak-' + $stamp) -Force };" ^
    "  if (Test-Path $jsonTarget) { Copy-Item $jsonTarget ($jsonTarget + '.bak-' + $stamp) -Force };" ^
    "  if (Test-Path $assetsTarget) { Copy-Item $assetsTarget ($assetsTarget + '.bak-' + $stamp) -Recurse -Force };" ^
    "}" ^
    "Copy-Item $dllSource (Join-Path $mods 'STS2_MCP.dll') -Force;" ^
    "Copy-Item $manifestSource (Join-Path $mods 'STS2_MCP.json') -Force;" ^
    "if (Test-Path $assetsSource) {" ^
    "  Copy-Item $assetsSource (Join-Path $mods 'STS2_MCP.assets') -Recurse -Force;" ^
    "}" ^
    "Write-Host 'Installed:';" ^
    "Write-Host ('  ' + (Join-Path $mods 'STS2_MCP.dll'));" ^
    "Write-Host ('  ' + (Join-Path $mods 'STS2_MCP.json'));" ^
    "if (Test-Path $assetsSource) { Write-Host ('  ' + (Join-Path $mods 'STS2_MCP.assets')) };" ^
    "if ($backup -eq 1) { Write-Host ('Backups created with timestamp ' + $stamp) }"
if errorlevel 1 goto fail

echo.
echo === Install succeeded ===
echo You can launch the game now.
goto end

:usage
echo Usage:
echo   install.cmd -GameDir "C:\Path\To\Slay the Spire 2"
echo.
echo Optional arguments:
echo   -Configuration Debug^|Release
echo   -SkipBuild
echo   -BackupExisting
echo   -NoPause
goto end

:fail
echo.
echo Installation failed.
set "EXIT_CODE=1"
goto end

:end
if not defined EXIT_CODE set "EXIT_CODE=0"
if "!NO_PAUSE!"=="0" (
    echo.
    pause
)
exit /b %EXIT_CODE%
