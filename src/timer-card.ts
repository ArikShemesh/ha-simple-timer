// timer-card.ts

import { LitElement, html } from 'lit';
import { cardStyles } from './timer-card.styles';

// Ensure HomeAssistant and TimerCardConfig are recognized from global.d.ts
interface TimerCardConfig {
  type: string;
  timer_instance_id?: string | null;
  entity?: string | null;
  sensor_entity?: string | null;
  timer_buttons: number[];
  card_title?: string | null;
  // Removed: notification_entity and show_seconds (now in backend config)
}

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
    show_seconds?: boolean; // NEW: This comes from backend now
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
const CARD_VERSION = "1.2.0";
const REPO_URL = "https://github.com/ArikShemesh/ha-simple-timer";
const DEFAULT_TIMER_BUTTONS = [15, 30, 60, 90, 120, 150]; // Default for new cards only

console.info(
  `%c SIMPLE-TIMER-CARD %c v${CARD_VERSION} `,
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
      _validationMessages: { state: true },
    };
  }

  hass?: HomeAssistant;
  _config?: TimerCardConfig;

  _countdownInterval: number | null = null;
  _liveRuntimeSeconds: number = 0;

  _timeRemaining: string | null = null;

  buttons: number[] = [];
  _validationMessages: string[] = [];
  _notificationSentForCurrentCycle: boolean = false;
  _entitiesLoaded: boolean = false;

  _effectiveSwitchEntity: string | null = null;
  _effectiveSensorEntity: string | null = null;

  static async getConfigElement(): Promise<HTMLElement> {
    await import("./timer-card-editor.js");
    return document.createElement("timer-card-editor");
  }

  static getStubConfig(_hass: HomeAssistant): TimerCardConfig {
    console.log("TimerCard: Generating stub config - NO auto-selection will be performed");
    
    return {
      type: "custom:timer-card",
      timer_instance_id: null, // Changed from auto-selected instance to null
      timer_buttons: [...DEFAULT_TIMER_BUTTONS], // Use default buttons
      card_title: "Simple Timer"
    };
  }

  setConfig(cfg: TimerCardConfig): void {
    this._config = {
      type: cfg.type || "custom:timer-card",
      timer_buttons: this._getValidatedTimerButtons(cfg.timer_buttons),
      card_title: cfg.card_title || null
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

    // Set buttons from validated config - could be empty array
    this.buttons = [...this._config.timer_buttons];

    this._liveRuntimeSeconds = 0;
    this._notificationSentForCurrentCycle = false;

    this._effectiveSwitchEntity = null;
    this._effectiveSensorEntity = null;
    this._entitiesLoaded = false;
    console.log(`TimerCard: setConfig completed. Configured instance ID: ${this._config.timer_instance_id}, Buttons: ${this.buttons.length}`);
  }

  _getValidatedTimerButtons(configButtons: any): number[] {
    let validatedTimerButtons: number[] = [];
    this._validationMessages = [];

    if (Array.isArray(configButtons)) {
        const invalidValues: any[] = [];
        const uniqueValues = new Set<number>();
        const duplicateValues: any[] = [];

        configButtons.forEach(val => {
            const numVal = Number(val);
            if (Number.isInteger(numVal) && numVal > 0 && numVal <= 1000) {
                if (uniqueValues.has(numVal)) {
                    duplicateValues.push(numVal);
                } else {
                    uniqueValues.add(numVal);
                    validatedTimerButtons.push(numVal);
                }
            } else {
                invalidValues.push(val);
            }
        });

        const messages: string[] = [];
        if (invalidValues.length > 0) {
            messages.push(`Invalid timer values ignored: ${invalidValues.join(', ')}. Only positive integers up to 1000 are allowed.`);
        }
        if (duplicateValues.length > 0) {
            messages.push(`Duplicate timer values were removed: ${[...new Set(duplicateValues)].join(', ')}.`);
        }
        this._validationMessages = messages;

        validatedTimerButtons.sort((a, b) => a - b);
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

	_startTimer(minutes: number): void {
        this._validationMessages = [];
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
			})
			.catch(error => {
				console.error("Timer-card: Error turning on switch or starting timer:", error);
			});
		this._notificationSentForCurrentCycle = false;
	}

	_cancelTimer(): void {
        this._validationMessages = [];
		if (!this._entitiesLoaded || !this.hass || !this.hass.callService) {
				console.error("Timer-card: Cannot cancel timer. Entities not loaded or callService unavailable.");
				return;
		}
		const entryId = this._getEntryId();
		if (!entryId) { console.error("Timer-card: Entry ID not found for cancelling timer."); return; }

		this.hass.callService(DOMAIN, "cancel_timer", { entry_id: entryId })
			.then(() => {
				// Backend handles notification
			})
			.catch(error => {
				console.error("Timer-card: Error cancelling timer:", error);
			});

		this._notificationSentForCurrentCycle = false;
	}

	_togglePower(): void {
        this._validationMessages = [];
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
						this.hass.callService(DOMAIN, "manual_power_toggle", { 
								entry_id: this._getEntryId(), 
								action: "turn_off" 
						});
						console.log(`Timer-card: Manually turning off switch: ${switchId}`);
				}
		} else {
			this.hass.callService(DOMAIN, "manual_power_toggle", { 
					entry_id: this._getEntryId(), 
					action: "turn_on" 
			})
				.then(() => {
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

	_hasOrphanedTimer(): { isOrphaned: boolean; duration?: number } {
		if (!this._entitiesLoaded || !this.hass || !this._effectiveSensorEntity) {
			return { isOrphaned: false };
		}

		const sensor = this.hass.states[this._effectiveSensorEntity];
		if (!sensor || sensor.attributes.timer_state !== 'active') {
			return { isOrphaned: false };
		}

		const activeDuration = sensor.attributes.timer_duration || 0;
		const hasMatchingButton = this.buttons.includes(activeDuration);

		return {
			isOrphaned: !hasMatchingButton,
			duration: activeDuration
		};
	}

  // NEW: Get show_seconds from the sensor attributes (backend config)
  _getShowSeconds(): boolean {
    if (!this._entitiesLoaded || !this.hass || !this._effectiveSensorEntity) {
      return false;
    }
    
    const sensor = this.hass.states[this._effectiveSensorEntity];
    // The backend will set this attribute based on the config entry
    return sensor?.attributes?.show_seconds || false;
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

    // Format time based on show_seconds setting from backend
    let formattedTime: string;
    let runtimeLabel: string;
    const showSeconds = this._getShowSeconds();

    if (showSeconds) {
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
		const orphanedTimer = this._hasOrphanedTimer();

    return html`
      <ha-card>
        <div class="card-header">
            <div class="card-title">${this._config?.card_title || ''}</div>
            <a href="${REPO_URL}" target="_blank" rel="noopener noreferrer" class="repo-link" title="Help">
                <ha-icon icon="mdi:help-circle-outline"></ha-icon>
            </a>
        </div>

        ${watchdogMessage ? html`
          <div class="status-message warning watchdog-banner">
            <ha-icon icon="mdi:alert-outline" class="status-icon"></ha-icon>
            <span class="status-text">${watchdogMessage}</span>
          </div>
        ` : ''}
				${orphanedTimer.isOrphaned ? html`
					<div class="status-message warning">
						<ha-icon icon="mdi:timer-alert-outline" class="status-icon"></ha-icon>
						<span class="status-text">
							Active ${orphanedTimer.duration}-minute timer has no corresponding button. 
							Use the power button to cancel or wait for automatic completion.
						</span>
					</div>
				` : ''}
        <div class="main-grid">
          <div class="button power-button ${isOn ? 'on' : ''}" @click=${this._togglePower}><ha-icon icon="mdi:power"></ha-icon></div>
          <div class="button readonly" @click=${this._showMoreInfo}>
            <span class="daily-time-text ${showSeconds ? 'with-seconds' : ''}">${formattedTime}</span>
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

  static get styles() {
    return cardStyles;
  }
}
customElements.define("timer-card", TimerCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "timer-card",
  name: "Simple Timer Card",
  description: "A card for the Simple Timer integration.",
});