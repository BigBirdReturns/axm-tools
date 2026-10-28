@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "APP=%LOCALAPPDATA%\MARY-App"
set "BOOT=%APP%\bootstrap\uv-0.13.5"
set "URL=https://github.com/astral-sh/uv/releases/download/0.13.5/uv-x86_64-pc-windows-msvc.zip"
set "SHA=a38b8d1902b7cfbc76b423ba1bb456f623f42064cdc72628b6075b89afd1019a"
if /I "%PROCESSOR_ARCHITECTURE%"=="ARM64" (
  set "URL=https://github.com/astral-sh/uv/releases/download/0.13.5/uv-aarch64-pc-windows-msvc.zip"
  set "SHA=09f47edf90726084a70f9426f6e3ca4f46e9bf7cbf23b1716ec64d60b055fae3"
)
if not exist "%BOOT%" mkdir "%BOOT%"
if not exist "%BOOT%\uv.zip" (
  curl.exe --fail --location --retry 2 --connect-timeout 20 --max-time 600 "%URL%" -o "%BOOT%\uv.zip.part"
  if errorlevel 1 goto failed
  move /y "%BOOT%\uv.zip.part" "%BOOT%\uv.zip" >nul
)
certutil.exe -hashfile "%BOOT%\uv.zip" SHA256 | findstr.exe /I /C:"%SHA%" >nul
if errorlevel 1 (
  echo Bootstrap archive checksum failed. Nothing was executed.
  goto failed
)
if not exist "%BOOT%\bin" mkdir "%BOOT%\bin"
tar.exe -xf "%BOOT%\uv.zip" -C "%BOOT%\bin"
if errorlevel 1 goto failed
set "UV=%BOOT%\bin\uv.exe"
if not exist "%UV%" goto failed
set "UV_PYTHON_INSTALL_DIR=%APP%\python"
set "UV_CACHE_DIR=%APP%\cache"
set "UV_PYTHON_BIN_DIR=%APP%\bin"
set "UV_NO_PROGRESS=1"
"%UV%" python install 3.12
if errorlevel 1 goto failed
"%UV%" run --no-project --managed-python --python 3.12 "%~dp0bootstrap.py" --uv "%UV%" %*
if errorlevel 1 goto failed
exit /b 0
:failed
echo Build stopped. Existing application versions and personal sources were preserved.
echo Read BUILD.md for the recorded prerequisites and the manual Python route.
pause
exit /b 2
