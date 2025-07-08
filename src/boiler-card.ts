// boiler-card.ts

import { LitElement, html, css } from 'lit';

// Ensure HomeAssistant and BoilerCardConfig are recognized from global.d.ts

const DOMAIN = "boiler_control";
const CARD_VERSION = "3.6.0";

console.info(
  `%c BOILER-CARD %c v${CARD_VERSION} `,
  'color: orange; font-weight: bold; background: black',
  'color: white; font-weight: bold; background: dimgray',
);

class BoilerCard extends LitElement {
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
  _config?: BoilerCardConfig;

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
    await import("./boiler-card-editor.js");
    return document.createElement("boiler-card-editor");
  }

  static getStubConfig(hass: HomeAssistant): BoilerCardConfig {
    console.log("BoilerCard: Generating stub config with hass object:", hass);
    let initialInstanceId: string | null = null;

    // Find the first boiler control sensor and use its entry_id
    for (const entityId of Object.keys(hass.states)) {
        const state = hass.states[entityId];
        if (entityId.startsWith("sensor.") && 
            typeof state.attributes.entry_id === 'string' && 
            typeof state.attributes.switch_entity_id === 'string') {
            initialInstanceId = state.attributes.entry_id; // Use entry_id, not entity_id
            console.info(`BoilerCard: getStubConfig auto-selected first instance: '${initialInstanceId}' from sensor '${entityId}'`);
            break;
        }
    }

    return {
      type: "custom:boiler-card",
      boiler_instance_id: initialInstanceId, // This will now be explicitly set
      timer_buttons: [15, 30, 60, 90, 120, 150],
      card_title: "Boiler Control"
    };
  }

  setConfig(cfg: BoilerCardConfig): void {
    this._config = {
      type: cfg.type || "custom:boiler-card",
      timer_buttons: Array.isArray(cfg.timer_buttons) ? [...cfg.timer_buttons] : [15, 30, 60, 90, 120, 150],
      card_title: cfg.card_title || null
    };

    if (cfg.boiler_instance_id) {
        this._config.boiler_instance_id = cfg.boiler_instance_id;
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

    let validatedTimerButtons: number[] = [];
    this._validationMessage = null;

    if (Array.isArray(this._config.timer_buttons)) {
        const invalidValues: any[] = [];
        this._config.timer_buttons.forEach(val => {
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
    } else {
        validatedTimerButtons = [15, 30, 45, 60, 90, 120, 150];
    }
    this.buttons = validatedTimerButtons;
    
    this._liveRuntimeSeconds = 0;
    this._notificationSentForCurrentCycle = false;

    this._effectiveSwitchEntity = null;
    this._effectiveSensorEntity = null;
    this._entitiesLoaded = false;
    console.log(`BoilerCard: setConfig completed. Configured instance ID: ${this._config.boiler_instance_id}`);
  }

  _determineEffectiveEntities(): void {
    let currentSwitch: string | null = null;
    let currentSensor: string | null = null;
    let entitiesAreValid = false;

    if (!this.hass || !this.hass.states) {
        this._entitiesLoaded = false;
        return;
    }

    if (this._config?.boiler_instance_id) {
        const targetEntryId = this._config.boiler_instance_id;
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
                console.warn(`BoilerCard: Configured instance '${targetEntryId}' sensor '${currentSensor}' links to missing or invalid switch '${currentSwitch}'.`);
            }
        } else {
            console.warn(`BoilerCard: Configured boiler_instance_id '${targetEntryId}' does not have a corresponding boiler_control sensor found.`);
        }
    }

    if (!entitiesAreValid && this._config?.sensor_entity) {
        const sensorState = this.hass.states[this._config.sensor_entity];
        if (sensorState && typeof sensorState.attributes.entry_id === 'string' && typeof sensorState.attributes.switch_entity_id === 'string') {
            currentSensor = this._config.sensor_entity;
            currentSwitch = sensorState.attributes.switch_entity_id as string | null;
            if (currentSwitch && this.hass.states[currentSwitch]) {
                entitiesAreValid = true;
                console.info(`BoilerCard: Using manually configured sensor_entity: Sensor '${currentSensor}', Switch '${currentSwitch}'.`);
            } else {
                console.warn(`BoilerCard: Manually configured sensor '${currentSensor}' links to missing or invalid switch '${currentSwitch}'.`);
            }
        } else {
            console.warn(`BoilerCard: Manually configured sensor_entity '${this._config.sensor_entity}' not found or missing required attributes.`);
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
                console.info(`BoilerCard: Auto-detected first instance: Sensor '${currentSensor}', Switch '${currentSwitch}'.`);
            } else {
                console.warn(`BoilerCard: Auto-detected sensor '${currentSensor}' links to missing or invalid switch '${currentSwitch}'.`);
            }
        } else {
            console.info(`BoilerCard: No boiler_control sensor found for auto-detection.`);
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
      console.error("Boiler-card: _getEntryId called without a valid effective sensor entity.");
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

    this.hass.callService(domain, service, { message: message });
  }

  _startTimer(minutes: number): void {
    if (!this._entitiesLoaded || !this.hass || !this.hass.callService) {
        console.error("Boiler-card: Cannot start timer. Entities not loaded or callService unavailable.");
        return;
    }
    const entryId = this._getEntryId();
    if (!entryId) { console.error("Boiler-card: Entry ID not found for starting timer."); return; }
    
    const switchId = this._effectiveSwitchEntity!;

    this.hass.callService("switch", "turn_on", { entity_id: switchId })
      .then(() => {
        this.hass!.callService(DOMAIN, "start_timer", { entry_id: entryId, duration: minutes });
        this._sendNotification(`Boiler was turned on for ${minutes} minutes`);
      })
      .catch(error => {
        console.error("Boiler-card: Error turning on switch or starting timer:", error);
      });
    this._notificationSentForCurrentCycle = false;
  }

  _cancelTimer(): void {
    if (!this._entitiesLoaded || !this.hass || !this.hass.callService) {
        console.error("Boiler-card: Cannot cancel timer. Entities not loaded or callService unavailable.");
        return;
    }
    const entryId = this._getEntryId();
    if (!entryId) { console.error("Boiler-card: Entry ID not found for cancelling timer."); return; }

    const switchId = this._effectiveSwitchEntity!;

    this.hass.callService("switch", "turn_off", { entity_id: switchId })
      .then(() => {
        this.hass!.callService(DOMAIN, "cancel_timer", { entry_id: entryId });
        this._sendBoilerFinishedNotification();
      })
      .catch(error => {
        console.error("Boiler-card: Error turning off switch or cancelling timer:", error);
      });
    this._notificationSentForCurrentCycle = false;
  }
	
  _togglePower(): void {
    if (!this._entitiesLoaded || !this.hass || !this.hass.states || !this.hass.callService) {
        console.error("Boiler-card: Cannot toggle power. Entities not loaded or services unavailable.");
        return;
    }
    const switchId = this._effectiveSwitchEntity!;

    const boilerSwitch = this.hass.states[switchId];
    if (!boilerSwitch) {
        console.warn(`Boiler-card: Boiler switch entity '${switchId}' not found during toggle.`);
        return;
    }

    if (boilerSwitch.state === 'on') {
      this._cancelTimer();
      console.log(`Boiler-card: Manually turning off boiler switch: ${switchId}`);
    } else {
      this.hass.callService("switch", "turn_on", { entity_id: switchId })
        .then(() => {
            this._sendNotification("Boiler started");
            console.log(`Boiler-card: Manually turning on boiler switch: ${switchId}`);
        })
        .catch(error => {
            console.error("Boiler-card: Error manually turning on switch:", error);
        });
      this._notificationSentForCurrentCycle = false;
    }
  }

  _showMoreInfo(): void {
    if (!this._entitiesLoaded || !this.hass) {
        console.error("Boiler-card: Cannot show more info. Entities not loaded.");
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
            console.warn("Boiler-card: timer_finishes_at is undefined for active timer. Stopping countdown.");
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
                  const finalSensorState = this.hass!.states[this._effectiveSensorEntity!];
                  const committedSeconds = parseFloat(finalSensorState.state as string) || 0;
                  
                  const totalMinutes = Math.round(committedSeconds / 60);
                  const hours = Math.floor(totalMinutes / 60);
                  const minutes = totalMinutes % 60;
                  const formattedDailyUsage = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
                  
                  this._sendNotification(`Boiler was turned off - daily usage ${formattedDailyUsage} (hh:mm)`);
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
  }

  _sendBoilerFinishedNotification(): void {
    if (!this._entitiesLoaded || !this.hass || !this.hass.states) return;

    const sensor = this.hass!.states[this._effectiveSensorEntity!];
    if (!sensor) return;

    const committedSeconds = parseFloat(sensor.state as string) || 0;
    const totalMinutes = Math.round(committedSeconds / 60);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    const formattedDailyUsage = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
    
    this._sendNotification(`Boiler finished – daily usage ${formattedDailyUsage} (hh:mm)`);
  }
  
  render() {
    let message: string | null = null;
    let isWarning = false;

    if (!this.hass) {
        message = "Home Assistant object (hass) not available. Card cannot load.";
        isWarning = true;
    } else if (!this._entitiesLoaded) {
        if (this._config?.boiler_instance_id) {
            const configuredSensorState = Object.values(this.hass.states).find(
                (state: HAState) => state.attributes.entry_id === this._config!.boiler_instance_id && state.entity_id.startsWith('sensor.')
            ) as HAState | undefined;

            if (!configuredSensorState) {
                message = `Boiler Control Instance '${this._config.boiler_instance_id}' not found. Please select a valid instance in the card editor.`;
                isWarning = true;
            } else if (typeof configuredSensorState.attributes.switch_entity_id !== 'string' || !(configuredSensorState.attributes.switch_entity_id && this.hass.states[configuredSensorState.attributes.switch_entity_id])) {
                message = `Boiler Control Instance '${this._config.boiler_instance_id}' linked to missing or invalid switch '${configuredSensorState.attributes.switch_entity_id}'. Please check instance configuration.`;
                isWarning = true;
            } else {
                message = "Loading Boiler Control Card. Please wait...";
                isWarning = false;
            }
        } else if (this._config?.sensor_entity) {
            const configuredSensorState = this.hass.states[this._config.sensor_entity];
            if (!configuredSensorState) {
                message = `Configured Boiler Control Sensor '${this._config.sensor_entity}' not found. Please select a valid instance in the card editor.`;
                isWarning = true;
            } else if (typeof configuredSensorState.attributes.switch_entity_id !== 'string' || !(configuredSensorState.attributes.switch_entity_id && this.hass.states[configuredSensorState.attributes.switch_entity_id])) {
                message = `Configured Boiler Control Sensor '${this._config.sensor_entity}' is invalid or its linked switch '${configuredSensorState.attributes.switch_entity_id}' is missing. Please select a valid instance.`;
                isWarning = true;
            } else {
                message = "Loading Boiler Control Card. Please wait...";
                isWarning = false;
            }
        } else {
            message = "Select a Boiler Control Instance from the dropdown in the card editor to link this card.";
            isWarning = false;
        }
    }

    if (message) {
      return html`<ha-card><div class="${isWarning ? 'warning' : 'placeholder'}">${message}</div></ha-card>`;
    }
	
    const boilerSwitch = this.hass!.states[this._effectiveSwitchEntity!];
    const sensor = this.hass!.states[this._effectiveSensorEntity!];
    
    const isOn = boilerSwitch.state === 'on';
    const isTimerActive = sensor.attributes.timer_state === 'active';
    const timerDurationInMinutes = sensor.attributes.timer_duration || 0; 
    const isManualOn = isOn && !isTimerActive;

    const committedSeconds = parseFloat(sensor.state as string) || 0; 
    
    let totalSecondsForDisplay = committedSeconds;
    
    const integerMinutes = Math.floor(totalSecondsForDisplay / 60);
    const remainingSeconds = totalSecondsForDisplay % 60;
    
    let finalTotalMinutes = integerMinutes;
    if (remainingSeconds >= 30) {
        finalTotalMinutes += 1;
    }

    const hours = Math.floor(finalTotalMinutes / 60);
    const minutes = finalTotalMinutes % 60;
    const formattedTime = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
    
    const watchdogMessage = sensor.attributes.watchdog_message;

    return html`
      <ha-card>
        ${this._config?.card_title ? html`<div class="card-title">${this._config.card_title}</div>` : ''} 
        <div class="main-grid">
          <div class="button power-button ${isOn ? 'on' : ''}" @click=${this._togglePower}><ha-icon icon="mdi:power"></ha-icon></div>
          <div class="button readonly" @click=${this._showMoreInfo}>
            <span class="daily-time-text">${formattedTime}</span>
            <span class="runtime-label">Daily Usage (hh:mm)</span>
          </div>
        </div>
        <div class="button-grid">
        ${watchdogMessage ? html`
          <div class="status-message warning">
            <ha-icon icon="mdi:alert-outline" class="status-icon"></ha-icon>
            <span class="status-text">${watchdogMessage}</span>
          </div>
        ` : ''}
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
        ${watchdogMessage || this._validationMessage ? html`
          <div class="status-message warning">
            <ha-icon icon="mdi:alert-outline" class="status-icon"></ha-icon>
            <span class="status-text">${watchdogMessage || this._validationMessage}</span>
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
        /* NEW: Added white-space property to preserve spaces within the title */
        white-space: pre-wrap; /* This should fix the trimming for the div itself */
        word-break: break-word; /* Ensure long words break */
      }
      .card-title pre { /* This pre tag is no longer needed if div handles white-space */
        margin: 0;
        padding: 0;
        /* white-space: pre-wrap;  Removed as parent div should handle it */
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
      .daily-time-text { font-size: 36px; font-weight: bold; }
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
customElements.define("boiler-card", BoilerCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "boiler-card",
  name: "Boiler Control Card",
  description: "A card for the Boiler Control integration.",
});