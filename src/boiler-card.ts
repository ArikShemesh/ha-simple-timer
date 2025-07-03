// boiler-card.ts

import { LitElement, html, css } from 'lit';

// Ensure HomeAssistant and BoilerCardConfig are recognized from global.d.ts

const DOMAIN = "boiler_control";
const CARD_VERSION = "3.6.0"; // Version updated

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
      _liveRuntimeSeconds: { state: true }
    };
  }

  hass?: HomeAssistant;
  _config?: BoilerCardConfig;

  _countdownInterval: number | null = null;
  _liveRuntimeInterval: number | null = null;

  _timeRemaining: string | null = null;
  _liveRuntimeSeconds: number = 0;

  buttons: number[] = [];
  _validationMessage: string | null = null;
  _notificationSentForCurrentCycle: boolean = false;

  static async getConfigElement(): Promise<HTMLElement> {
    await import("./boiler-card-editor.js");
    return document.createElement("boiler-card-editor");
  }

  static getStubConfig(hass: HomeAssistant): BoilerCardConfig {
    let boilerSensorCandidate: string | null = null;
    let availableSwitchCandidate: string = "switch.your_boiler_switch_HERE";

    for (const entityId of Object.keys(hass.states)) {
      if (entityId.startsWith("switch.")) {
        availableSwitchCandidate = entityId;
        break;
      }
    }

    for (const entityId of Object.keys(hass.states)) {
        const state = hass.states[entityId];
        if (entityId.startsWith("sensor.") && typeof state.attributes.entry_id === 'string' && state.attributes.entry_id.length > 0) {
            boilerSensorCandidate = entityId;
            break;
        }
    }

    return {
      type: "custom:boiler-card",
      entity: availableSwitchCandidate,
      sensor_entity: boilerSensorCandidate || `sensor.daily_runtime`,
      timer_buttons: [15, 30, 60, 90, 120, 150]
    };
  }

  setConfig(cfg: BoilerCardConfig): void {
    if (!cfg.entity) {
      throw new Error("You must specify 'entity' (the switch to control)");
    }
    if (!cfg.sensor_entity) {
        throw new Error("You must specify 'sensor_entity' (the boiler_control sensor)");
    }

    const oldConfig = this._config;
    this._config = {
      ...cfg,
      sensor_entity: cfg.sensor_entity,
      type: cfg.type || "custom:boiler-card"
    };
    
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

    if (this.hass && oldConfig?.entity !== this._config.entity) {
        this._updateBackendSwitchEntity();
    }
  }

  _updateBackendSwitchEntity(): void {
    const entryId = this._getEntryId();
    if (!entryId || !this.hass || !this._config?.entity || !this._config.sensor_entity) return;

    const sensor = this.hass.states[this._config.sensor_entity];
    if (sensor && sensor.attributes.switch_entity_id === this._config.entity) {
      return;
    }

    console.log(`Boiler-card: Linking to sensor. Telling backend to monitor switch: ${this._config.entity}`);
    this.hass.callService(DOMAIN, "update_switch_entity", {
      entry_id: entryId,
      switch_entity_id: this._config.entity,
    });
  }

  _getEntryId(): string | null {
    const sensor = this.hass?.states[this._config?.sensor_entity || ''];
    if (sensor && sensor.attributes.entry_id) {
      return sensor.attributes.entry_id;
    }
    console.error("Could not determine entry_id from sensor_entity:", this._config?.sensor_entity);
    return null;
  }
  
  _sendNotification(message: string): void {
    if (!this.hass || !this._config?.notification_entity || this._config.notification_entity === "none_selected") {
      return;
    }
    const serviceParts = this._config.notification_entity.split('.');
    const domain = serviceParts[0];
    const service = serviceParts.slice(1).join('.');

    this.hass.callService(domain, service, { message: message });
  }

  _startTimer(minutes: number): void {
    const entryId = this._getEntryId();
    if (!entryId || !this.hass || !this._config?.entity) return;
    const entityToControl = this._config.entity;

    this.hass.callService("switch", "turn_on", { entity_id: entityToControl })
      .then(() => {
        this.hass!.callService(DOMAIN, "start_timer", { entry_id: entryId, duration: minutes });
        // **FIX**: Restore notification on timer start
        this._sendNotification(`Boiler was turned on for ${minutes} minutes`);
      });
    this._notificationSentForCurrentCycle = false;
  }

  _cancelTimer(): void {
    const entryId = this._getEntryId();
    if (!entryId || !this.hass || !this._config?.entity) return;
    const entityToControl = this._config.entity;

    this.hass.callService("switch", "turn_off", { entity_id: entityToControl })
      .then(() => {
        this.hass!.callService(DOMAIN, "cancel_timer", { entry_id: entryId });
      });
    this._notificationSentForCurrentCycle = false;
  }
	
  _togglePower(): void {
    if (!this.hass || !this._config?.entity) return;
    const boilerSwitch = this.hass.states[this._config.entity];
    if (!boilerSwitch) return;

    if (boilerSwitch.state === 'on') {
      this._cancelTimer();
    } else {
      this.hass.callService("switch", "turn_on", { entity_id: this._config.entity });
    }
  }

  _showMoreInfo(): void {
    if (!this._config?.sensor_entity) return;
    const event = new CustomEvent("hass-more-info", {
      bubbles: true,
      composed: true,
      detail: { entityId: this._config.sensor_entity }
    });
    this.dispatchEvent(event);
  }
  
  connectedCallback(): void {
    super.connectedCallback();
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
      this._updateLiveRuntime();
      this._updateCountdown();
      if (this._config && this.hass) {
        this._updateBackendSwitchEntity();
      }
    }
  }

  _updateLiveRuntime(): void {
    if (!this.hass || !this._config?.entity) {
      this._stopLiveRuntime();
      return;
    }
    const mainSwitch = this.hass.states[this._config.entity];
    if (!mainSwitch || mainSwitch.state !== 'on') {
        this._stopLiveRuntime();
        return;
    }
    if (this._liveRuntimeInterval) return;

    const startedAt = mainSwitch.last_changed ? new Date(mainSwitch.last_changed).getTime() : new Date().getTime();
    
    this._liveRuntimeInterval = window.setInterval(() => {
        this._liveRuntimeSeconds = (new Date().getTime() - startedAt) / 1000;
        this.requestUpdate();
    }, 1000);
  }

  _stopLiveRuntime(): void {
    if (this._liveRuntimeInterval) {
      window.clearInterval(this._liveRuntimeInterval);
      this._liveRuntimeInterval = null;
    }
    this._liveRuntimeSeconds = 0;
  }

  _updateCountdown(): void {
    if (!this.hass || !this._config?.sensor_entity) {
      this._stopCountdown();
      return;
    }
    const sensor = this.hass.states[this._config.sensor_entity];
    
    this._stopCountdown();

    if (sensor && sensor.attributes.timer_state === 'active') {
      if (!this._countdownInterval) {
          const rawFinish = sensor.attributes.timer_finishes_at;
          if (rawFinish === undefined) { this._stopCountdown(); return; }
          const finishesAt = new Date(rawFinish).getTime();

          const update = () => {
            const now = new Date().getTime();
            const remaining = Math.max(0, Math.round((finishesAt - now) / 1000));
            this._timeRemaining = `${Math.floor(remaining / 60).toString().padStart(2, '0')}:${(remaining % 60).toString().padStart(2, '0')}`;

            if (remaining === 0) {
                this._stopCountdown();
                if (!this._notificationSentForCurrentCycle) {
                    // **FIX**: Restore detailed notification on timer end
                    const finalSensorState = this.hass!.states[this._config!.sensor_entity!];
                    const committedSeconds = parseFloat(finalSensorState.state as string) || 0;
                    const timerDurationSeconds = (finalSensorState.attributes.timer_duration || 0) * 60;
                    const totalDailyUsageSeconds = committedSeconds + timerDurationSeconds;
                    
                    const totalMinutes = Math.round(totalDailyUsageSeconds / 60);
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
    } else {
      this._stopCountdown();
      this._notificationSentForCurrentCycle = false;
    }
  }

  _stopCountdown(): void {
    if (this._countdownInterval) {
      window.clearInterval(this._countdownInterval);
      this._countdownInterval = null;
    }
    this._timeRemaining = null;
  }
  
  render() {
    if (!this.hass || !this._config || !this._config.entity || this._config.entity === "switch.your_boiler_switch_HERE" || !this._config.sensor_entity) {
      return html`<ha-card><div class="placeholder">Please select your **Boiler Switch Entity** and **Boiler Control Sensor** in the card editor.</div></ha-card>`;
    }
	
    const boilerSwitch = this.hass.states[this._config.entity];
    const sensor = this.hass.states[this._config.sensor_entity];

    if (!boilerSwitch) {
      return html`<ha-card><div class="warning">Boiler Switch Entity '${this._config.entity}' not found. Please check configuration.</div></ha-card>`;
    }
    if (!sensor) {
        return html`<ha-card><div class="warning">Boiler Control Sensor '${this._config.sensor_entity}' not found. Please ensure the Boiler Control integration is configured and the sensor exists.</div></ha-card>`;
    }
    
    const isOn = boilerSwitch.state === 'on';
    const isTimerActive = sensor.attributes.timer_state === 'active';
    const timerDurationInMinutes = sensor.attributes.timer_duration || 0; 
    const isManualOn = isOn && !isTimerActive;

    const committedSeconds = parseFloat(sensor.state as string) || 0;
    
    let totalSecondsForDisplay = committedSeconds;
    if (isOn) {
        totalSecondsForDisplay += (this._liveRuntimeSeconds || 0);
    }

    const integerMinutes = Math.floor(totalSecondsForDisplay / 60);
    const remainingSeconds = totalSecondsForDisplay % 60;
    
    let finalTotalMinutes = integerMinutes;
    if (remainingSeconds >= 59.5) {
        finalTotalMinutes += 1;
    }

    const hours = Math.floor(finalTotalMinutes / 60);
    const minutes = finalTotalMinutes % 60;
    const formattedTime = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
    
    const watchdogMessage = sensor.attributes.watchdog_message;

    return html`
      <ha-card>
        <div class="main-grid">
          <div class="button power-button ${isOn ? 'on' : ''}" @click=${this._togglePower}><ha-icon icon="mdi:power"></ha-icon></div>
          <div class="button readonly" @click=${this._showMoreInfo}>
            <span class="daily-time-text">${formattedTime}</span>
            <span class="runtime-label">Daily Usage (hh:mm)</span>
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
    return css`:host { display: block; } .placeholder { padding: 16px; background-color: var(--secondary-background-color); } .warning { padding: 16px; color: white; background-color: var(--error-color); } .main-grid, .button-grid { gap: 12px; padding: 12px; } .main-grid { display: grid; grid-template-columns: 1fr 1fr; } .button-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; padding-top: 0; } .button { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 16px 8px; background-color: var(--secondary-background-color); border-radius: 12px; cursor: pointer; transition: background-color 0.2s, opacity 0.2s; text-align: center; -webkit-tap-highlight-color: transparent; height: 100px; box-sizing: border-box; } .button:hover { background-color: var(--primary-color-faded, #3a506b); } .power-button { font-size: 80px; --mdc-icon-size: 80px; color: white; background-color: var(--error-color); } .power-button.on { background-color: var(--success-color); } .readonly { background-color: var(--card-background-color); border: 1px solid var(--secondary-background-color); line-height: 1.2; } .active, .active:hover { background-color: var(--primary-color); color: white; } .countdown-text { font-size: 28px; font-weight: bold; color: white; } .daily-time-text { font-size: 36px; font-weight: bold; } .runtime-label { font-size: 14px; text-transform: uppercase; color: var(--secondary-text-color); margin-top: 2px; } .timer-button-content { display: flex; flex-direction: column; align-items: center; justify-content: center; line-height: 1.1; } .timer-button-value { font-size: 36px; font-weight: 500; color: var(--primary-text-color); } .timer-button-unit { font-size: 14px; color: var(--secondary-text-color); } .active .timer-button-value, .active .timer-button-unit { color: white; } .disabled { opacity: 0.5; cursor: not-allowed; } .disabled:hover { background-color: var(--secondary-background-color); } .status-message { display: flex; align-items: center; padding: 8px 12px; margin: 0 12px 12px 12px; border-radius: 8px; border: 1px solid var(--warning-color); background-color: rgba(var(--rgb-warning-color), 0.1); } .status-icon { color: var(--warning-color); margin-right: 8px; } .status-text { font-size: 14px; color: var(--primary-text-color); }`; }
}
customElements.define("boiler-card", BoilerCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "boiler-card",
  name: "Boiler Control Card",
  description: "A card for the Boiler Control integration.",
});
