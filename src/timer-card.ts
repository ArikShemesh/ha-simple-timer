// timer-card.ts

import { LitElement, html } from 'lit';
import { cardStyles } from './timer-card.styles';
import { compactStyles } from './timer-card-compact.styles';


interface HAState {
  entity_id: string;
  state: string;
  attributes: {
    friendly_name?: string;
    entry_id?: string;
    switch_entity_id?: string;
    timer_state?: 'active' | 'idle';
    timer_finishes_at?: string;
    timer_duration?: number;
    watchdog_message?: string;
    show_seconds?: boolean; // This comes from backend now
    reset_time?: string; // Reset time from backend
    default_timer_enabled?: boolean;
    default_timer_duration?: number;
    default_timer_unit?: string;
    [key: string]: any;
  };
  last_changed: string;
  last_updated: string;
  context: {
    id: string;
    parent_id: string | null;
    user_id: string | null;
  };
}

interface HomeAssistant {
  states: {
    [entityId: string]: HAState;
  };
  services: {
    [domain: string]: { [service: string]: any } | undefined;
  };
  callService(domain: string, service: string, data?: Record<string, unknown>): Promise<void>;
  callApi<T = unknown>(method: 'GET' | 'POST' | 'PUT' | 'DELETE', path: string, parameters?: Record<string, unknown>, headers?: Record<string, string>): Promise<T>;
  callWS<T>(msg: { type: string;[key: string]: any }): Promise<T>;
  config: {
    components: {
      [domain: string]: {
        config_entries: { [entry_id: string]: unknown };
      };
    };
    [key: string]: any;
  };
}

const DOMAIN = "simple_timer";
const CARD_VERSION = "1.8.0";
const DEFAULT_TIMER_BUTTONS = [15, 30, 60, 90, 120, 150]; // Fallback when a config has no timer_buttons
// What a freshly added card starts with. Kept separate from the fallback above
// so shrinking it never changes a card that is already on a dashboard.
const NEW_CARD_TIMER_BUTTONS = [15, 30, 60, 120];
const TOTAL_BLOCKS = 16; // Segments in the block-style progress bar

console.info(
  `%c SIMPLE-TIMER-CARD %c v${CARD_VERSION} `,
  'color: orange; font-weight: bold; background: black',
  'color: white; font-weight: bold; background: dimgray',
);

interface TimerButton {
  displayValue: number;
  unit: string; // 'min', 's', 'h'
  labelUnit: string; // 'Min', 'Sec', 'Hr'
  minutesEquivalent: number;
  isDefault?: boolean;
}

class TimerCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      _config: { type: Object },
      _timeRemaining: { state: true },
      _remainingSeconds: { state: true },
      _sliderValue: { state: true },
      _entitiesLoaded: { state: true },
      _effectiveSwitchEntity: { state: true },
      _effectiveSensorEntity: { state: true },
      _validationMessages: { state: true },
      _scheduleExpanded: { state: true },
      _scheduleTime: { state: true },
      _scheduleDuration: { state: true },
      _scheduleUnit: { state: true },
      _scheduleRepeat: { state: true },
      _scheduleDays: { state: true },
      _compactExpanded: { state: true },
    };
  }

  hass?: HomeAssistant;
  _config?: TimerCardConfig;

  _countdownInterval: number | null = null;
  _liveRuntimeSeconds: number = 0;

  _timeRemaining: string | null = null;
  _remainingSeconds: number = 0; // Drives the block progress bar between formatted-string changes
  _sliderValue: number = 0;

  buttons: TimerButton[] = [];
  _validationMessages: string[] = [];
  _notificationSentForCurrentCycle: boolean = false;
  _entitiesLoaded: boolean = false;
  _serverTimeOffset: number = 0; // Offset in ms to add to local time to get server time
  _lastSyncedUpdate: string | null = null; // Track last_updated to detect fresh updates

  _effectiveSwitchEntity: string | null = null;
  _effectiveSensorEntity: string | null = null;

  _longPressTimer: number | null = null;
  _isLongPress: boolean = false;
  _touchStartPosition: { x: number; y: number } | null = null;
  _isCancelling: boolean = false;

  // Separate long-press state for the countdown/progress area. Kept apart from
  // the fields above, which belong to the daily-usage display and drive a
  // *reset* on long press - sharing them would let one element's press cancel
  // or misfire the other's.
  _countdownLongPressTimer: number | null = null;
  _countdownTouchStartPosition: { x: number; y: number } | null = null;

  // Schedule panel state
  _scheduleExpanded: boolean = false;
  _scheduleTime: string = "21:30";
  _scheduleDuration: number = 30;
  _scheduleUnit: string = "min";
  _scheduleRepeat: boolean = false;
  _scheduleDays: string[] = [];

  // Compact layout: the chevron panel holding the slider and schedule
  _compactExpanded: boolean = false;

  static async getConfigElement(): Promise<HTMLElement> {
    await import("./timer-card-editor.js");
    return document.createElement("timer-card-editor");
  }

  static getStubConfig(_hass: HomeAssistant): TimerCardConfig {
    console.log("TimerCard: Generating stub config - NO auto-selection will be performed");

    // New cards start compact. No card_title: compact names itself after the
    // controlled device. Existing cards carry no `layout` key and stay classic.
    return {
      type: "custom:timer-card",
      layout: "compact",
      timer_instance_id: null, // Changed from auto-selected instance to null
      timer_buttons: [...NEW_CARD_TIMER_BUTTONS],
      countdown_display: "both",
      hide_slider: false,
      slider_thumb_color: null,
      slider_background_color: null,
      power_button_background_color: null,
      power_button_icon_color: null
    };
  }

  setConfig(cfg: TimerCardConfig): void {
    const newSliderMax = cfg.slider_max && cfg.slider_max > 0 && cfg.slider_max <= 9999 ? cfg.slider_max : 120;
    const instanceId = cfg.timer_instance_id || 'default';

    this.buttons = this._getValidatedTimerButtons(cfg.timer_buttons);

    this._config = {
      ...cfg, // Preserve any HA-managed properties (e.g. visibility)
      type: cfg.type || "custom:timer-card",
      // Anything but an explicit "compact" is classic, so cards saved before
      // the option existed keep the layout they were built with.
      layout: cfg.layout === 'compact' ? 'compact' : 'classic',
      timer_buttons: cfg.timer_buttons || [...DEFAULT_TIMER_BUTTONS],
      card_title: cfg.card_title || null,
      entity_state_icon: cfg.entity_state_icon || null,
      power_button_icon: cfg.power_button_icon || null,
      slider_max: newSliderMax,
      slider_unit: cfg.slider_unit || 'min',
      reverse_mode: cfg.reverse_mode || false,
      hide_slider: cfg.hide_slider || false,
      show_daily_usage: cfg.show_daily_usage !== false,
      countdown_display: cfg.countdown_display || 'countdown',
      timer_instance_id: instanceId,
      entity: cfg.entity,
      sensor_entity: cfg.sensor_entity,
      slider_thumb_color: cfg.slider_thumb_color || null,
      slider_background_color: cfg.slider_background_color || null,
      timer_button_font_color: cfg.timer_button_font_color || null,
      timer_button_background_color: cfg.timer_button_background_color || null,
      power_button_background_color: cfg.power_button_background_color || null,
      power_button_icon_color: cfg.power_button_icon_color || null,
      entity_state_button_background_color: cfg.entity_state_button_background_color || null,
      entity_state_button_icon_color: cfg.entity_state_button_icon_color || null,
      entity_state_button_background_color_on: cfg.entity_state_button_background_color_on || null,
      entity_state_button_icon_color_on: cfg.entity_state_button_icon_color_on || null,
      turn_off_on_cancel: cfg.turn_off_on_cancel !== false,
      show_schedule: cfg.show_schedule || false
    };

    if (cfg.timer_instance_id) {
      this._config.timer_instance_id = cfg.timer_instance_id;
    }
    if (cfg.entity) {
      this._config.entity = cfg.entity;
    }
    if (cfg.sensor_entity) {
      this._config.sensor_entity = cfg.sensor_entity;
    }

    // Always initialize from localStorage
    const saved = localStorage.getItem(`simple-timer-slider-${instanceId}`);
    let parsed = saved ? parseInt(saved) : NaN;
    if (isNaN(parsed) || parsed < 0) {
      parsed = newSliderMax;
    }

    // Clamp if needed
    if (parsed > newSliderMax) {
      parsed = newSliderMax;
    }

    this._sliderValue = parsed;
    localStorage.setItem(`simple-timer-slider-${instanceId}`, this._sliderValue.toString());

    // Restore last-used schedule form values (survives page refresh)
    this._restoreSchedule();

    this.requestUpdate();


    this._liveRuntimeSeconds = 0;
    this._notificationSentForCurrentCycle = false;
    this._effectiveSwitchEntity = null;
    this._effectiveSensorEntity = null;
    this._entitiesLoaded = false;
  }

  _getValidatedTimerButtons(configButtons: any): TimerButton[] {
    let validatedTimerButtons: TimerButton[] = [];
    this._validationMessages = [];

    if (Array.isArray(configButtons)) {
      const invalidValues: any[] = [];
      const uniqueValues = new Set<string>(); // Use string representation for uniqueness
      const duplicateValues: any[] = [];

      configButtons.forEach(val => {
        let displayValue: number;
        let unit = 'min';
        let labelUnit = 'Min';
        let minutesEquivalent: number;

        const strVal = String(val).trim().toLowerCase();

        // Match numbers (including decimals) optionally followed by unit, optionally ending with *
        const match = strVal.match(/^(\d+(?:\.\d+)?)\s*(s|sec|seconds|m|min|minutes|h|hr|hours|d|day|days)?(\*)?$/);

        if (match) {
          const numVal = parseFloat(match[1]);
          const isFloat = match[1].includes('.');
          const unitStr = match[2] || 'min';
          const isDefault = !!match[3];
          const isHours = unitStr.startsWith('h');
          const isDays = unitStr.startsWith('d');

          // User Restriction: Limit to 9999 for all units
          if (numVal > 9999) {
            invalidValues.push(val);
            return;
          }

          // User Restriction: Fractional numbers only allowed for hours and days
          if (isFloat && !isHours && !isDays) {
            invalidValues.push(val);
            return;
          }

          // User Restriction: Max 1 digit after decimal for hours and days
          if (isFloat && (isHours || isDays)) {
            const decimalPart = match[1].split('.')[1];
            if (decimalPart && decimalPart.length > 1) {
              invalidValues.push(val);
              return;
            }
          }

          displayValue = numVal;

          if (unitStr.startsWith('s')) {
            unit = 's';
            labelUnit = 'sec';
            minutesEquivalent = displayValue / 60;
          } else if (unitStr.startsWith('h')) {
            unit = 'h';
            labelUnit = 'hr';
            minutesEquivalent = displayValue * 60;
          } else if (unitStr.startsWith('d')) {
            unit = 'd';
            labelUnit = 'day';
            minutesEquivalent = displayValue * 1440;
          } else {
            unit = 'min';
            labelUnit = 'min';
            minutesEquivalent = displayValue;
          }

          if (displayValue > 0) {
            const uniqueKey = `${minutesEquivalent}`;
            if (isDefault) {
              // Always accept default timer (it doesn't conflict with grid buttons)
              validatedTimerButtons.push({ displayValue, unit, labelUnit, minutesEquivalent, isDefault });
            } else {
              if (uniqueValues.has(uniqueKey)) {
                duplicateValues.push(val);
              } else {
                uniqueValues.add(uniqueKey);
                validatedTimerButtons.push({ displayValue, unit, labelUnit, minutesEquivalent, isDefault });
              }
            }
          } else {
            invalidValues.push(val);
          }
        } else {
          invalidValues.push(val);
        }
      });

      const messages: string[] = [];
      if (invalidValues.length > 0) {
        messages.push(`Invalid timer values ignored: ${invalidValues.join(', ')}. Format example: 30, "30s", "1h", "2d". Limit 9999.`);
      }
      if (duplicateValues.length > 0) {
        messages.push(`Duplicate timer values were removed.`);
      }
      this._validationMessages = messages;

      validatedTimerButtons.sort((a, b) => a.minutesEquivalent - b.minutesEquivalent);
      return validatedTimerButtons;
    }

    if (configButtons === undefined || configButtons === null) {
      return [];
    }

    console.warn(`TimerCard: Invalid timer_buttons type (${typeof configButtons}):`, configButtons, `- using empty array`);
    this._validationMessages = [`Invalid timer_buttons configuration. Expected array, got ${typeof configButtons}.`];
    return [];
  }

  _determineEffectiveEntities(): void {
    let currentSwitch: string | null = null;
    let currentSensor: string | null = null;
    let entitiesAreValid = false;

    if (!this.hass || !this.hass.states) {
      this._entitiesLoaded = false;
      return;
    }

    if (this._config?.timer_instance_id) {
      const targetEntryId = this._config.timer_instance_id;
      const allSensors = Object.keys(this.hass.states).filter(entityId => entityId.startsWith('sensor.'));
      const instanceSensor = allSensors.find(entityId => {
        const state = this.hass!.states[entityId];
        return state.attributes.entry_id === targetEntryId &&
          typeof state.attributes.switch_entity_id === 'string';
      });

      if (instanceSensor) {
        const sensorState = this.hass.states[instanceSensor];
        currentSensor = instanceSensor;
        currentSwitch = sensorState.attributes.switch_entity_id as string | null;

        if (currentSwitch && this.hass.states[currentSwitch]) {
          entitiesAreValid = true;
        } else {
          console.warn(`TimerCard: Configured instance '${targetEntryId}' sensor '${currentSensor}' links to missing or invalid switch '${currentSwitch}'.`);
        }
      } else {
        console.warn(`TimerCard: Configured timer_instance_id '${targetEntryId}' does not have a corresponding simple_timer sensor found.`);
      }
    }

    if (!entitiesAreValid && this._config?.sensor_entity) {
      const sensorState = this.hass.states[this._config.sensor_entity];
      if (sensorState && typeof sensorState.attributes.entry_id === 'string' && typeof sensorState.attributes.switch_entity_id === 'string') {
        currentSensor = this._config.sensor_entity;
        currentSwitch = sensorState.attributes.switch_entity_id as string | null;
        if (currentSwitch && this.hass.states[currentSwitch]) {
          entitiesAreValid = true;
          console.info(`TimerCard: Using manually configured sensor_entity: Sensor '${currentSensor}', Switch '${currentSwitch}'.`);
        } else {
          console.warn(`TimerCard: Manually configured sensor '${currentSensor}' links to missing or invalid switch '${currentSwitch}'.`);
        }
      } else {
        console.warn(`TimerCard: Manually configured sensor_entity '${this._config.sensor_entity}' not found or missing required attributes.`);
      }
    }

    if (this._effectiveSwitchEntity !== currentSwitch || this._effectiveSensorEntity !== currentSensor) {
      this._effectiveSwitchEntity = currentSwitch;
      this._effectiveSensorEntity = currentSensor;
      this.requestUpdate();
    }

    this._entitiesLoaded = entitiesAreValid;
  }

  _getEntryId(): string | null {
    if (!this._effectiveSensorEntity || !this.hass || !this.hass.states) {
      console.error("Timer-card: _getEntryId called without a valid effective sensor entity.");
      return null;
    }
    const sensor = this.hass.states[this._effectiveSensorEntity];
    if (sensor && sensor.attributes.entry_id) {
      return sensor.attributes.entry_id;
    }
    console.error("Could not determine entry_id from effective sensor_entity attributes:", this._effectiveSensorEntity);
    return null;
  }

  _startTimer(minutes: number, unit: string = 'min', startMethod: 'button' | 'slider' = 'button'): void {
    this._validationMessages = [];
    if (!this._entitiesLoaded || !this.hass || !this.hass.callService) {
      console.error("Timer-card: Cannot start timer. Entities not loaded or callService unavailable.");
      return;
    }

    const entryId = this._getEntryId();
    if (!entryId) { console.error("Timer-card: Entry ID not found for starting timer."); return; }

    const switchId = this._effectiveSwitchEntity!;
    let reverseMode = this._config?.reverse_mode || false;

    // Override: If a Default Timer is active on the backend, Reverse Mode is strictly disabled
    // to prevent conflicting logic (Auto-Off vs Delayed-Start).
    if (this._effectiveSensorEntity && this.hass) {
      const sensor = this.hass.states[this._effectiveSensorEntity];
      if (sensor && sensor.attributes.default_timer_enabled) {
        reverseMode = false;
      }
    }

    if (reverseMode) {
      // REVERSE MODE: Start timer directly (Decoupled: Do not force OFF state)
      this.hass!.callService(DOMAIN, "start_timer", {
        entry_id: entryId,
        duration: minutes,
        unit: unit,
        reverse_mode: true,
        start_method: startMethod
      });
    } else {
      // NORMAL MODE: Start timer directly (Backend handles turning switch ON)
      this.hass!.callService(DOMAIN, "start_timer", { entry_id: entryId, duration: minutes, unit: unit, start_method: startMethod });
    }

    this._notificationSentForCurrentCycle = false;
  }

  _addTimer(minutes: number, unit: string = 'min'): void {
    this._validationMessages = [];
    if (!this._entitiesLoaded || !this.hass || !this.hass.callService) {
      console.error("Timer-card: Cannot add to timer. Entities not loaded or callService unavailable.");
      return;
    }

    const entryId = this._getEntryId();
    if (!entryId) { console.error("Timer-card: Entry ID not found for adding to timer."); return; }

    this.hass.callService(DOMAIN, "add_timer", {
      entry_id: entryId,
      duration: minutes,
      unit: unit
    }).then(() => {
      console.log(`Timer-card: Added ${minutes} ${unit} to active timer.`);
    }).catch(error => {
      console.error("Timer-card: Error adding to timer:", error);
    });
  }

  _setSchedule(): void {
    this._validationMessages = [];
    if (!this._entitiesLoaded || !this.hass || !this.hass.callService) {
      console.error("Timer-card: Cannot set schedule. Entities not loaded or callService unavailable.");
      return;
    }

    const entryId = this._getEntryId();
    if (!entryId) { console.error("Timer-card: Entry ID not found for scheduling."); return; }

    const duration = Number(this._scheduleDuration);
    if (!this._scheduleTime || !(duration > 0)) {
      this._validationMessages = ["Set a start time and a run-for duration above 0."];
      return;
    }

    this._persistSchedule();

    this.hass.callService(DOMAIN, "schedule_timer", {
      entry_id: entryId,
      start_time: this._scheduleTime.length === 5 ? `${this._scheduleTime}:00` : this._scheduleTime,
      duration: duration,
      unit: this._scheduleUnit,
      repeat: this._scheduleRepeat,
      days: this._scheduleRepeat ? this._scheduleDays : [],
    }).then(() => {
      this._scheduleExpanded = false;
    }).catch(error => {
      console.error("Timer-card: Error setting schedule:", error);
    });
  }

  _cancelSchedule(): void {
    if (!this.hass || !this.hass.callService) return;
    const entryId = this._getEntryId();
    if (!entryId) { console.error("Timer-card: Entry ID not found for cancelling schedule."); return; }
    this.hass.callService(DOMAIN, "cancel_schedule", { entry_id: entryId })
      .catch(error => console.error("Timer-card: Error cancelling schedule:", error));
  }

  _toggleScheduleDay(day: string): void {
    this._scheduleDays = this._scheduleDays.includes(day)
      ? this._scheduleDays.filter(d => d !== day)
      : [...this._scheduleDays, day];
    this._persistSchedule();
  }

  _scheduleStorageKey(): string {
    return `simple-timer-schedule-${this._config?.timer_instance_id || 'default'}`;
  }

  _persistSchedule(): void {
    try {
      localStorage.setItem(this._scheduleStorageKey(), JSON.stringify({
        time: this._scheduleTime,
        duration: this._scheduleDuration,
        unit: this._scheduleUnit,
        repeat: this._scheduleRepeat,
        days: this._scheduleDays,
      }));
    } catch (e) {
      console.warn("Timer-card: could not persist schedule form", e);
    }
  }

  _restoreSchedule(): void {
    try {
      const raw = localStorage.getItem(this._scheduleStorageKey());
      if (!raw) return;
      const s = JSON.parse(raw);
      if (typeof s.time === 'string') this._scheduleTime = s.time;
      if (typeof s.duration === 'number') this._scheduleDuration = s.duration;
      if (typeof s.unit === 'string') this._scheduleUnit = s.unit;
      if (typeof s.repeat === 'boolean') this._scheduleRepeat = s.repeat;
      if (Array.isArray(s.days)) this._scheduleDays = s.days;
    } catch (e) {
      console.warn("Timer-card: could not restore schedule form", e);
    }
  }

  _cancelTimer(): void {
    this._validationMessages = [];
    if (!this._entitiesLoaded || !this.hass || !this.hass.callService) {
      console.error("Timer-card: Cannot cancel timer. Entities not loaded or callService unavailable.");
      return;
    }

    // Set flag to prevent immediate restart
    this._isCancelling = true;

    const entryId = this._getEntryId();
    if (!entryId) {
      console.error("Timer-card: Entry ID not found for cancelling timer.");
      this._isCancelling = false;
      return;
    }

    const turnOffEntity = this._config?.turn_off_on_cancel !== false;

    this.hass.callService(DOMAIN, "cancel_timer", { entry_id: entryId, turn_off_entity: turnOffEntity })
      .then(() => {
        // Reset flag after a short delay to ensure state has settled
        setTimeout(() => {
          this._isCancelling = false;
        }, 1000);
      })
      .catch(error => {
        console.error("Timer-card: Error cancelling timer:", error);
        this._isCancelling = false;
      });

    this._notificationSentForCurrentCycle = false;
  }



  // Renamed from _togglePower: This ONLY controls the timer now.
  // Renamed from _togglePower: This ONLY controls the timer now.
  _handleTimerControl(): void {
    this._validationMessages = [];

    // Check basic requirements
    if (!this._entitiesLoaded || !this.hass || !this.hass.states) {
      console.error("Timer-card: Cannot control timer. Entities not loaded.");
      return;
    }

    const sensorId = this._effectiveSensorEntity!;
    const sensor = this.hass.states[sensorId];

    if (!sensor) {
      console.error("Timer-card: Sensor entity not found.");
      return;
    }

    const isTimerActive = sensor.attributes.timer_state === 'active';

    // IF TIMER ACTIVE -> STOP TIMER (Decoupled: does NOT turn off switch interactions)
    if (isTimerActive) {
      this._cancelTimer();
      console.log(`Timer-card: Stopping active timer.`);
      return;
    }

    // IF TIMER IDLE -> START TIMER
    if (this._sliderValue > 0) {
      const unit = this._config?.slider_unit || 'min';
      this._startTimer(this._sliderValue, unit, 'slider');
      console.log(`Timer-card: Starting timer for ${this._sliderValue} ${unit}`);
    } else {
      console.warn("Timer-card: Slider value is 0, cannot start timer.");
    }
  }

  // Completely independent power toggle
  _handleIndependentPower(event: Event): void {
    event.preventDefault();
    event.stopPropagation();

    if (!this._entitiesLoaded || !this.hass || !this._effectiveSwitchEntity) {
      console.error("Timer-card: Cannot toggle power. Entities not loaded.");
      return;
    }

    const switchId = this._effectiveSwitchEntity;
    console.log(`Timer-card: Toggling independent power for ${switchId}`);

    // The backend says where the press goes, because only it knows what "on"
    // means for the device - a climate entity needs a stored hvac mode, and
    // homeassistant.toggle does not reach every domain. Never decided here
    // from the entity id: this bundle ships frozen, and a domain added to the
    // integration later must work without a card release. An older integration
    // publishes nothing, so absent means the direct toggle every version used.
    const sensor = this._effectiveSensorEntity
      ? this.hass.states[this._effectiveSensorEntity]
      : undefined;
    const route = sensor?.attributes?.power_toggle_route;

    if (route && route !== 'direct') {
      const entryId = this._getEntryId();
      if (!entryId) {
        console.error("Timer-card: Cannot toggle power without an entry_id.");
        return;
      }
      const active = sensor?.attributes?.device_active === true;
      this.hass.callService("simple_timer", "manual_power_toggle", {
        entry_id: entryId,
        action: active ? "turn_off" : "turn_on",
      }).catch(err => console.error("Timer-card: Error toggling power:", err));
      return;
    }

    this.hass.callService("homeassistant", "toggle", { entity_id: switchId })
      .catch(err => console.error("Timer-card: Error toggling power:", err));
  }

  _showMoreInfo(entityId?: string): void {
    if (!this._entitiesLoaded || !this.hass) {
      console.error("Timer-card: Cannot show more info. Entities not loaded.");
      return;
    }
    const sensorId = entityId || this._effectiveSensorEntity!;

    const event = new CustomEvent("hass-more-info", {
      bubbles: true,
      composed: true,
      detail: { entityId: sensorId }
    });
    this.dispatchEvent(event);
  }

  // Status entity for this instance, published by the backend on the runtime
  // sensor. Absent when the card is newer than the integration, in which case
  // callers fall back to the runtime sensor.
  get _effectiveStatusEntity(): string | null {
    if (!this.hass || !this._effectiveSensorEntity) return null;
    const sensor = this.hass.states[this._effectiveSensorEntity];
    const statusId = sensor?.attributes?.status_entity_id;
    if (typeof statusId !== 'string' || !this.hass.states[statusId]) return null;
    return statusId;
  }

  // Opens history on the status entity - a plain state timeline of
  // idle/active/scheduled, unlike the runtime sensor's sawtooth usage graph.
  _showHistory(): void {
    this._showMoreInfo(this._effectiveStatusEntity || undefined);
  }

  connectedCallback(): void {
    super.connectedCallback();

    // Restore slider value per instance
    const instanceId = this._config?.timer_instance_id || 'default';
    const savedValue = localStorage.getItem(`simple-timer-slider-${instanceId}`);

    if (savedValue) {
      //this._sliderValue = parseInt(savedValue);
    } else {
      // Fall back to last timer duration for this instance
      this._determineEffectiveEntities();
      if (this._entitiesLoaded && this.hass && this._effectiveSensorEntity) {
        const sensor = this.hass.states[this._effectiveSensorEntity];
        const lastDuration = sensor?.attributes?.timer_duration || 0;
        if (lastDuration > 0 && lastDuration <= 120) {
          this._sliderValue = lastDuration;
        }
      }
    }

    this._determineEffectiveEntities();
    this._updateLiveRuntime();
    this._syncServerTime(); // Sync time on load
    this._updateCountdown();
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this._stopCountdown();
    this._stopLiveRuntime();
    if (this._longPressTimer) {
      window.clearTimeout(this._longPressTimer);
    }
  }

  updated(changedProperties: Map<string | number | symbol, unknown>): void {
    if (changedProperties.has("hass") || changedProperties.has("_config")) {
      this._determineEffectiveEntities();
      this._updateLiveRuntime();
      this._syncServerTime();
      this._updateCountdown();
    }
  }



  _updateLiveRuntime(): void {
    this._liveRuntimeSeconds = 0;
  }

  _stopLiveRuntime(): void {
    this._liveRuntimeSeconds = 0;
  }

  _updateCountdown(): void {
    if (!this._entitiesLoaded || !this.hass || !this.hass.states) {
      this._stopCountdown();
      return;
    }
    const sensor = this.hass.states[this._effectiveSensorEntity!];

    if (!sensor || sensor.attributes.timer_state !== 'active') {
      this._stopCountdown();
      this._notificationSentForCurrentCycle = false;
      return;
    }

    const rawFinish = sensor.attributes.timer_finishes_at;
    if (rawFinish === undefined) {
      console.warn("Timer-card: timer_finishes_at is undefined for active timer. Stopping countdown.");
      this._stopCountdown();
      return;
    }
    // Always calculate the most current finish time
    const finishesAt = new Date(rawFinish).getTime();

    // If we have a running interval, check if we need to restart it (e.g. time added)
    // We store the target time on the instance to compare
    if (this._countdownInterval && this['_currentFinishesAt'] !== finishesAt) {
      this._stopCountdown(); // Restart with new time
    }

    // Store current target for next comparison
    this['_currentFinishesAt'] = finishesAt;

    if (!this._countdownInterval) {
      const update = () => {
        // Re-read latest finish time in case it changed (though restarting handles most cases, safe to be robust)
        // actually, restarting handling it is cleaner.
        // But to be super safe, let's just use the current captured finishesAt which is now fresh because we restarted.


        // Calculate drift-corrected now
        const now = new Date().getTime() + this._serverTimeOffset;
        const remaining = Math.max(0, Math.round((finishesAt - now) / 1000));

        // Only the block progress bar needs the raw value: the formatted string
        // changes just once per minute when show_seconds is off, which would
        // stall the bar. Skip the reactive write in countdown-only mode so we
        // don't force a render every second for nothing. Read the config here
        // rather than closing over it, so switching modes mid-timer applies.
        if ((this._config?.countdown_display || 'countdown') !== 'countdown') {
          this._remainingSeconds = remaining;
        }

        // Format countdown based on show_seconds setting
        const showSeconds = this._getShowSeconds();
        if (this._isCompact()) {
          this._timeRemaining = this._formatCompactRemaining(remaining, showSeconds);
        } else if (showSeconds) {
          const hours = Math.floor(remaining / 3600);
          const minutes = Math.floor((remaining % 3600) / 60);
          const seconds = remaining % 60;
          this._timeRemaining = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        } else {
          const hours = Math.floor(remaining / 3600);
          const minutes = Math.floor((remaining % 3600) / 60);
          this._timeRemaining = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
        }

        if (remaining === 0) {
          // Do not stop immediately, let the backend handle state change to idle
          // But we can stop the interval if we want.
          // keeping it running until state changes is usually safer to avoid 00:00 -> 00:01 glitches if backend is slow.
          // But existing logic stopped it.
          this._stopCountdown();
          if (!this._notificationSentForCurrentCycle) {
            this._notificationSentForCurrentCycle = true;
          }
        }
      };
      this._countdownInterval = window.setInterval(update, 500);
      update();
    }
  }

  _stopCountdown(): void {
    if (this._countdownInterval) {
      window.clearInterval(this._countdownInterval);
      this._countdownInterval = null;
    }
    this._timeRemaining = null;
    this._remainingSeconds = 0;
  }



  _isCompact(): boolean {
    return this._config?.layout === 'compact';
  }

  // Sections-view sizing. Compact is content-height ("auto") and full width
  // by default - half of a narrow section is too tight for a running timer -
  // but can be shrunk to half; under ~260px the card switches to its narrow
  // arrangement (see the container query in the compact styles). Classic
  // keeps the full-width default it always had.
  getGridOptions(): Record<string, unknown> {
    if (!this._isCompact()) {
      return { columns: 12, rows: 'auto' };
    }
    return { columns: 12, rows: 'auto', min_columns: 6 };
  }

  // Compact countdown. Drops the hours under one hour; with seconds hidden it
  // rounds UP, so a running timer never reads "0 min".
  _formatCompactRemaining(remaining: number, showSeconds: boolean): string {
    const pad = (n: number) => n.toString().padStart(2, '0');
    if (showSeconds) {
      const h = Math.floor(remaining / 3600);
      const m = Math.floor((remaining % 3600) / 60);
      const s = remaining % 60;
      return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
    }
    const totalMinutes = Math.ceil(remaining / 60);
    if (totalMinutes < 60) return `${totalMinutes} min`;
    const h = Math.floor(totalMinutes / 60);
    const m = totalMinutes % 60;
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  }

  // Compact daily usage: elapsed time, so it rounds DOWN.
  _formatCompactUsage(totalSeconds: number, showSeconds: boolean): string {
    const t = Math.max(0, Math.floor(totalSeconds));
    const h = Math.floor(t / 3600);
    const m = Math.floor((t % 3600) / 60);
    const s = t % 60;
    if (showSeconds) {
      if (h > 0) return `${h}h ${m}m ${s}s`;
      if (m > 0) return `${m}m ${s}s`;
      return `${s}s`;
    }
    if (h > 0) return m > 0 ? `${h}h ${m}m` : `${h}h`;
    return `${m} min`;
  }

  // Wall-clock time in the user's HA 12/24h setting. Adds the weekday when it
  // is not today, and the date when it is a week or more away.
  // The user's HA language and 12/24h choice, for toLocale*String. Shared by
  // every clock time the card shows, so they never disagree.
  _clockLocale(): { lang: string | string[]; hourOpt: { hour12?: boolean } } {
    const locale = (this.hass as any)?.locale;
    const lang = locale?.language || [];
    if (locale?.time_format === '12') return { lang, hourOpt: { hour12: true } };
    if (locale?.time_format === '24') return { lang, hourOpt: { hour12: false } };
    return { lang, hourOpt: {} }; // "language" / "system": the locale decides
  }

  _formatClockTime(iso: string): string {
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return '';
      const { lang, hourOpt } = this._clockLocale();
      const time = d.toLocaleTimeString(lang, { hour: '2-digit', minute: '2-digit', ...hourOpt });
      const now = new Date();
      if (d.toDateString() === now.toDateString()) return time;
      const daysAway = (d.getTime() - now.getTime()) / 86400000;
      const day = daysAway < 6
        ? d.toLocaleDateString(lang, { weekday: 'short' })
        : d.toLocaleDateString(lang, { month: 'short', day: 'numeric' });
      return `${day} ${time}`;
    } catch {
      return '';
    }
  }

  // Get show_seconds from the sensor attributes (backend config)
  _getShowSeconds(): boolean {
    if (!this._entitiesLoaded || !this.hass || !this._effectiveSensorEntity) {
      return false;
    }

    const sensor = this.hass.states[this._effectiveSensorEntity];
    // The backend will set this attribute based on the config entry
    return sensor?.attributes?.show_seconds || false;
  }

  _handleUsageClick(event: Event): void {
    // Prevent default to avoid conflicts with touch events
    event.preventDefault();
    // Only show more info if it wasn't a long press
    if (!this._isLongPress) {
      this._showMoreInfo();
    }
    this._isLongPress = false;
  }

  _startLongPress(event: Event): void {
    event.preventDefault();
    this._isLongPress = false;

    this._longPressTimer = window.setTimeout(() => {
      this._isLongPress = true;
      this._resetUsage();
      // Add haptic feedback on mobile
      if ('vibrate' in navigator) {
        navigator.vibrate(50);
      }
    }, 800); // 800ms long press duration
  }

  _endLongPress(event?: Event): void {
    if (event) {
      event.preventDefault();
    }
    if (this._longPressTimer) {
      window.clearTimeout(this._longPressTimer);
      this._longPressTimer = null;
    }
  }

  // --- Countdown long press: opens history ---------------------------------
  // Bound to both the countdown text and the progress bar, since either can be
  // hidden independently and the gesture must survive whichever remains.

  _startCountdownLongPress(event: Event): void {
    event.preventDefault();

    this._countdownLongPressTimer = window.setTimeout(() => {
      this._showHistory();
      if ('vibrate' in navigator) {
        navigator.vibrate(50);
      }
    }, 800); // Matches the daily-usage long press duration
  }

  _endCountdownLongPress(event?: Event): void {
    if (event) {
      event.preventDefault();
    }
    if (this._countdownLongPressTimer) {
      window.clearTimeout(this._countdownLongPressTimer);
      this._countdownLongPressTimer = null;
    }
    this._countdownTouchStartPosition = null;
  }

  _handleCountdownTouchStart(event: TouchEvent): void {
    const touch = event.touches[0];
    this._countdownTouchStartPosition = { x: touch.clientX, y: touch.clientY };

    this._countdownLongPressTimer = window.setTimeout(() => {
      this._showHistory();
      if ('vibrate' in navigator) {
        navigator.vibrate(50);
      }
    }, 800);
  }

  _handleCountdownTouchMove(event: TouchEvent): void {
    // Cancel if the finger drifts - treats the gesture as a scroll, not a hold.
    if (!this._countdownTouchStartPosition || !this._countdownLongPressTimer) return;

    const touch = event.touches[0];
    const deltaX = Math.abs(touch.clientX - this._countdownTouchStartPosition.x);
    const deltaY = Math.abs(touch.clientY - this._countdownTouchStartPosition.y);

    if (deltaX > 10 || deltaY > 10) {
      this._endCountdownLongPress();
    }
  }

  _handlePowerClick(event: Event): void {
    // Only handle mouse clicks, not touch events
    if (event.type === 'click' && !this._isLongPress) {
      event.preventDefault();
      event.stopPropagation();
      this._handleTimerControl();
    }
    this._isLongPress = false;
  }

  _handleTouchEnd(event: TouchEvent): void {
    event.preventDefault();
    event.stopPropagation();

    if (this._longPressTimer) {
      window.clearTimeout(this._longPressTimer);
      this._longPressTimer = null;
    }

    // Check if the touch moved too much (sliding)
    let hasMoved = false;
    if (this._touchStartPosition && event.changedTouches[0]) {
      const touch = event.changedTouches[0];
      const deltaX = Math.abs(touch.clientX - this._touchStartPosition.x);
      const deltaY = Math.abs(touch.clientY - this._touchStartPosition.y);
      const moveThreshold = 10; // pixels

      hasMoved = deltaX > moveThreshold || deltaY > moveThreshold;
    }

    // Only trigger if it's not a long press AND the touch didn't move much
    if (!this._isLongPress && !hasMoved) {
      this._showMoreInfo();
    }

    this._isLongPress = false;
    this._touchStartPosition = null;
  }

  _handleTouchStart(event: TouchEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this._isLongPress = false;

    // Record the initial touch position
    const touch = event.touches[0];
    this._touchStartPosition = { x: touch.clientX, y: touch.clientY };

    this._longPressTimer = window.setTimeout(() => {
      this._isLongPress = true;
      this._resetUsage();
      if ('vibrate' in navigator) {
        navigator.vibrate(50);
      }
    }, 800);
  }

  _resetUsage(): void {
    this._validationMessages = [];

    if (!this._entitiesLoaded || !this.hass || !this.hass.callService) {
      console.error("Timer-card: Cannot reset usage. Entities not loaded or callService unavailable.");
      return;
    }

    const entryId = this._getEntryId();
    if (!entryId) {
      console.error("Timer-card: Entry ID not found for resetting usage.");
      return;
    }

    // Show confirmation dialog
    if (!confirm("Reset daily usage to 00:00?\n\nThis action cannot be undone.")) {
      return;
    }

    this.hass.callService(DOMAIN, "reset_daily_usage", { entry_id: entryId })
      .then(() => {
        console.log("Timer-card: Daily usage reset successfully");
      })
      .catch(error => {
        console.error("Timer-card: Error resetting daily usage:", error);
      });
  }

  _handleSliderChange(event: Event): void {
    const slider = event.target as HTMLInputElement;
    this._sliderValue = parseInt(slider.value);

    const instanceId = this._config?.timer_instance_id || 'default';
    localStorage.setItem(`simple-timer-slider-${instanceId}`, this._sliderValue.toString());
  }

  _getCurrentTimerMode(): string {
    if (!this._entitiesLoaded || !this.hass || !this._effectiveSensorEntity) {
      return 'normal';
    }

    const sensor = this.hass.states[this._effectiveSensorEntity];
    return sensor?.attributes?.reverse_mode ? 'reverse' : 'normal';
  }

  _getSliderStyle(): string {
    const thumbColor = this._config?.slider_thumb_color || '#2ab69c';
    const backgroundColor = this._config?.slider_background_color || 'var(--secondary-background-color)';
    const borderColor = this._config?.slider_thumb_color ?
      this._adjustColorBrightness(thumbColor, 20) : '#4bd9bf';

    // Convert hex to RGB for rgba() usage in box-shadow
    const hexToRgb = (hex: string) => {
      const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
      return result ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16)
      } : { r: 42, g: 182, b: 156 }; // fallback to default
    };

    const rgb = hexToRgb(thumbColor);
    const borderRgb = hexToRgb(borderColor);

    return `
      .timer-slider {
        background: ${backgroundColor} !important;
      }
      .timer-slider::-webkit-slider-thumb {
        background: ${thumbColor} !important;
        border: 2px solid ${borderColor} !important;
        box-shadow: 
          0 0 0 2px rgba(${borderRgb.r}, ${borderRgb.g}, ${borderRgb.b}, 0.3),
          0 0 8px rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.4),
          0 2px 4px rgba(0, 0, 0, 0.2) !important;
      }
      .timer-slider::-webkit-slider-thumb:hover {
        background: ${this._adjustColorBrightness(thumbColor, -10)} !important;
        border: 2px solid ${borderColor} !important;
        box-shadow: 
          0 0 0 3px rgba(${borderRgb.r}, ${borderRgb.g}, ${borderRgb.b}, 0.4),
          0 0 12px rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.6),
          0 2px 6px rgba(0, 0, 0, 0.3) !important;
      }
      .timer-slider::-webkit-slider-thumb:active {
        background: ${this._adjustColorBrightness(thumbColor, -20)} !important;
        border: 2px solid ${borderColor} !important;
        box-shadow: 
          0 0 0 4px rgba(${borderRgb.r}, ${borderRgb.g}, ${borderRgb.b}, 0.5),
          0 0 16px rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.7),
          0 2px 8px rgba(0, 0, 0, 0.4) !important;
      }
      .timer-slider::-moz-range-thumb {
        background: ${thumbColor} !important;
        border: 2px solid ${borderColor} !important;
        box-shadow: 
          0 0 0 2px rgba(${borderRgb.r}, ${borderRgb.g}, ${borderRgb.b}, 0.3),
          0 0 8px rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.4),
          0 2px 4px rgba(0, 0, 0, 0.2) !important;
      }
      .timer-slider::-moz-range-thumb:hover {
        background: ${this._adjustColorBrightness(thumbColor, -10)} !important;
        border: 2px solid ${borderColor} !important;
        box-shadow: 
          0 0 0 3px rgba(${borderRgb.r}, ${borderRgb.g}, ${borderRgb.b}, 0.4),
          0 0 12px rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.6),
          0 2px 6px rgba(0, 0, 0, 0.3) !important;
      }
      .timer-slider::-moz-range-thumb:active {
        background: ${this._adjustColorBrightness(thumbColor, -20)} !important;
        border: 2px solid ${borderColor} !important;
        box-shadow: 
          0 0 0 4px rgba(${borderRgb.r}, ${borderRgb.g}, ${borderRgb.b}, 0.5),
          0 0 16px rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.7),
          0 2px 8px rgba(0, 0, 0, 0.4) !important;
      }
    `;
  }

  _getTimerButtonStyle(): string {
    const fontColor = this._config?.timer_button_font_color;
    const backgroundColor = this._config?.timer_button_background_color;

    if (!fontColor && !backgroundColor) {
      return ''; // No custom styling needed
    }

    let styles = '';

    if (fontColor || backgroundColor) {
      styles += `
        .timer-button {
          ${fontColor ? `color: ${fontColor} !important;` : ''}
          ${backgroundColor ? `background-color: ${backgroundColor} !important;` : ''}
        }
      `;
    }

    return styles;
  }

  _getPowerButtonStyle(): string {
    const powerBg = this._config?.power_button_background_color;
    const powerIcon = this._config?.power_button_icon_color;
    const stateBg = this._config?.entity_state_button_background_color;
    const stateIcon = this._config?.entity_state_button_icon_color;
    const stateBgOn = this._config?.entity_state_button_background_color_on;
    const stateIconOn = this._config?.entity_state_button_icon_color_on;

    if (!powerBg && !powerIcon && !stateBg && !stateIcon && !stateBgOn && !stateIconOn) {
      return ''; // No custom styling needed
    }

    let styles = '';

    // Timer Control Button (Start/Stop)
    if (powerBg || powerIcon) {
      styles += `
        .timer-control-button {
          ${powerBg ? `background-color: ${powerBg} !important;` : ''}
        }
        .timer-control-button ha-icon[icon] {
          ${powerIcon ? `color: ${powerIcon} !important;` : ''}
        }
        .timer-control-button.reverse ha-icon[icon] {
          ${powerIcon ? `color: ${powerIcon} !important;` : ''}
        }
      `;
    }

    // Entity State Button
    // Default (Off) State
    if (stateBg || stateIcon) {
      styles += `
        .entity-state-button {
          ${stateBg ? `background-color: ${stateBg} !important;` : ''}
        }
        .entity-state-button ha-icon[icon] {
          ${stateIcon ? `color: ${stateIcon} !important;` : ''}
        }
        .entity-state-button.reverse ha-icon[icon] {
          ${stateIcon ? `color: ${stateIcon} !important;` : ''}
        }
      `;
    }

    // On State
    if (stateBgOn || stateIconOn) {
      styles += `
        .entity-state-button.on {
          ${stateBgOn ? `background-color: ${stateBgOn} !important;` : ''}
        }
        .entity-state-button.on ha-icon[icon] {
          ${stateIconOn ? `color: ${stateIconOn} !important;` : ''}
        }
        /* Ensure specific override if needed */
        .entity-state-button.on.reverse ha-icon[icon] {
          ${stateIconOn ? `color: ${stateIconOn} !important;` : ''}
        }
      `;
    }

    return styles;
  }

  _adjustColorBrightness(color: string, percent: number): string {
    const num = parseInt(color.replace("#", ""), 16);
    const amt = Math.round(2.55 * percent);
    const R = Math.max(0, Math.min(255, (num >> 16) + amt));
    const G = Math.max(0, Math.min(255, (num >> 8 & 0x00FF) + amt));
    const B = Math.max(0, Math.min(255, (num & 0x0000FF) + amt));
    return "#" + (0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1);
  }

  async _fetchLovelaceConfig(): Promise<any> {
    if (!this.hass) return null;
    try {
      const urlPath = this._getDashboardUrlPath();
      return await this.hass.callWS({
        type: 'lovelace/config',
        url_path: urlPath
      });
    } catch (e) {
      console.warn("TimerCard: Failed to fetch lovelace config", e);
      return null;
    }
  }

  _getDashboardUrlPath(): string | null {
    const path = window.location.pathname;
    const parts = path.split('/');
    if (parts.length > 1 && parts[1] !== 'lovelace') {
      return parts[1];
    }
    return null;
  }



  _renderPreview() {
    if (this._isCompact()) return this._renderCompactPreview();
    const previewButtons = [15, 30, 60, 90, 120];
    const previewMode = this._config?.countdown_display || 'countdown';
    const previewShowCountdown = previewMode !== 'progress';
    const previewShowProgress = previewMode !== 'countdown';
    const previewActiveBlocks = Math.ceil(TOTAL_BLOCKS * 0.65);
    return html`
      <style>
        ${this._getSliderStyle()}
        ${this._getTimerButtonStyle()}
        ${this._getPowerButtonStyle()}
      </style>
      <ha-card>
        <div class="card-header ${this._config?.card_title ? 'has-title' : ''}">
          <div class="card-title">${this._config?.card_title || ''}</div>
        </div>
        <div class="card-content">
          <div class="entity-state-button">
            <ha-icon icon="${this._config?.entity_state_icon || this._config?.power_button_icon || 'mdi:power'}"></ha-icon>
          </div>
          <div class="countdown-section">
            ${previewShowCountdown ? html`<div class="countdown-display">00:10:00</div>` : ''}
            ${previewShowProgress ? html`
              <div class="block-progress-bar ${!previewShowCountdown ? 'solo' : ''}">
                ${Array.from({ length: TOTAL_BLOCKS }, (_, index) => html`
                  <div class="progress-block ${index < previewActiveBlocks ? 'active' : ''}"></div>
                `)}
              </div>
            ` : ''}
            <div class="daily-usage-display">Daily usage: 00:03:20</div>
          </div>
          <div class="slider-row">
            <input type="range" min="0" step="1" max="${this._config?.slider_max || 120}" value="10" class="timer-slider" />
            <div class="slider-right-group">
              <span class="slider-label">10 ${this._config?.slider_unit || 'min'}</span>
              <div class="timer-control-button">
                <ha-icon icon="mdi:play"></ha-icon>
              </div>
            </div>
          </div>
        </div>
        <div class="button-grid">
          ${previewButtons.map(m => html`
            <div class="timer-button">
              <div class="timer-button-value">${m}</div>
              <div class="timer-button-unit">min</div>
            </div>
          `)}
        </div>
      </ha-card>
    `;
  }

  render() {

    let message: string | null = null;
    let isWarning = false;

    if (!this.hass) {
      message = "Home Assistant object (hass) not available. Card cannot load.";
      isWarning = true;
    } else if (!this._entitiesLoaded) {
      if (this._config?.timer_instance_id && this._config.timer_instance_id !== 'default') {
        const configuredSensorState = Object.values(this.hass.states).find(
          (state: HAState) => state.attributes.entry_id === this._config!.timer_instance_id && state.entity_id.startsWith('sensor.')
        ) as HAState | undefined;

        if (!configuredSensorState) {
          message = `Timer instance '${this._config.timer_instance_id}' not found. It may have been removed, or the Simple Timer integration is not loaded yet. Check Settings → Devices & Services, or pick another instance in the card editor.`;
          isWarning = true;
        } else if (typeof configuredSensorState.attributes.switch_entity_id !== 'string' || !(configuredSensorState.attributes.switch_entity_id && this.hass.states[configuredSensorState.attributes.switch_entity_id])) {
          message = `Timer Control Instance '${this._config.timer_instance_id}' linked to missing or invalid device '${configuredSensorState.attributes.switch_entity_id}'. Please check instance configuration.`;
          isWarning = true;
        } else {
          message = "Loading Timer Control Card. Please wait...";
          isWarning = false;
        }
      } else if (this._config?.sensor_entity) {
        const configuredSensorState = this.hass.states[this._config.sensor_entity];
        if (!configuredSensorState) {
          message = `Configured Timer Control Sensor '${this._config.sensor_entity}' not found. Please select a valid instance in the card editor.`;
          isWarning = true;
        } else if (typeof configuredSensorState.attributes.switch_entity_id !== 'string' || !(configuredSensorState.attributes.switch_entity_id && this.hass.states[configuredSensorState.attributes.switch_entity_id])) {
          message = `Configured Timer Control Sensor '${this._config.sensor_entity}' is invalid or its linked device '${configuredSensorState.attributes.switch_entity_id}' is missing. Please select a valid instance.`;
          isWarning = true;
        } else {
          message = "Loading Timer Control Card. Please wait...";
          isWarning = false;
        }
      } else {
        return this._renderPreview();
      }
    }

    if (message) {
      return html`<ha-card><div class="${isWarning ? 'warning' : 'placeholder'}">${message}</div></ha-card>`;
    }

    const timerSwitch = this.hass!.states[this._effectiveSwitchEntity!];
    const sensor = this.hass!.states[this._effectiveSensorEntity!];

    // The backend resolves this now, because "running" is not the same string
    // in every domain - a climate entity's state is its hvac mode. The
    // fallback keeps this card working against an older backend that does not
    // publish the attribute yet.
    const isOn = typeof sensor.attributes.device_active === 'boolean'
      ? sensor.attributes.device_active
      : timerSwitch.state === 'on';
    const isTimerActive = sensor.attributes.timer_state === 'active';
    const timerDurationInMinutes = sensor.attributes.timer_duration || 0;
    const isManualOn = isOn && !isTimerActive;
    const isReverseMode = sensor.attributes.reverse_mode;

    const committedSeconds = parseFloat(sensor.state as string) || 0;

    // Format time based on show_seconds setting from backend
    const showSeconds = this._getShowSeconds();
    let dailyUsageFormatted: string;
    let countdownDisplay: string;

    if (showSeconds) {
      // Show full HH:MM:SS format
      const totalSecondsInt = Math.floor(committedSeconds);
      const hours = Math.floor(totalSecondsInt / 3600);
      const minutes = Math.floor((totalSecondsInt % 3600) / 60);
      const seconds = totalSecondsInt % 60;
      dailyUsageFormatted = `Daily usage: ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;

      // Countdown display - show active countdown or 00:00:00
      countdownDisplay = this._timeRemaining || '00:00:00';
    } else {
      // Show HH:MM format (original behavior)
      const totalMinutes = Math.floor(committedSeconds / 60);
      const hours = Math.floor(totalMinutes / 60);
      const minutes = totalMinutes % 60;
      dailyUsageFormatted = `Daily usage: ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;

      // Countdown display - show active countdown or 00:00
      countdownDisplay = this._timeRemaining || '00:00';
    }

    const watchdogMessage = sensor.attributes.watchdog_message;

    // Block-style progress bar. timer_duration is in minutes (and grows when
    // time is added), so convert it to seconds before comparing against the
    // remaining time derived from timer_finishes_at. The 500ms countdown tick
    // updates _remainingSeconds, which is what re-runs this render.
    const totalDurationSeconds = timerDurationInMinutes * 60;
    const rawFinishesAt = sensor.attributes.timer_finishes_at;
    let remainingPercentage = 0;

    if (isTimerActive && totalDurationSeconds > 0 && rawFinishesAt) {
      const nowMs = new Date().getTime() + this._serverTimeOffset;
      const remainingSeconds = Math.max(0, (new Date(rawFinishesAt).getTime() - nowMs) / 1000);
      remainingPercentage = Math.min(1, remainingSeconds / totalDurationSeconds);
    }

    // Keep at least one lit block while the timer is still running.
    const activeBlocksCount = remainingPercentage > 0
      ? Math.max(1, Math.ceil(remainingPercentage * TOTAL_BLOCKS))
      : 0;

    if (this._isCompact()) {
      return this._renderCompact(sensor, timerSwitch, {
        isOn, isTimerActive, isReverseMode: !!isReverseMode, committedSeconds,
        showSeconds, watchdogMessage, remainingPercentage, timerDurationInMinutes,
      });
    }

    const countdownDisplayMode = this._config?.countdown_display || 'countdown';
    const showCountdownText = countdownDisplayMode !== 'progress';
    const showProgressBar = countdownDisplayMode !== 'countdown';


    return html`
      <style>
        ${this._getSliderStyle()}
        ${this._getTimerButtonStyle()}
        ${this._getPowerButtonStyle()}
      </style>
      <ha-card>
        <div class="card-header ${this._config?.card_title ? 'has-title' : ''}">
						<div class="card-title">${this._config?.card_title || ''}</div>
				</div>

        ${watchdogMessage ? html`
          <div class="status-message warning watchdog-banner">
            <ha-icon icon="mdi:alert-outline" class="status-icon"></ha-icon>
            <span class="status-text">${watchdogMessage}</span>
          </div>
        ` : ''}


        <div class="card-content">

          
          <!-- Independent Power Toggle (Always Visible now) -->
          <div class="entity-state-button ${isOn ? 'on' : ''}"
                @click=${this._handleIndependentPower}
                title="Toggle Power (Independent)">
            <ha-icon icon="${this._config?.entity_state_icon || this._config?.power_button_icon || 'mdi:power'}"></ha-icon>
          </div>
          
          ${'' /* Removed the conditional power-button-top-right that was here */}

          <!-- Countdown Display Section -->
          <div class="countdown-section">
            ${showCountdownText ? html`
              <div class="countdown-display ${isTimerActive ? 'active' : ''} ${isReverseMode ? 'reverse' : ''}"
                   @mousedown=${this._startCountdownLongPress}
                   @mouseup=${this._endCountdownLongPress}
                   @mouseleave=${this._endCountdownLongPress}
                   @touchstart=${this._handleCountdownTouchStart}
                   @touchmove=${this._handleCountdownTouchMove}
                   @touchend=${this._endCountdownLongPress}
                   @touchcancel=${this._endCountdownLongPress}
                   title="Hold to show history">
                ${countdownDisplay}
              </div>
            ` : ''}

            <!-- Block Progress Bar -->
            ${showProgressBar ? html`
              <div class="block-progress-bar ${isReverseMode ? 'reverse' : ''} ${!showCountdownText ? 'solo' : ''}"
                   @mousedown=${this._startCountdownLongPress}
                   @mouseup=${this._endCountdownLongPress}
                   @mouseleave=${this._endCountdownLongPress}
                   @touchstart=${this._handleCountdownTouchStart}
                   @touchmove=${this._handleCountdownTouchMove}
                   @touchend=${this._endCountdownLongPress}
                   @touchcancel=${this._endCountdownLongPress}
                   title="Hold to show history">
                ${Array.from({ length: TOTAL_BLOCKS }, (_, index) => {
      const isActiveBlock = index < activeBlocksCount;
      const isLeadBlock = isTimerActive && isActiveBlock && index === activeBlocksCount - 1;
      return html`
                    <div class="progress-block ${isActiveBlock ? 'active' : ''} ${isLeadBlock ? 'lead' : ''}"></div>
                  `;
    })}
              </div>
            ` : ''}

						${this._config?.show_daily_usage !== false ? html`
							<div class="daily-usage-display"
									 @click=${this._handleUsageClick}
									 @mousedown=${this._startLongPress}
									 @mouseup=${this._endLongPress}
									 @mouseleave=${this._endLongPress}
									 @touchstart=${this._handleTouchStart}
									 @touchend=${this._handleTouchEnd}
									 @touchcancel=${this._endLongPress}
									 title="Click to show more info, hold to reset daily usage">
								${dailyUsageFormatted}
            </div>
						` : ''}
          </div>

          <!-- Slider Row -->
          ${!this._config?.hide_slider ? html`
          <div class="slider-row">
            <input
              type="range"
              min="0"
              step="1"
              max="${this._config?.slider_max || 120}"
              .value=${this._sliderValue.toString()}
              @input=${this._handleSliderChange}
              class="timer-slider"
            />
            
            <div class="slider-right-group">
                <span class="slider-label">${this._sliderValue} ${this._config?.slider_unit || 'min'}</span>
                
                <div class="timer-control-button ${isTimerActive ? 'active' : ''} ${!isTimerActive && this._sliderValue === 0 ? 'disabled' : ''}" 
                     @click=${!isTimerActive && this._sliderValue === 0 ? null : this._handleTimerControl}
                     title="${isTimerActive ? 'Stop Timer' : (this._sliderValue === 0 ? 'Set time to start' : 'Start Timer')}">
                  <ha-icon icon="${isTimerActive ? 'mdi:stop' : (this._sliderValue === 0 ? 'mdi:stop' : 'mdi:play')}"></ha-icon>
                </div>
            </div>
          </div>
          ` : ''}

          </div>
          
           <!-- Timer Buttons Grid -->
           ${this.buttons.length > 0 || (this._config?.hide_slider && isTimerActive) ? html`
          <div class="button-grid">
            ${this.buttons.map(button => {
      // Skip default timer buttons from grid
      if (button.isDefault) return '';

      // Highlight if current duration matches button (visual indicator only)
      const isActive = isTimerActive && Math.abs(timerDurationInMinutes - button.minutesEquivalent) < 0.001 && sensor.attributes.timer_start_method === 'button';

      // Buttons are NO LONGER disabled when timer is active - they now Extend
      return html`
                <div class="timer-button ${isActive ? 'active' : ''}" 
                     @click=${() => {
          if (isTimerActive) {
            this._addTimer(button.displayValue, button.unit);
          } else {
            this._startTimer(button.displayValue, button.unit, 'button');
          }
        }}>
                  <div class="timer-button-value">${isTimerActive ? '+' : ''}${button.displayValue}</div>
                  <div class="timer-button-unit">${button.labelUnit}</div>
                </div>
              `;
    })}
            
            ${this._config?.hide_slider ? html`
                <!-- Stop Button appended to grid when slider is hidden -->
                <div class="timer-button stop-button ${isTimerActive ? 'active' : 'disabled'}" 
                     style="color: var(--primary-color);"
                     @click=${isTimerActive ? this._handleTimerControl : null}>
                  <div class="timer-button-value">
                    <ha-icon icon="mdi:stop"></ha-icon>
                  </div>
                  <div class="timer-button-unit">Stop</div>
                </div>
            ` : ''}
          </div>
          ` : ''}

          ${this._config?.show_schedule ? this._renderSchedulePanel(sensor) : ''}
        </div>

        ${this._validationMessages.length > 0 ? html`
          <div class="status-message warning">
            <ha-icon icon="mdi:alert-outline" class="status-icon"></ha-icon>
            <div class="status-text">
                ${this._validationMessages.map(msg => html`<div>${msg}</div>`)}
            </div>
          </div>
        ` : ''}
      </ha-card>
    `;
  }

  // ---- Compact layout -----------------------------------------------------
  // One tile-style row (icon, name, status, action), preset buttons under it,
  // and the slider + schedule behind a chevron. Reuses every classic handler;
  // only the markup and formatting differ.

  _shortUnit(unit: string): string {
    return ({ s: 's', min: 'm', h: 'h', d: 'd' } as Record<string, string>)[unit] ?? unit;
  }

  _startFromCompactSlider(): void {
    if (this._sliderValue <= 0) return;
    this._startTimer(this._sliderValue, this._config?.slider_unit || 'min', 'slider');
    this._compactExpanded = false;
  }

  // Stop only. Unlike _handleTimerControl it never falls through to "start":
  // a timer that ended a moment before the tap landed must not be restarted
  // for the slider length. Nor does it cancel an idle timer, which for a
  // just-finished delayed start would switch the device back off.
  _stopFromCompact(): void {
    const sensor = this._effectiveSensorEntity ? this.hass?.states[this._effectiveSensorEntity] : undefined;
    if (sensor?.attributes?.timer_state !== 'active') return;
    this._cancelTimer();
  }

  // Collapse the chevron panel when a timer starts or a schedule is armed,
  // whatever started it (chip, slider, schedule form, automation), so it does
  // not pop back open when that ends. Only on the transition: the panel may
  // be opened again while a schedule is armed.
  _lastCompactStatus: string | null = null;

  willUpdate(changed: Map<string | number | symbol, unknown>): void {
    super.willUpdate(changed);
    if (!this._isCompact() || !this.hass || !this._effectiveSensorEntity) return;
    const a = this.hass.states[this._effectiveSensorEntity]?.attributes;
    if (!a) return;
    const status = a.timer_state === 'active' ? 'active' : a.schedule_state === 'armed' ? 'armed' : 'idle';
    if (status !== this._lastCompactStatus) {
      if (this._lastCompactStatus !== null && status !== 'idle') this._compactExpanded = false;
      this._lastCompactStatus = status;
    }
  }

  // Remaining time for the compact row. Falls back to computing it from
  // timer_finishes_at when the ticking string is not there yet (first render)
  // or has been cleared at 0 while HA still reports the timer active.
  _compactTimeText(sensor: HAState, showSeconds: boolean): string {
    if (this._timeRemaining) return this._timeRemaining;
    const finishesAt = sensor.attributes.timer_finishes_at;
    const remaining = finishesAt
      ? Math.max(0, Math.round((new Date(finishesAt).getTime() - (Date.now() + this._serverTimeOffset)) / 1000))
      : 0;
    return this._formatCompactRemaining(remaining, showSeconds);
  }

  _renderCompactIcon(timerSwitch: HAState | undefined) {
    const override = this._config?.entity_state_icon || this._config?.power_button_icon || undefined;
    // ha-state-icon gives the device's own icon (a fan, a water heater). It is
    // HA's element and may not be loaded on every page, so fall back to
    // ha-icon, which every card here already relies on.
    if (timerSwitch && customElements.get('ha-state-icon')) {
      return html`<ha-state-icon .hass=${this.hass} .stateObj=${timerSwitch} .icon=${override}></ha-state-icon>`;
    }
    return html`<ha-icon icon=${override || timerSwitch?.attributes?.icon || 'mdi:power'}></ha-icon>`;
  }

  _getCompactStyle(): string {
    const c = this._config;
    if (!c) return '';
    const rules: string[] = [];
    const decl = (pairs: [string, string | null | undefined][]) =>
      pairs.filter(([, v]) => v).map(([k, v]) => `${k}: ${v} !important;`).join(' ');

    if (c.timer_button_font_color || c.timer_button_background_color) {
      rules.push(`.c-chip { ${decl([['color', c.timer_button_font_color], ['background', c.timer_button_background_color]])} }`);
    }
    if (c.power_button_background_color || c.power_button_icon_color) {
      rules.push(`.c-act.ctl, .c-start { ${decl([['background', c.power_button_background_color], ['color', c.power_button_icon_color]])} }`);
    }
    if (c.entity_state_button_background_color || c.entity_state_button_icon_color) {
      rules.push(`.c-icon { ${decl([['background', c.entity_state_button_background_color], ['color', c.entity_state_button_icon_color]])} }`);
    }
    if (c.entity_state_button_background_color_on || c.entity_state_button_icon_color_on) {
      rules.push(`.c-icon.on { ${decl([['background', c.entity_state_button_background_color_on], ['color', c.entity_state_button_icon_color_on]])} }`);
    }
    if (c.slider_thumb_color || c.slider_background_color) {
      rules.push(`.c-range { ${decl([['--st-range-fill', c.slider_thumb_color], ['--st-range-track', c.slider_background_color]])} }`);
    }
    return rules.join('\n');
  }

  _renderCompact(sensor: HAState, timerSwitch: HAState, s: {
    isOn: boolean; isTimerActive: boolean; isReverseMode: boolean; committedSeconds: number;
    showSeconds: boolean; watchdogMessage: string | undefined; remainingPercentage: number;
    timerDurationInMinutes: number;
  }) {
    const cfg = this._config!;
    const chips = this.buttons.filter(b => !b.isDefault);
    const displayMode = cfg.countdown_display || 'countdown';
    const showTime = s.isTimerActive && displayMode !== 'progress';
    const showBar = s.isTimerActive && displayMode !== 'countdown';
    const expandable = !cfg.hide_slider || !!cfg.show_schedule;
    const isArmed = !s.isTimerActive && sensor.attributes.schedule_state === 'armed' && !!sensor.attributes.scheduled_start;
    // While a schedule is armed the row already shows it, so the panel holds
    // only the slider. It is offered only when no preset buttons exist: they
    // already start a timer, and without them nothing else could.
    const canExpand = isArmed ? (!cfg.hide_slider && chips.length === 0) : expandable;
    const showPanel = this._compactExpanded && canExpand && !s.isTimerActive;
    // `reverse` colors the RUNNING timer (the sensor's sticky attribute
    // describes the timer in progress). `startsReverse` colors controls that
    // START one, and must match what _startTimer will actually send.
    const reverse = s.isReverseMode ? 'reverse' : '';
    const startsReverse = cfg.reverse_mode && !sensor.attributes.default_timer_enabled ? 'reverse' : '';
    const timeText = showTime ? this._compactTimeText(sensor, s.showSeconds) : '';
    const chevron = html`
      <button type="button" class="c-act ghost ${isArmed ? 'c-armed-chev' : ''}"
              @click=${() => { this._compactExpanded = !this._compactExpanded; }}
              aria-label=${this._compactExpanded ? 'Fewer options' : 'More options'}
              aria-expanded=${this._compactExpanded ? 'true' : 'false'}>
        <ha-icon icon=${this._compactExpanded ? 'mdi:chevron-up' : 'mdi:chevron-down'}></ha-icon>
      </button>`;
    const name = cfg.card_title || timerSwitch?.attributes?.friendly_name || 'Simple Timer';
    const sliderUnit = cfg.slider_unit || 'min';

    // Second line
    const usage = cfg.show_daily_usage !== false
      ? `${this._formatCompactUsage(s.committedSeconds, s.showSeconds)} today`
      : null;
    let lead: string;
    let withUsage = true;
    if (s.isTimerActive) {
      // Only the end time: the icon already shows on/off, and usage matters
      // when idle, not while a countdown runs. Keeps the line from truncating.
      const at = sensor.attributes.timer_finishes_at ? this._formatClockTime(sensor.attributes.timer_finishes_at) : '';
      lead = at
        ? (s.isReverseMode ? `Turns on at ${at}` : `Until ${at}`)
        : (s.isOn ? 'On' : 'Off');
      withUsage = false;
    } else if (isArmed) {
      const repeatDays = this._scheduleRepeatDays(sensor);
      lead = [
        this._formatClockTime(sensor.attributes.scheduled_start),
        `${sensor.attributes.scheduled_duration} ${sensor.attributes.scheduled_unit || 'min'}`,
        repeatDays,
      ].filter(Boolean).join(' · ');
      withUsage = false;
    } else {
      lead = s.isOn ? 'On' : 'Off';
    }

    // Right side of the main row
    let action;
    if (s.isTimerActive) {
      action = html`
        ${showTime ? html`
          <div class="c-time ${reverse}"
               @mousedown=${this._startCountdownLongPress}
               @mouseup=${this._endCountdownLongPress}
               @mouseleave=${this._endCountdownLongPress}
               @touchstart=${this._handleCountdownTouchStart}
               @touchmove=${this._handleCountdownTouchMove}
               @touchend=${this._endCountdownLongPress}
               @touchcancel=${this._endCountdownLongPress}
               title="Hold to show history">${timeText}</div>
        ` : ''}
        <button type="button" class="c-act ctl ${reverse}" @click=${this._stopFromCompact}
                aria-label=${s.isReverseMode ? 'Cancel delayed start' : 'Stop timer'} title="Stop timer">
          <ha-icon icon="mdi:stop"></ha-icon>
        </button>`;
    } else if (isArmed) {
      action = html`
        <button type="button" class="c-act ghost" @click=${this._cancelSchedule}
                aria-label="Cancel schedule" title="Cancel schedule">
          <ha-icon icon="mdi:close"></ha-icon>
        </button>
        ${canExpand ? chevron : ''}`;
    } else {
      action = html`
        ${chips.length === 0 && !cfg.hide_slider ? html`
          <button type="button" class="c-pill ${startsReverse}" ?disabled=${this._sliderValue <= 0}
                  @click=${this._startFromCompactSlider} title="Start timer">
            <ha-icon icon="mdi:play"></ha-icon><span class="c-pill-label">${this._sliderValue} ${sliderUnit}</span>
          </button>
        ` : ''}
        ${expandable ? chevron : ''}`;
    }

    const sliderMax = cfg.slider_max || 120;
    const pct = Math.max(0, Math.min(100, (this._sliderValue / sliderMax) * 100));
    const hasExtra = chips.length > 0 || showPanel || !!s.watchdogMessage || this._validationMessages.length > 0;

    return html`
      <style>${this._getCompactStyle()}</style>
      <ha-card class="compact ${hasExtra ? 'has-extra' : ''}">
        <div class="c-row">
          <button type="button" class="c-icon ${s.isOn ? 'on' : ''}" @click=${this._handleIndependentPower}
                  aria-label="Toggle power" title="Toggle power">
            ${this._renderCompactIcon(timerSwitch)}
          </button>
          <div class="c-info" @click=${() => this._showMoreInfo()}>
            <div class="c-name">${name}</div>
            <div class="c-sec">
              ${isArmed ? html`<ha-icon icon="mdi:clock-outline"></ha-icon>` : ''}
              ${showTime ? html`<span class="c-left ${reverse}">${s.isReverseMode
                ? `On in ${timeText}`
                : `${timeText} left`}</span>` : ''}
              <span class="c-sec-text ${showTime ? 'wide-only' : ''}">${lead}${withUsage && usage ? html` · <span
                  @click=${(e: Event) => { e.stopPropagation(); this._handleUsageClick(e); }}
                  @mousedown=${this._startLongPress}
                  @mouseup=${this._endLongPress}
                  @mouseleave=${this._endLongPress}
                  @touchstart=${this._handleTouchStart}
                  @touchend=${this._handleTouchEnd}
                  @touchcancel=${this._endLongPress}
                  title="Click to show more info, hold to reset daily usage">${usage}</span>` : ''}</span>
            </div>
          </div>
          ${action}
        </div>

        ${s.watchdogMessage ? html`
          <div class="status-message warning">
            <ha-icon icon="mdi:alert-outline" class="status-icon"></ha-icon>
            <span class="status-text">${s.watchdogMessage}</span>
          </div>
        ` : ''}

        ${chips.length > 0 ? html`
          <div class="c-feat">
            ${chips.map(button => {
              const selected = s.isTimerActive
                && Math.abs(s.timerDurationInMinutes - button.minutesEquivalent) < 0.001
                && sensor.attributes.timer_start_method === 'button';
              return html`
                <button type="button" class="c-chip ${selected ? 'sel' : ''}"
                        @click=${() => s.isTimerActive
                          ? this._addTimer(button.displayValue, button.unit)
                          : this._startTimer(button.displayValue, button.unit, 'button')}>
                  ${s.isTimerActive ? '+' : ''}${button.displayValue}${this._shortUnit(button.unit)}
                </button>`;
            })}
          </div>
        ` : ''}

        ${showPanel ? html`
          <div class="c-panel">
            ${!cfg.hide_slider ? html`
              <div class="c-slider-row">
                <div class="c-range-wrap">
                  <input type="range" class="c-range" min="0" step="1" max=${sliderMax}
                         style="--st-pct: ${pct}%"
                         aria-label="Timer duration"
                         .value=${this._sliderValue.toString()}
                         @input=${this._handleSliderChange} />
                  <span class="c-range-label">${this._sliderValue} ${sliderUnit}</span>
                </div>
                <button type="button" class="c-start ${startsReverse}" ?disabled=${this._sliderValue <= 0}
                        @click=${this._startFromCompactSlider}>
                  <ha-icon icon="mdi:play"></ha-icon>Start
                </button>
              </div>
            ` : ''}
            ${cfg.show_schedule && !isArmed ? this._renderSchedulePanel(sensor) : ''}
          </div>
        ` : ''}

        ${this._validationMessages.length > 0 ? html`
          <div class="status-message warning">
            <ha-icon icon="mdi:alert-outline" class="status-icon"></ha-icon>
            <div class="status-text">
              ${this._validationMessages.map(msg => html`<div>${msg}</div>`)}
            </div>
          </div>
        ` : ''}

        ${showBar ? html`
          <div class="c-bar ${reverse}"><div style="width: ${(s.remainingPercentage * 100).toFixed(2)}%"></div></div>
        ` : ''}
      </ha-card>
    `;
  }

  _renderCompactPreview() {
    const cfg = this._config;
    const chips = this.buttons.filter(b => !b.isDefault).slice(0, 6);
    const icon = cfg?.entity_state_icon || cfg?.power_button_icon || 'mdi:timer-outline';
    return html`
      <style>${this._getCompactStyle()}</style>
      <ha-card class="compact ${chips.length ? 'has-extra' : ''}">
        <div class="c-row">
          <div class="c-icon"><ha-icon icon=${icon}></ha-icon></div>
          <div class="c-info">
            <div class="c-name">${cfg?.card_title || 'Simple Timer'}</div>
            <div class="c-sec"><span class="c-sec-text">Off${cfg?.show_daily_usage !== false ? ' · 3 min today' : ''}</span></div>
          </div>
          <div class="c-act ghost"><ha-icon icon="mdi:chevron-down"></ha-icon></div>
        </div>
        ${chips.length ? html`
          <div class="c-feat">
            ${chips.map(b => html`<div class="c-chip" style="display:flex;align-items:center;justify-content:center">${b.displayValue}${this._shortUnit(b.unit)}</div>`)}
          </div>
        ` : ''}
      </ha-card>
    `;
  }

  _formatScheduleClock(iso: string): string {
    try {
      const d = new Date(iso);
      // Respect HA's configured time format (falls back to locale/OS default).
      const { lang, hourOpt } = this._clockLocale();
      return d.toLocaleString(lang, {
        month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
        ...hourOpt,
      });
    } catch {
      return iso;
    }
  }

  _orderDaysByLocale(): { key: string; label: string }[] {
    const days: Record<string, { key: string; label: string }> = {
      mon: { key: 'mon', label: 'M' }, tue: { key: 'tue', label: 'T' },
      wed: { key: 'wed', label: 'W' }, thu: { key: 'thu', label: 'T' },
      fri: { key: 'fri', label: 'F' }, sat: { key: 'sat', label: 'S' },
      sun: { key: 'sun', label: 'S' },
    };
    const order = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']; // Mon=0 .. Sun=6
    let startKey = 'mon';

    const fw = (this.hass as any)?.locale?.first_weekday;
    const nameMap: Record<string, string> = {
      monday: 'mon', tuesday: 'tue', wednesday: 'wed', thursday: 'thu',
      friday: 'fri', saturday: 'sat', sunday: 'sun',
    };
    if (fw && nameMap[fw]) {
      startKey = nameMap[fw];
    } else {
      // "language" / "system" / unknown -> derive from the locale's week info.
      try {
        const lang = (this.hass as any)?.locale?.language;
        const loc: any = new (Intl as any).Locale(lang);
        const info = loc.weekInfo || (loc.getWeekInfo && loc.getWeekInfo());
        const firstDay = info?.firstDay; // 1=Mon .. 7=Sun
        if (firstDay) startKey = order[(firstDay - 1) % 7];
      } catch {
        /* keep Monday */
      }
    }

    const start = order.indexOf(startKey);
    const rotated = [...order.slice(start), ...order.slice(0, start)];
    return rotated.map(k => days[k]);
  }

  // "daily", "Mon, Wed, Fri", or null for a one-shot schedule. Days are ordered
  // by the locale's first weekday, the same as the day chips.
  _scheduleRepeatDays(sensor: HAState): string | null {
    if (!sensor.attributes.schedule_repeat) return null;
    const days: number[] = sensor.attributes.schedule_days || [];
    if (days.length === 0 || days.length === 7) return 'daily';
    const keyToInt: Record<string, number> = { mon: 0, tue: 1, wed: 2, thu: 3, fri: 4, sat: 5, sun: 6 };
    const intToName: Record<number, string> = { 0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun' };
    return this._orderDaysByLocale()
      .map(d => keyToInt[d.key])
      .filter(i => days.includes(i))
      .map(i => intToName[i])
      .join(', ');
  }

  _renderSchedulePanel(sensor: HAState) {
    const DAYS = this._orderDaysByLocale();

    // Armed state -> banner
    if (sensor?.attributes?.schedule_state === 'armed' && sensor.attributes.scheduled_start) {
      const start = this._formatScheduleClock(sensor.attributes.scheduled_start);
      const dur = sensor.attributes.scheduled_duration;
      const unit = sensor.attributes.scheduled_unit || 'min';
      const repeatDays = this._scheduleRepeatDays(sensor);
      const repeatText = repeatDays === null ? 'One-shot' : `Repeats ${repeatDays}`;
      return html`
        <div class="schedule-banner">
          <ha-icon class="sched-ico" icon="mdi:clock-outline"></ha-icon>
          <div class="sched-banner-text">
            <div class="sched-banner-main">Starts ${start} · runs ${dur} ${unit}</div>
            <div class="sched-banner-sub">${repeatText}</div>
          </div>
          <div class="sched-banner-x" @click=${this._cancelSchedule} title="Cancel schedule">
            <ha-icon icon="mdi:close"></ha-icon>
          </div>
        </div>
      `;
    }

    // Collapsed trigger
    if (!this._scheduleExpanded) {
      return html`
        <div class="schedule-toggle" @click=${() => { this._scheduleExpanded = true; }}>
          <ha-icon icon="mdi:clock-outline"></ha-icon>
          <span>Schedule Timer</span>
          <ha-icon class="sched-chevron" icon="mdi:chevron-down"></ha-icon>
        </div>
      `;
    }

    // Expanded panel
    return html`
      <div class="schedule-panel">
        <div class="schedule-toggle open" @click=${() => { this._scheduleExpanded = false; }}>
          <ha-icon icon="mdi:clock-outline"></ha-icon>
          <span>Schedule Timer</span>
          <ha-icon class="sched-chevron" icon="mdi:chevron-up"></ha-icon>
        </div>

        <div class="sched-field">
          <div class="sched-label">Start at</div>
          <input class="sched-time" type="time"
            .value=${this._scheduleTime}
            @input=${(e: Event) => { this._scheduleTime = (e.target as HTMLInputElement).value; this._persistSchedule(); }} />
        </div>

        <div class="sched-field">
          <div class="sched-label">Run for</div>
          <div class="sched-dur-row">
            <input class="sched-num" type="number" min="1" step="1"
              .value=${String(this._scheduleDuration)}
              @input=${(e: Event) => { this._scheduleDuration = Number((e.target as HTMLInputElement).value); this._persistSchedule(); }} />
            <select class="sched-unit"
              .value=${this._scheduleUnit}
              @change=${(e: Event) => { this._scheduleUnit = (e.target as HTMLSelectElement).value; this._persistSchedule(); }}>
              <option value="s">sec</option>
              <option value="min">min</option>
              <option value="h">hr</option>
            </select>
          </div>
          ${this.buttons.filter(b => !b.isDefault).length > 0 ? html`
            <div class="sched-shortcut-label">Quick fill</div>
            <div class="sched-pills">
              ${this.buttons.filter(b => !b.isDefault).map(b => html`
                <div class="sched-pill ${this._scheduleDuration === b.displayValue && this._scheduleUnit === b.unit ? 'selected' : ''}"
                  @click=${() => { this._scheduleDuration = b.displayValue; this._scheduleUnit = b.unit; this._persistSchedule(); }}>
                  ${b.displayValue} ${b.labelUnit}
                </div>
              `)}
            </div>
          ` : ''}
        </div>

        <div class="sched-repeat-row">
          <span>Repeat daily</span>
          <ha-switch
            .checked=${this._scheduleRepeat}
            @change=${(e: Event) => { this._scheduleRepeat = (e.target as any).checked; this._persistSchedule(); }}></ha-switch>
        </div>

        ${this._scheduleRepeat ? html`
          <div class="sched-days">
            ${DAYS.map(d => html`
              <div class="sched-day ${this._scheduleDays.includes(d.key) ? 'on' : ''}"
                @click=${() => this._toggleScheduleDay(d.key)}>${d.label}</div>
            `)}
          </div>
        ` : ''}

        <div class="sched-actions">
          <div class="sched-btn ghost" @click=${() => { this._scheduleExpanded = false; }}>Cancel</div>
          <div class="sched-btn primary" @click=${this._setSchedule}>Set schedule</div>
        </div>
      </div>
    `;
  }

  static get styles() {
    return [cardStyles, compactStyles];
  }

  _syncServerTime() {
    if (!this.hass || !this._effectiveSensorEntity) return;
    const sensor = this.hass.states[this._effectiveSensorEntity];
    if (!sensor?.last_updated) return;

    // Only compute offset when last_updated has JUST changed,
    // meaning we're receiving a fresh state update right now.
    // This avoids stale offset calculations from old last_updated values.
    const currentLastUpdated = sensor.last_updated;
    if (currentLastUpdated === this._lastSyncedUpdate) return;
    this._lastSyncedUpdate = currentLastUpdated;

    const serverTimeMs = new Date(currentLastUpdated).getTime();
    const localTimeMs = new Date().getTime();
    const offset = serverTimeMs - localTimeMs;
    // Only apply if significant (> 2s), to avoid jitter from network latency
    if (Math.abs(offset) > 2000) {
      this._serverTimeOffset = offset;
    } else {
      this._serverTimeOffset = 0;
    }
  }
}
// Guard against double-registration: a stale resource or duplicated module
// load would otherwise make the second define() throw and abort evaluation.
if (!customElements.get("timer-card")) {
  customElements.define("timer-card", TimerCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "timer-card")) {
  window.customCards.push({
    type: "timer-card",
    name: "HA Simple Timer Card",
    description: "A card for the Simple Timer integration.",
    preview: true,
    getEntitySuggestion: (hass, entityId) => {
      if (!entityId.startsWith("sensor.")) return null;
      const state = hass.states[entityId];
      if (!state || typeof state.attributes.switch_entity_id !== "string") return null;
      const entryId = state.attributes.entry_id as string | undefined;
      return {
        config: { ...TimerCard.getStubConfig(hass as any), ...(entryId ? { timer_instance_id: entryId } : { sensor_entity: entityId }) },
      };
    },
  });
}