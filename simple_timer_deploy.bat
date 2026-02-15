@echo off
set "TARGET_ENV=%~1"

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

REM =======================================================
REM SELECT ENVIRONMENT
REM =======================================================
if "%TARGET_ENV%"=="" goto :SelectEnv
goto :CheckEnv

:SelectEnv
cls
echo.
echo  Select target environment:
echo.
echo    1. PROD  (Real HA)
echo    2. DEV   (Local HA)
echo    3. Exit
echo.
choice /C 123 /N /M "  Enter choice (1, 2, or 3): "
if errorlevel 3 (
    echo Exiting...
    exit /b 0
)
if errorlevel 2 (
    set "TARGET_ENV=dev"
    goto :CheckEnv
)
if errorlevel 1 (
    set "TARGET_ENV=prod"
    goto :CheckEnv
)
goto :SelectEnv

:CheckEnv
if /i "%TARGET_ENV%"=="prod" (
    set "HA_CONFIG_DIR=%HA_PROD_CONFIG_DIR%"
    set "HA_URL=%HA_PROD_URL%"
    set "HA_API_TOKEN=%HA_PROD_API_TOKEN%"
    call :ColorEcho "Cyan" "Deploying to PROD environment..."
    goto :DoDeploy
)
if /i "%TARGET_ENV%"=="dev" (
    set "HA_CONFIG_DIR=%HA_DEV_CONFIG_DIR%"
    set "HA_URL=%HA_DEV_URL%"
    set "HA_API_TOKEN=%HA_DEV_API_TOKEN%"
    call :ColorEcho "Cyan" "Deploying to DEV environment..."
    goto :DoDeploy
)

call :ColorEcho "Red" "[ERROR] Invalid environment selected: %TARGET_ENV%"
pause
exit /b 1

:DoDeploy
if "%HA_CONFIG_DIR%"=="" (
    call :ColorEcho "Red" "[ERROR] HA_CONFIG_DIR is not set for %TARGET_ENV% environment!"
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
    call :ColorEcho "Yellow" "[INFO] Creating destination directory: %DEST_INTEGRATION%"
    mkdir "%DEST_INTEGRATION%"
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