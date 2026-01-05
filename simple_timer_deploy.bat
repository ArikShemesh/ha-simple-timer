@echo off
cls
powershell -Command "Clear-Host"
setlocal enabledelayedexpansion
REM Simple deployment script for Simple Timer Integration (Windows) - DEV

REM =======================================================
REM LOAD CONFIGURATION
REM =======================================================
if not exist "deploy_config.bat" (
    call :ColorEcho "Red" "[ERROR] deploy_config.bat not found!"
    echo Please copy "deploy_config.template.bat" to "deploy_config.bat" and set your variables.
    pause
    exit /b 1
)
call deploy_config.bat

if "%HA_CONFIG_DIR%"=="" (
    call :ColorEcho "Red" "[ERROR] HA_CONFIG_DIR is not set in deploy_config.bat!"
    pause
    exit /b 1
)

call :ColorEcho "Cyan" "Starting deployment..."
echo Target: %HA_CONFIG_DIR%
echo.

set "SRC_DIST=custom_components\simple_timer\dist"
set "DEST_INTEGRATION=%HA_CONFIG_DIR%\custom_components\simple_timer"
set "DEST_WWW=%HA_CONFIG_DIR%\www"



echo.
call :ColorEcho "Cyan" "[1/3] Building card..."
call npm run build
if %errorlevel% neq 0 (
    call :ColorEcho "Red" "[ERROR] Build failed. Halting."
    exit /b %errorlevel%
)

echo.
call :ColorEcho "Cyan" "[2/3] Copying integration files..."
if not exist "%DEST_INTEGRATION%" (
    call :ColorEcho "Red" "[ERROR] Destination not found: %DEST_INTEGRATION%"
    exit /b 1
)
xcopy /E /I /Y "custom_components\simple_timer\*" "%DEST_INTEGRATION%\" >nul
echo Integration files copied.

echo.
call :ColorEcho "Cyan" "[3/3] Copying frontend resources..."
if not exist "%DEST_WWW%" mkdir "%DEST_WWW%"
copy /Y "%SRC_DIST%\timer-card.js" "%DEST_WWW%\timer-card.js" >nul
echo timer-card.js copied.

echo.
call :ColorEcho "Green" "*****************************************"
call :ColorEcho "Green" "*** DEPLOYMENT COMPLETED SUCCESSFULLY ***"
call :ColorEcho "Green" "*****************************************"

REM Reload resources if configured
if defined HA_URL (
    if defined HA_API_TOKEN (
        echo.
        call :ColorEcho "Cyan" "Reloading resources..."
        powershell -Command "try { Invoke-RestMethod -Uri '%HA_URL%/api/services/simple_timer/reload_resources' -Method Post -Body '{}' -Headers @{ 'Authorization' = 'Bearer %HA_API_TOKEN%'; 'Content-Type' = 'application/json' }; Write-Host 'Resources reloaded successfully' -ForegroundColor Green } catch { Write-Error $_ }"
    ) else (
        call :ColorEcho "Yellow" "[INFO] HA_API_TOKEN not set, skipping auto-reload."
    )
) else (
    call :ColorEcho "Yellow" "[INFO] HA_URL not set, skipping auto-reload."
)

echo.
call :ColorEcho "Yellow" "*Hard refresh your browser (Ctrl+Shift+R) to see changes."
goto :eof

:ColorEcho
powershell -Command "Write-Host '%~2' -ForegroundColor %~1" 2>nul || echo %~2
goto :eof