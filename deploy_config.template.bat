@echo off
REM =======================================================
REM DEPLOYMENT CONFIGURATION (TEMPLATE)
REM Copy this file to "deploy_config.bat" and set your values.
REM =======================================================

REM =======================================================
REM PROD ENVIRONMENT (Real HA)
REM =======================================================
set "HA_PROD_CONFIG_DIR=\\YOUR_PROD_HA_IP\config"
REM set "HA_PROD_URL=http://YOUR_PROD_HA_IP:8123"
REM set "HA_PROD_API_TOKEN=YOUR_PROD_LONG_LIVED_ACCESS_TOKEN"

REM =======================================================
REM DEV ENVIRONMENT (Local/Test HA)
REM =======================================================
set "HA_DEV_CONFIG_DIR=C:\Users\arik\Documents\Private\Arik\Git\HA_DEV\core\config"
REM set "HA_DEV_URL=http://localhost:8123"
REM set "HA_DEV_API_TOKEN=YOUR_DEV_LONG_LIVED_ACCESS_TOKEN"
