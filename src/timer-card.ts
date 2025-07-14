// timer-card.ts

import { LitElement, html, css } from 'lit';

// Ensure HomeAssistant and TimerCardConfig are recognized from global.d.ts

const DOMAIN = "simple_timer";
const CARD_VERSION = "1.0.10";
const DEFAULT_TIMER_BUTTONS = [15, 30, 60, 90, 120, 150]; // Default for new cards only

console.info(
  `%c TIMER-CARD %c v${CARD_VERSION} `,
  'color: orange; font-weight: bold; background: black',
  'color: white; font-weight: bold; background: dimgray',
);

class TimerCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      _config: { type: Object },
      _timeRemaining: { state: true },
      _entitiesLoaded: { state: true },
      _effectiveSwitchEntity: { state: true },
      _effectiveSensorEntity: { state: true },
    };
  }

  hass?: HomeAssistant;
  _config?: TimerCardConfig;

  _countdownInterval: number | null = null;
  _liveRuntimeSeconds: number = 0;

  _timeRemaining: string | null = null;

  buttons: number[] = [];
  _validationMessage: string | null = null;
  _notificationSentForCurrentCycle: boolean = false;
  _entitiesLoaded: boolean = false;

  _effectiveSwitchEntity: string | null = null;
  _effectiveSensorEntity: string | null = null;

  static async getConfigElement(): Promise<HTMLElement> {
    await import("./timer-card-editor.js");
    return document.createElement("timer-card-editor");
  }

  static getStubConfig(hass: HomeAssistant): TimerCardConfig {
    console.log("TimerCard: Generating stub config with hass object:", hass);
    let initialInstanceId: string | null = null;

    // Find the first timer control sensor and use its entry_id
    for (const entityId of Object.keys(hass.states)) {
        const state = hass.states[entityId];
        if (entityId.startsWith("sensor.") &&
            typeof state.attributes.entry_id === 'string' &&
            typeof state.attributes.switch_entity_id === 'string') {
            initialInstanceId = state.attributes.entry_id; // Use entry_id, not entity_id
            console.info(`TimerCard: getStubConfig auto-selected first instance: '${initialInstanceId}' from sensor '${entityId}'`);
            break;
        }
    }

    return {
      type: "custom:timer-card",
      timer_instance_id: initialInstanceId, // This will now be explicitly set
      timer_buttons: [...DEFAULT_TIMER_BUTTONS], // Use default buttons
      card_title: "Simple Timer",
      show_seconds: false
    };
  }

  setConfig(cfg: TimerCardConfig): void {
    this._config = {
      type: cfg.type || "custom:timer-card",
      timer_buttons: this._getValidatedTimerButtons(cfg.timer_buttons),
      card_title: cfg.card_title || null,
      show_seconds: cfg.show_seconds || false
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
    if (cfg.notification_entity) {
        this._config.notification_entity = cfg.notification_entity;
    }

    // Set buttons from validated config - could be empty array
    this.buttons = [...this._config.timer_buttons];

    this._liveRuntimeSeconds = 0;
    this._notificationSentForCurrentCycle = false;

    this._effectiveSwitchEntity = null;
    this._effectiveSensorEntity = null;
    this._entitiesLoaded = false;
    console.log(`TimerCard: setConfig completed. Configured instance ID: ${this._config.timer_instance_id}, Buttons: ${this.buttons.length}, Show seconds: ${this._config.show_seconds}`);
  }

  _getValidatedTimerButtons(configButtons: any): number[] {
    let validatedTimerButtons: number[] = [];
    this._validationMessage = null;

    if (Array.isArray(configButtons)) {
        const invalidValues: any[] = [];

        configButtons.forEach(val => {
            const numVal = Number(val);
            if (Number.isInteger(numVal) && numVal > 0 && numVal <= 1000) {
                validatedTimerButtons.push(numVal);
            } else {
                invalidValues.push(val);
            }
        });

        if (invalidValues.length > 0) {
            this._validationMessage = `Invalid timer values ignored: ${invalidValues.join(', ')}. Only positive integers up to 1000 are allowed.`;
        }

        validatedTimerButtons.sort((a, b) => a - b);
        return validatedTimerButtons;
    }

    if (configButtons === undefined || configButtons === null) {
        return [];
    }

    console.warn(`TimerCard: Invalid timer_buttons type (${typeof configButtons}):`, configButtons, `- using empty array`);
    this._validationMessage = `Invalid timer_buttons configuration. Expected array, got ${typeof configButtons}.`;
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

    if (!entitiesAreValid) {
        const allSensors = Object.keys(this.hass.states).filter(entityId => entityId.startsWith('sensor.'));
        const autoDetectedSensorKey = allSensors.find(entityId => {
            const state = this.hass!.states[entityId];
            return typeof state.attributes.entry_id === 'string' && typeof state.attributes.switch_entity_id === 'string';
        });

        if (autoDetectedSensorKey) {
            const sensorState = this.hass.states[autoDetectedSensorKey];
            currentSensor = autoDetectedSensorKey;
            currentSwitch = sensorState.attributes.switch_entity_id as string | null;
            if (currentSwitch && this.hass.states[currentSwitch]) {
                entitiesAreValid = true;
                console.info(`TimerCard: Auto-detected first instance: Sensor '${currentSensor}', Switch '${currentSwitch}'.`);
            } else {
                console.warn(`TimerCard: Auto-detected sensor '${currentSensor}' links to missing or invalid switch '${currentSwitch}'.`);
            }
        } else {
            console.info(`TimerCard: No simple_timer sensor found for auto-detection.`);
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

  _sendNotification(message: string): void {
    if (!this.hass || !this.hass.callService || !this._config?.notification_entity || this._config.notification_entity === "none_selected") {
      return;
    }
    const serviceParts = this._config.notification_entity.split('.');
    const domain = serviceParts[0];
    const service = serviceParts.slice(1).join('.');

    this.hass.callService(domain, service, { message: message })
      .catch(error => {
        console.warn("Timer-card: Notification failed:", error);
      });
  }

  _startTimer(minutes: number): void {
    if (!this._entitiesLoaded || !this.hass || !this.hass.callService) {
        console.error("Timer-card: Cannot start timer. Entities not loaded or callService unavailable.");
        return;
    }
    const entryId = this._getEntryId();
    if (!entryId) { console.error("Timer-card: Entry ID not found for starting timer."); return; }

    const switchId = this._effectiveSwitchEntity!;

    this.hass.callService("homeassistant", "turn_on", { entity_id: switchId })
      .then(() => {
        this.hass!.callService(DOMAIN, "start_timer", { entry_id: entryId, duration: minutes });
        this._sendNotification(`${this._config?.card_title || 'Timer'} was turned on for ${minutes} minutes`);
      })
      .catch(error => {
        console.error("Timer-card: Error turning on switch or starting timer:", error);
      });
    this._notificationSentForCurrentCycle = false;
  }

  _cancelTimer(): void {
    if (!this._entitiesLoaded || !this.hass || !this.hass.callService) {
        console.error("Timer-card: Cannot cancel timer. Entities not loaded or callService unavailable.");
        return;
    }
    const entryId = this._getEntryId();
    if (!entryId) { console.error("Timer-card: Entry ID not found for cancelling timer."); return; }

    this.hass.callService(DOMAIN, "cancel_timer", { entry_id: entryId })
      .then(() => {
        this._sendTimerFinishedNotification();
      })
      .catch(error => {
        console.error("Timer-card: Error cancelling timer:", error);
      });

    this._notificationSentForCurrentCycle = false;
  }

  _togglePower(): void {
    if (!this._entitiesLoaded || !this.hass || !this.hass.states || !this.hass.callService) {
        console.error("Timer-card: Cannot toggle power. Entities not loaded or services unavailable.");
        return;
    }
    const switchId = this._effectiveSwitchEntity!;
    const sensorId = this._effectiveSensorEntity!;

    const timerSwitch = this.hass.states[switchId];
    if (!timerSwitch) {
        console.warn(`Timer-card: Switch entity '${switchId}' not found during toggle.`);
        return;
    }

    const sensor = this.hass.states[sensorId];
    const isTimerActive = sensor && sensor.attributes.timer_state === 'active';

    if (timerSwitch.state === 'on') {
        if (isTimerActive) {
            this._cancelTimer();
            console.log(`Timer-card: Cancelling active timer for switch: ${switchId}`);
        } else {
            this.hass.callService("homeassistant", "turn_off", { entity_id: switchId });
            const sensorState = this.hass.states[this._effectiveSensorEntity!];
            if (sensorState) {
                const totalSeconds = parseFloat(sensorState.state as string) || 0;
                const { formattedTime, label } = this._formatTimeForNotification(totalSeconds);
                this._sendNotification(`${this._config?.card_title || 'Timer'} was turned off - daily usage ${formattedTime} ${label}`);
            }
            console.log(`Timer-card: Manually turning off switch: ${switchId}`);
        }
    } else {
      this.hass.callService("homeassistant", "turn_on", { entity_id: switchId })
        .then(() => {
            this._sendNotification(`${this._config?.card_title || 'Timer'} started`);
            console.log(`Timer-card: Manually turning on switch: ${switchId}`);
        })
        .catch(error => {
            console.error("Timer-card: Error manually turning on switch:", error);
        });
      this._notificationSentForCurrentCycle = false;
    }
  }

  _showMoreInfo(): void {
    if (!this._entitiesLoaded || !this.hass) {
        console.error("Timer-card: Cannot show more info. Entities not loaded.");
        return;
    }
    const sensorId = this._effectiveSensorEntity!;

    const event = new CustomEvent("hass-more-info", {
      bubbles: true,
      composed: true,
      detail: { entityId: sensorId }
    });
    this.dispatchEvent(event);
  }

  connectedCallback(): void {
    super.connectedCallback();
    this._determineEffectiveEntities();
    this._updateLiveRuntime();
    this._updateCountdown();
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this._stopCountdown();
    this._stopLiveRuntime();
  }

  updated(changedProperties: Map<string | number | symbol, unknown>): void {
    if (changedProperties.has("hass") || changedProperties.has("_config")) {
        this._determineEffectiveEntities();
        this._updateLiveRuntime();
        this._updateCountdown();
    }
  }

  _updateLiveRuntime(): void {
    this._liveRuntimeSeconds = 0;
  }

  _stopLiveRuntime(): void {
    this._liveRuntimeSeconds = 0;
  }

  _formatTimeForNotification(totalSeconds: number): { formattedTime: string; label: string } {
    if (this._config?.show_seconds) {
      const totalSecondsInt = Math.floor(totalSeconds);
      const hours = Math.floor(totalSecondsInt / 3600);
      const minutes = Math.floor((totalSecondsInt % 3600) / 60);
      const seconds = totalSecondsInt % 60;
      const formattedTime = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
      return { formattedTime, label: "(hh:mm:ss)" };
    } else {
      // ▼▼▼ FIX: Use Math.floor to match the card's display logic ▼▼▼
      const totalMinutes = Math.floor(totalSeconds / 60);
      const hours = Math.floor(totalMinutes / 60);
      const minutes = totalMinutes % 60;
      const formattedTime = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
      return { formattedTime, label: "(hh:mm)" };
    }
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

    if (!this._countdownInterval) {
        const rawFinish = sensor.attributes.timer_finishes_at;
        if (rawFinish === undefined) {
            console.warn("Timer-card: timer_finishes_at is undefined for active timer. Stopping countdown.");
            this._stopCountdown();
            return;
        }
        const finishesAt = new Date(rawFinish).getTime();

        const update = () => {
          const now = new Date().getTime();
          const remaining = Math.max(0, Math.round((finishesAt - now) / 1000));
          this._timeRemaining = `${Math.floor(remaining / 60).toString().padStart(2, '0')}:${(remaining % 60).toString().padStart(2, '0')}`;

          if (remaining === 0) {
              this._stopCountdown();
              if (!this._notificationSentForCurrentCycle) {
                  this._notificationSentForCurrentCycle = true; // Set flag immediately to prevent multiple triggers

                  setTimeout(() => {
                      if (!this.hass || !this._effectiveSensorEntity) return;

                      const finalSensorState = this.hass.states[this._effectiveSensorEntity];
                      if (!finalSensorState) return;

                      const totalSeconds = parseFloat(finalSensorState.state as string) || 0;
                      
                      const { formattedTime, label } = this._formatTimeForNotification(totalSeconds);
                      this._sendNotification(`${this._config?.card_title || 'Timer'} was turned off - daily usage ${formattedTime} ${label}`);
                  }, 500);
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
  }

  _sendTimerFinishedNotification(): void {
    if (!this._entitiesLoaded || !this.hass || !this.hass.states) return;

    const sensor = this.hass!.states[this._effectiveSensorEntity!];
    if (!sensor) return;

    const committedSeconds = parseFloat(sensor.state as string) || 0;
    
    const { formattedTime, label } = this._formatTimeForNotification(committedSeconds);
    this._sendNotification(`${this._config?.card_title || 'Timer'} finished – daily usage ${formattedTime} ${label}`);
  }

  render() {
    let message: string | null = null;
    let isWarning = false;

    if (!this.hass) {
        message = "Home Assistant object (hass) not available. Card cannot load.";
        isWarning = true;
    } else if (!this._entitiesLoaded) {
        if (this._config?.timer_instance_id) {
            const configuredSensorState = Object.values(this.hass.states).find(
                (state: HAState) => state.attributes.entry_id === this._config!.timer_instance_id && state.entity_id.startsWith('sensor.')
            ) as HAState | undefined;

            if (!configuredSensorState) {
                message = `Timer Control Instance '${this._config.timer_instance_id}' not found. Please select a valid instance in the card editor.`;
                isWarning = true;
            } else if (typeof configuredSensorState.attributes.switch_entity_id !== 'string' || !(configuredSensorState.attributes.switch_entity_id && this.hass.states[configuredSensorState.attributes.switch_entity_id])) {
                message = `Timer Control Instance '${this._config.timer_instance_id}' linked to missing or invalid switch '${configuredSensorState.attributes.switch_entity_id}'. Please check instance configuration.`;
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
                message = `Configured Timer Control Sensor '${this._config.sensor_entity}' is invalid or its linked switch '${configuredSensorState.attributes.switch_entity_id}' is missing. Please select a valid instance.`;
                isWarning = true;
            } else {
                message = "Loading Timer Control Card. Please wait...";
                isWarning = false;
            }
        } else {
            message = "Select a Timer Control Instance from the dropdown in the card editor to link this card.";
            isWarning = false;
        }
    }

    if (message) {
      return html`<ha-card><div class="${isWarning ? 'warning' : 'placeholder'}">${message}</div></ha-card>`;
    }

    const timerSwitch = this.hass!.states[this._effectiveSwitchEntity!];
    const sensor = this.hass!.states[this._effectiveSensorEntity!];

    const isOn = timerSwitch.state === 'on';
    const isTimerActive = sensor.attributes.timer_state === 'active';
    const timerDurationInMinutes = sensor.attributes.timer_duration || 0;
    const isManualOn = isOn && !isTimerActive;

    const committedSeconds = parseFloat(sensor.state as string) || 0;

    let totalSecondsForDisplay = committedSeconds;

    // Format time based on show_seconds setting
    let formattedTime: string;
    let runtimeLabel: string;

    if (this._config?.show_seconds) {
      // Show full HH:MM:SS format
      const totalSecondsInt = Math.floor(totalSecondsForDisplay);
      const hours = Math.floor(totalSecondsInt / 3600);
      const minutes = Math.floor((totalSecondsInt % 3600) / 60);
      const seconds = totalSecondsInt % 60;
      formattedTime = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
      runtimeLabel = "Daily Usage (hh:mm:ss)";
    } else {
      // Show HH:MM format (original behavior)
      const totalMinutes = Math.floor(totalSecondsForDisplay / 60);
      const hours = Math.floor(totalMinutes / 60);
      const minutes = totalMinutes % 60;
      formattedTime = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
      runtimeLabel = "Daily Usage (hh:mm)";
    }

    const watchdogMessage = sensor.attributes.watchdog_message;

    return html`
      <ha-card>
        ${this._config?.card_title ? html`<div class="card-title">${this._config.card_title}</div>` : ''}
        ${watchdogMessage ? html`
          <div class="status-message warning watchdog-banner">
            <ha-icon icon="mdi:alert-outline" class="status-icon"></ha-icon>
            <span class="status-text">${watchdogMessage}</span>
          </div>
        ` : ''}
        <div class="main-grid">
          <div class="button power-button ${isOn ? 'on' : ''}" @click=${this._togglePower}><ha-icon icon="mdi:power"></ha-icon></div>
          <div class="button readonly" @click=${this._showMoreInfo}>
            <span class="daily-time-text ${this._config?.show_seconds ? 'with-seconds' : ''}">${formattedTime}</span>
            <span class="runtime-label">${runtimeLabel}</span>
          </div>
        </div>
        <div class="button-grid">
          ${this.buttons.map(minutes => {
            const isActive = isTimerActive && timerDurationInMinutes === minutes;
            const isDisabled = isManualOn || (isTimerActive && !isActive);
            return html`
              <div class="button timer-button ${isActive ? 'active' : ''} ${isDisabled ? 'disabled' : ''}" @click=${() => { if (isActive) this._cancelTimer(); else if (!isDisabled) this._startTimer(minutes); }}>
                ${isActive && this._timeRemaining ? html`<span class="countdown-text">${this._timeRemaining}</span>` : html`<div class="timer-button-content"><span class="timer-button-value">${minutes}</span><span class="timer-button-unit">Min</span></div>`}
              </div>
            `;
          })}
        </div>
        ${this._validationMessage ? html`
          <div class="status-message warning">
            <ha-icon icon="mdi:alert-outline" class="status-icon"></ha-icon>
            <span class="status-text">${this._validationMessage}</span>
          </div>
        ` : ''}
      </ha-card>
    `;
  }

  static get styles() {
    return css`
      :host { display: block; }
      .ha-card {
        padding: 0;
      }
      .card-title {
        font-size: 1.2em;
        font-weight: bold;
        text-align: center;
        padding: 12px;
        background-color: var(--primary-color-faded, rgba(150, 210, 230, 0.2));
        border-bottom: 1px solid var(--divider-color);
        color: var(--primary-text-color);
        border-radius: 12px 12px 0 0;
        margin-bottom: 12px;
        white-space: pre-wrap;
        word-break: break-word;
      }
      .card-title pre {
        margin: 0;
        padding: 0;
        font-family: inherit;
        font-size: inherit;
        color: inherit;
      }
      .placeholder { padding: 16px; background-color: var(--secondary-background-color); }
      .warning { padding: 16px; color: white; background-color: var(--error-color); }
      .main-grid, .button-grid { gap: 12px; padding: 12px; }
      .main-grid { display: grid; grid-template-columns: 1fr 1fr; }
      .button-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(90px, 1fr)); padding-top: 0; }
      .button {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 16px 8px;
        background-color: var(--secondary-background-color);
        border-radius: 12px;
        cursor: pointer;
        transition: background-color 0.2s, opacity 0.2s;
        text-align: center;
        -webkit-tap-highlight-color: transparent;
        height: 100px;
        box-sizing: border-box;
      }
      .button:hover { background-color: var(--primary-color-faded, #3a506b); }
      .power-button {
        font-size: 80px;
        --mdc-icon-size: 80px;
        color: white;
        background-color: var(--error-color);
      }
      .power-button.on { background-color: var(--success-color); }
      .readonly {
        background-color: var(--card-background-color);
        border: 1px solid var(--secondary-background-color);
        line-height: 1.2;
        cursor: default;
      }
      .active, .active:hover { background-color: var(--primary-color); color: white; }
      .countdown-text { font-size: 28px; font-weight: bold; color: white; }
      .daily-time-text {
        font-size: 36px;
        font-weight: bold;
      }
      .daily-time-text.with-seconds {
        font-size: 28px;
      }
      .runtime-label { font-size: 14px; text-transform: uppercase; color: var(--secondary-text-color); margin-top: 2px; }
      .timer-button-content { display: flex; flex-direction: column; align-items: center; justify-content: center; line-height: 1.1; }
      .timer-button-value { font-size: 36px; font-weight: 500; color: var(--primary-text-color); }
      .timer-button-unit { font-size: 14px; color: var(--secondary-text-color); }
      .active .timer-button-value, .active .timer-button-unit { color: white; }
      .disabled { opacity: 0.5; cursor: not-allowed; }
      .disabled:hover { background-color: var(--secondary-background-color); }
      .status-message {
        display: flex;
        align-items: center;
        padding: 8px 12px;
        margin: 0 12px 12px 12px;
        border-radius: 8px;
        border: 1px solid var(--warning-color);
        background-color: rgba(var(--rgb-warning-color), 0.1);
      }
      .status-icon { color: var(--warning-color); margin-right: 8px; }
      .status-text { font-size: 14px; color: var(--primary-text-color); }
      .watchdog-banner {
        margin: 0 0 12px 0;
        border-radius: 0;
        grid-column: 1 / -1;
      }
      .status-message.warning {
        display: flex;
        align-items: center;
        padding: 8px 12px;
        margin: 0 12px 12px 12px;
        border-radius: 8px;
        border: 1px solid var(--warning-color);
        background-color: rgba(var(--rgb-warning-color), 0.1);
      }
      .status-icon {
        color: var(--warning-color);
        margin-right: 8px;
      }
      .status-text {
        font-size: 14px;
        color: var(--primary-text-color);
      }
    `;
  }
}
customElements.define("timer-card", TimerCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "timer-card",
  name: "Simple Timer Card",
  description: "A card for the Simple Timer integration.",
});
