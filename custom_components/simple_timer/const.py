"""Constants for the Simple Timer integration."""
DOMAIN = "simple_timer"
PLATFORMS = ["sensor"]

# Frontend card serve path. Must be an integration-owned namespace, NOT under
# "/local/" — "/local/" is HA's reserved static mount for <config>/www/, and
# serving from there races HA's www catch-all route (file 404s when the www
# route wins). LEGACY_CARD_URL is the old "/local/" path, kept only so we can
# migrate/clean up resources left behind by versions <= 1.5.0.
CARD_URL = "/simple_timer/timer-card.js"
LEGACY_CARD_URL = "/local/simple-timer/timer-card.js"

WARNING_MSG_OFFLINE = "Warning: Home assistant was offline or reloaded during a running timer! Usage time may be unsynchronized."