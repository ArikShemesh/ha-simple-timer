// timer-card.ts

import { LitElement, html } from 'lit';
import { cardStyles } from './timer-card.styles';


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
    reset_time?: string; // NEW: Reset time from backend
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
      _sliderValue: { state: true },
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
	_sliderValue: number = 0;

  buttons: number[] = [];
  _validationMessages: string[] = [];
  _notificationSentForCurrentCycle: boolean = false;
  _entitiesLoaded: boolean = false;

  _effectiveSwitchEntity: string | null = null;
  _effectiveSensorEntity: string | null = null;
	
	_longPressTimer: number | null = null;
	_isLongPress: boolean = false;
	_touchStartPosition: { x: number; y: number } | null = null;
	_isCancelling: boolean = false;

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
      card_title: "Simple Timer",
			power_button_icon: "mdi:power"
    };
  }

  setConfig(cfg: TimerCardConfig): void {
		const newSliderMax = cfg.slider_max && cfg.slider_max > 0 && cfg.slider_max <= 1000 ? cfg.slider_max : 120;
		const instanceId = cfg.timer_instance_id || 'default';

		this._config = {
			type: cfg.type || "custom:timer-card",
			timer_buttons: this._getValidatedTimerButtons(cfg.timer_buttons),
			card_title: cfg.card_title || null,
			power_button_icon: cfg.power_button_icon || null,
			slider_max: newSliderMax,
			reverse_mode: cfg.reverse_mode || false,
			show_daily_usage: cfg.show_daily_usage !== false,
			timer_instance_id: instanceId,
			entity: cfg.entity,
			sensor_entity: cfg.sensor_entity
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
		if (isNaN(parsed) || parsed <= 0) {
			parsed = newSliderMax;
		}

		// Clamp if needed
		if (parsed > newSliderMax) {
			parsed = newSliderMax;
		}

		this._sliderValue = parsed;
		localStorage.setItem(`simple-timer-slider-${instanceId}`, this._sliderValue.toString());

		this.requestUpdate();

		this.buttons = [...this._config.timer_buttons];
		this._liveRuntimeSeconds = 0;
		this._notificationSentForCurrentCycle = false;
		this._effectiveSwitchEntity = null;
		this._effectiveSensorEntity = null;
		this._entitiesLoaded = false;
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

	_startTimer(minutes: number, startMethod: 'button' | 'slider' = 'button'): void {
        this._validationMessages = [];
		if (!this._entitiesLoaded || !this.hass || !this.hass.callService) {
				console.error("Timer-card: Cannot start timer. Entities not loaded or callService unavailable.");
				return;
		}
		
		const entryId = this._getEntryId();
		if (!entryId) { console.error("Timer-card: Entry ID not found for starting timer."); return; }

		const switchId = this._effectiveSwitchEntity!;
		const reverseMode = this._config?.reverse_mode || false;
		
		if (reverseMode) {
			// REVERSE MODE: Ensure switch is OFF, then start timer
			this.hass.callService("homeassistant", "turn_off", { entity_id: switchId })
				.then(() => {
					// Pass reverse mode info to backend via service call data
					this.hass!.callService(DOMAIN, "start_timer", { 
						entry_id: entryId, 
						duration: minutes,
						reverse_mode: true,
						start_method: startMethod
					});
				})
				.catch(error => {
					console.error("Timer-card: Error turning off switch for reverse timer:", error);
				});
		} else {
			// NORMAL MODE: Turn ON switch, then start timer
			this.hass.callService("homeassistant", "turn_on", { entity_id: switchId })
				.then(() => {
					this.hass!.callService(DOMAIN, "start_timer", { entry_id: entryId, duration: minutes, start_method: startMethod });
				})
				.catch(error => {
					console.error("Timer-card: Error turning on switch or starting timer:", error);
				});
		}
		
		this._notificationSentForCurrentCycle = false;
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

    this.hass.callService(DOMAIN, "cancel_timer", { entry_id: entryId })
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

  _togglePower(): void {
    this._validationMessages = [];
    if (!this._entitiesLoaded || !this.hass || !this.hass.states || !this.hass.callService) {
      console.error("Timer-card: Cannot toggle power. Entities not loaded or services unavailable.");
      return;
    }
    
    // Don't do anything if we're in the middle of cancelling
    if (this._isCancelling) {
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

    // PRIORITY 1: Check for active timer first (regardless of switch state)
    if (isTimerActive) {
      // Check if this is a reverse mode timer
      const isReverseMode = sensor.attributes.reverse_mode;
      
      if (isReverseMode) {
        // For reverse timers: cancel means "start now instead of waiting"
        this._cancelTimer();
        console.log(`Timer-card: Cancelling reverse timer and turning on switch: ${switchId}`);
      } else {
        // For normal timers: cancel means "stop and turn off"
        this._cancelTimer();
        console.log(`Timer-card: Cancelling normal timer for switch: ${switchId}`);
      }
      return;
    }

    // PRIORITY 2: Handle switch state for non-timer operations
    if (timerSwitch.state === 'on') {
      // Switch is on but no timer active - manual turn off
      this.hass.callService(DOMAIN, "manual_power_toggle", { 
        entry_id: this._getEntryId(), 
        action: "turn_off" 
      });
      console.log(`Timer-card: Manually turning off switch: ${switchId}`);
    } else {
      // Switch is currently OFF and no timer active
      if (this._sliderValue > 0) {
        this._startTimer(this._sliderValue, 'slider');
        console.log(`Timer-card: Starting timer for ${this._sliderValue} minutes`);
      } else {
        // Manual turn on (infinite until manually turned off)
        this.hass.callService(DOMAIN, "manual_power_toggle", { 
          entry_id: this._getEntryId(), 
          action: "turn_on" 
        })
        .then(() => {
          console.log(`Timer-card: Manually turning on switch (infinite): ${switchId}`);
        })
        .catch(error => {
          console.error("Timer-card: Error manually turning on switch:", error);
        });
      }
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
          
          // Format countdown based on show_seconds setting
          const showSeconds = this._getShowSeconds();
          if (showSeconds) {
            const hours = Math.floor(remaining / 3600);
            const minutes = Math.floor((remaining % 3600) / 60);
            const seconds = remaining % 60;
            this._timeRemaining = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
          } else {
            const minutes = Math.floor(remaining / 60);
            const seconds = remaining % 60;
            this._timeRemaining = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
          }

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
		const sliderMax = this._config?.slider_max || 120;
		const isWithinSliderRange = activeDuration >= 0 && activeDuration <= sliderMax;

		return {
			isOrphaned: !hasMatchingButton && !isWithinSliderRange,
			duration: activeDuration
		};
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
	
	_handlePowerClick(event: Event): void {
    // Only handle mouse clicks, not touch events
    if (event.type === 'click' && !this._isLongPress) {
        event.preventDefault();
        event.stopPropagation();
        this._togglePower();
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
		const orphanedTimer = this._hasOrphanedTimer();

		return html`
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
        ${orphanedTimer.isOrphaned ? html`
          <div class="status-message warning">
            <ha-icon icon="mdi:timer-alert-outline" class="status-icon"></ha-icon>
            <span class="status-text">
              Active ${orphanedTimer.duration}-minute timer has no corresponding button. 
              Use the power button to cancel or wait for automatic completion.
            </span>
          </div>
        ` : ''}

        <div class="card-content">

          <!-- Countdown Display Section -->
          <div class="countdown-section">
            <div class="countdown-display ${isTimerActive ? 'active' : ''} ${isReverseMode ? 'reverse' : ''}">
              ${countdownDisplay}
            </div>
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
          <div class="slider-row">
            <div class="slider-container">
              <input
                type="range"
                min="0"
								step="1"
                max="${this._config?.slider_max || 120}"
                .value=${this._sliderValue.toString()}
                @input=${this._handleSliderChange}
                class="timer-slider"
              />
              <span class="slider-label">${this._sliderValue} min</span>
            </div>
            <div class="power-button-small ${isTimerActive && isReverseMode ? 'on reverse' : isOn ? 'on' : this._config?.reverse_mode ? 'reverse' : ''}" 
								 @click=${this._handlePowerClick}
								 title="Click to toggle power">
							${this._config?.power_button_icon ? html`<ha-icon icon="${this._config.power_button_icon}"></ha-icon>` : ''}
						</div>
          </div>

          <!-- Timer Buttons -->
          <div class="button-grid">
            ${this.buttons.map(minutes => {
              // Only highlight if timer was started via button, NOT slider
              const isActive = isTimerActive && timerDurationInMinutes === minutes && sensor.attributes.timer_start_method === 'button';
              const isDisabled = isManualOn || (isTimerActive && !isActive);
              return html`
                <div class="timer-button ${isActive ? 'active' : ''} ${isDisabled ? 'disabled' : ''}" 
                     @click=${() => {
												if (isActive) this._cancelTimer(); 
												else if (!isDisabled) {
														this._startTimer(minutes, 'button');
												}
										}}>
                  <div class="timer-button-value">${minutes}</div>
                  <div class="timer-button-unit">Min</div>
                </div>
              `;
            })}
          </div>
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