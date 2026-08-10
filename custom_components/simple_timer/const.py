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

# Config entry key holding what "on" means for domains where that is a choice
# rather than a fixed service call - climate stores the hvac_mode to apply.
# Stored once on the entry, never per timer.
CONF_TURN_ON_OPTION = "turn_on_option"

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

# Runtime sensor state attributes. These are the card's public API - the card
# reads them by name, and shipped bundles will not be rebuilt. Do not rename.
ATTR_TIMER_STATE = "timer_state"
ATTR_TIMER_FINISHES_AT = "timer_finishes_at"
ATTR_TIMER_DURATION = "timer_duration"
ATTR_TIMER_REMAINING = "timer_remaining"
ATTR_WATCHDOG_MESSAGE = "watchdog_message"
ATTR_SWITCH_ENTITY_ID = "switch_entity_id"
ATTR_STATUS_ENTITY_ID = "status_entity_id"
ATTR_LAST_ON_TIMESTAMP = "last_on_timestamp"
ATTR_INSTANCE_TITLE = "instance_title"
ATTR_NEXT_RESET_DATE = "next_reset_date"
ATTR_RESET_TIME = "reset_time"
ATTR_TIMER_START_METHOD = "timer_start_method"

# Whether the monitored device is currently running, already resolved for the
# card. Additive: older bundles fall back to comparing the device state against
# "on", which is wrong for climate, where running means any non-off hvac mode.
ATTR_DEVICE_ACTIVE = "device_active"

# Where the card must send a power-button press. "direct" means it may call
# homeassistant.toggle itself, which is what every bundle did before climate
# support; "integration" means only we know how to turn this device on or off,
# so the press goes through the manual_power_toggle service.
#
# Published rather than derived from the entity domain, because the card is a
# shipped bundle nobody rebuilds: a new domain in domains.py must not need a
# card release. Absent means an integration older than this attribute, and the
# card falls back to "direct" - exactly what it used to do.
ATTR_POWER_TOGGLE_ROUTE = "power_toggle_route"
POWER_TOGGLE_DIRECT = "direct"
POWER_TOGGLE_INTEGRATION = "integration"

# Scheduled-start attributes
ATTR_SCHEDULE_STATE = "schedule_state"
ATTR_SCHEDULED_START = "scheduled_start"
ATTR_SCHEDULED_DURATION = "scheduled_duration"
ATTR_SCHEDULED_UNIT = "scheduled_unit"
ATTR_SCHEDULE_REPEAT = "schedule_repeat"
ATTR_SCHEDULE_DAYS = "schedule_days"

# Bus events described by logbook.py for human-readable Activity lines.
EVENT_TIMER_STARTED = f"{DOMAIN}_started"
EVENT_TIMER_EXTENDED = f"{DOMAIN}_extended"
EVENT_TIMER_CANCELLED = f"{DOMAIN}_cancelled"
EVENT_TIMER_FINISHED = f"{DOMAIN}_finished"
EVENT_SCHEDULE_SET = f"{DOMAIN}_scheduled"
EVENT_SCHEDULE_CANCELLED = f"{DOMAIN}_schedule_cancelled"