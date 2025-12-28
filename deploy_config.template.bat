@echo off
REM =======================================================
REM DEPLOYMENT CONFIGURATION (TEMPLATE)
REM Copy this file to "deploy_config.bat" and set your values.
REM =======================================================

REM Path to your Home Assistant config directory
REM Example: set "HA_CONFIG_DIR=\\192.168.1.100\config"
set "HA_CONFIG_DIR=\\YOUR_HA_IP_ADDRESS\config"

REM Optional: Home Assistant URL and Token for auto-reloading resources
REM set "HA_URL=http://192.168.1.100:8123"
REM set "HA_API_TOKEN=YOUR_LONG_LIVED_ACCESS_TOKEN"
