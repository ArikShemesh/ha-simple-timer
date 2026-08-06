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

# Dispatcher signal fired whenever the runtime sensor writes state. Formatted
# with the config entry_id so each timer instance has its own channel. The
# status sensor listens on this instead of us having to touch every one of the
# ~30 async_write_ha_state() call sites in TimerRuntimeSensor.
SIGNAL_STATE_UPDATED = f"{DOMAIN}_state_updated_{{}}"

# Status sensor states. Non-numeric on purpose: the runtime sensor carries a
# unit_of_measurement, so HA's logbook filters it out and it can never appear
# in a device's Activity feed. These states are what make the timer loggable.
STATUS_IDLE = "idle"
STATUS_ACTIVE = "active"
STATUS_DELAYED_START = "delayed_start"
STATUS_SCHEDULED = "scheduled"

STATUS_OPTIONS = [
    STATUS_IDLE,
    STATUS_ACTIVE,
    STATUS_DELAYED_START,
    STATUS_SCHEDULED,
]

# Bus events described by logbook.py for human-readable Activity lines.
EVENT_TIMER_STARTED = f"{DOMAIN}_started"
EVENT_TIMER_EXTENDED = f"{DOMAIN}_extended"
EVENT_TIMER_CANCELLED = f"{DOMAIN}_cancelled"
EVENT_TIMER_FINISHED = f"{DOMAIN}_finished"
EVENT_SCHEDULE_SET = f"{DOMAIN}_scheduled"
EVENT_SCHEDULE_CANCELLED = f"{DOMAIN}_schedule_cancelled"