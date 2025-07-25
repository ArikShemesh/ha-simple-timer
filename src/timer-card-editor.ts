// timer-card-editor.ts

import { LitElement, html } from 'lit';
import { editorCardStyles } from './timer-card-editor.styles';

// Define necessary interfaces directly in this file for compilation robustness.
interface TimerCardConfig {
  type: string;
  timer_instance_id?: string | null;
  entity?: string | null;
  sensor_entity?: string | null;
  timer_buttons: number[];
  notification_entity?: string | null;
  card_title?: string | null;
  show_seconds?: boolean; // NEW: Option to show seconds in daily usage
}

interface HAState {
  entity_id: string;
  state: string;
  attributes: {
    friendly_name?: string;
    entry_id?: string;
    switch_entity_id?: string;
    instance_title?: string;
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

interface HAService {
  description: string;
  fields: {
    [field: string]: {
      description: string;
      example: string;
    };
  };
}

interface HomeAssistant {
  states: {
    [entityId: string]: HAState;
  };
  services: {
    notify?: { [service: string]: HAService };
    switch?: { [service: string]: HAService };
    [domain: string]: { [service: string]: HAService } | undefined;
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

interface HAConfigEntry {
  entry_id: string;
  title: string;
  domain: string;
}

interface HAConfigEntriesByDomainResponse {
  entry_by_domain: {
    [domain: string]: HAConfigEntry[];
  };
}

const ATTR_INSTANCE_TITLE = "instance_title";
const DOMAIN = "simple_timer";
const DEFAULT_TIMER_BUTTONS = [15, 30, 60, 90, 120, 150]; // Default for new cards only

class TimerCardEditor extends LitElement {
  static properties = {
    hass: { type: Object },
    _config: { type: Object },
  };

  hass?: HomeAssistant;
  _config: TimerCardConfig;
  _configFullyLoaded: boolean = false; // Track if we've received a complete config

  private _timerInstancesOptions: Array<{ value: string; label: string }> = [];

  constructor() {
    super();
    this._config = {
      type: "custom:timer-card",
      timer_buttons: [...DEFAULT_TIMER_BUTTONS], // Use centralized default
      notification_entity: null,
      timer_instance_id: null,
      card_title: null,
      show_seconds: false
    };
  }

  async _getSimpleTimerInstances(): Promise<Array<{ value: string; label: string }>> {
    if (!this.hass || !this.hass.states) {
      console.warn("TimerCardEditor: hass.states not available when trying to fetch instances from states.");
      return [];
    }

    const instancesMap = new Map<string, { value: string; label: string }>();

    for (const entityId in this.hass.states) {
      const state = this.hass.states[entityId];

      // UPDATED: Look for sensors that have the required simple timer attributes
      // The entity name format is now: "[Instance Name] Runtime ([entry_id_short])"
      if (entityId.startsWith('sensor.') &&
          entityId.includes('runtime') &&  // Runtime sensors contain 'runtime' in their ID
          state.attributes.entry_id &&
          typeof state.attributes.entry_id === 'string' &&
          state.attributes.switch_entity_id &&
          typeof state.attributes.switch_entity_id === 'string'
         ) {
        const entryId = state.attributes.entry_id;
        const instanceTitle = state.attributes[ATTR_INSTANCE_TITLE];

        let instanceLabel = `Timer Control (${entryId.substring(0, 8)})`;

        console.debug(`TimerCardEditor: Processing sensor ${entityId} (Entry: ${entryId})`);
        console.debug(`TimerCardEditor: Found raw attribute '${ATTR_INSTANCE_TITLE}': ${instanceTitle}`);
        console.debug(`TimerCardEditor: Type of raw attribute: ${typeof instanceTitle}`);

        if (instanceTitle && typeof instanceTitle === 'string' && instanceTitle.trim() !== '') {
            instanceLabel = instanceTitle.trim();
            console.debug(`TimerCardEditor: Using '${ATTR_INSTANCE_TITLE}' for label: "${instanceLabel}"`);
        } else {
            console.warn(`TimerCardEditor: Sensor '${entityId}' has no valid '${ATTR_INSTANCE_TITLE}' attribute. Falling back to entry ID based label: "${instanceLabel}".`);
        }

        if (!instancesMap.has(entryId)) {
          instancesMap.set(entryId, { value: entryId, label: instanceLabel });
          console.debug(`TimerCardEditor: Added instance: ${instanceLabel} (${entryId}) from sensor: ${entityId}`);
        } else {
            console.debug(`TimerCardEditor: Skipping duplicate entry_id: ${entryId}`);
        }
      }
    }

    const instances = Array.from(instancesMap.values());
    instances.sort((a, b) => a.label.localeCompare(b.label));

    if (instances.length === 0) {
        console.info(`TimerCardEditor: No Simple Timer integration instances found by scanning hass.states.`);
    } else {
        console.info("TimerCardEditor: Found Simple Timer instances by scanning states:", instances);
    }
    return instances;
  }

  _getNotificationServiceTargets(): Array<{ value: string; label: string }> {
    if (!this.hass || !this.hass.services) {
      return [];
    }
    const targets: Array<{ value: string; label: string }> = [];

    if (this.hass.services.notify) {
      for (const serviceName in this.hass.services.notify) {
        if (serviceName !== "send" && !serviceName.includes("_all") && !serviceName.includes("_group")) {
          const friendlyName = this.hass.services.notify[serviceName]?.description || serviceName;
          targets.push({ value: `notify.${serviceName}`, label: friendlyName });
        }
      }
    }

    for (const domain in this.hass.services) {
      if (domain.includes("telegram") || domain.includes("mobile_app")) {
        const domainServices = this.hass.services[domain];
        for (const serviceName in domainServices) {
          if (serviceName.includes("send") || serviceName.includes("message") || serviceName.includes("notify")) {
            const fullService = `${domain}.${serviceName}`;
            if (!targets.some(t => t.value === fullService)) {
                const friendlyName = domainServices[serviceName]?.description || fullService;
                targets.push({ value: fullService, label: friendlyName });
            }
          }
        }
      }
    }
    targets.sort((a, b) => a.label.localeCompare(b.label));
    return targets;
  }
	
	_getValidatedTimerButtons(configButtons: any): number[] {
    if (Array.isArray(configButtons)) {
        const validatedButtons: number[] = [];
        const seen = new Set<number>();

        configButtons.forEach(val => {
            const numVal = Number(val);
            if (Number.isInteger(numVal) && numVal > 0 && numVal <= 1000) {
                if (!seen.has(numVal)) {
                    validatedButtons.push(numVal);
                    seen.add(numVal);
                }
            }
        });

        validatedButtons.sort((a, b) => a - b);
        console.log(`TimerCardEditor: Using ${validatedButtons.length} timer buttons from config:`, validatedButtons);
        return validatedButtons;
    }

    if (configButtons === undefined || configButtons === null) {
        console.log(`TimerCardEditor: No timer_buttons in config, using empty array.`);
        return [];
    }

    console.warn(`TimerCardEditor: Invalid timer_buttons type (${typeof configButtons}):`, configButtons, `- using empty array`);
    return [];
	}

  async setConfig(cfg: TimerCardConfig): Promise<void> {
    console.log(`TimerCardEditor: setConfig called with:`, cfg);
    const oldConfig = { ...this._config };

    const timerButtonsToSet = this._getValidatedTimerButtons(cfg.timer_buttons);

    const newConfigData: TimerCardConfig = {
      type: cfg.type || "custom:timer-card",
      timer_buttons: timerButtonsToSet,
      card_title: cfg.card_title || null,
      show_seconds: cfg.show_seconds || false
    };

    if (cfg.timer_instance_id) {
        newConfigData.timer_instance_id = cfg.timer_instance_id;
        console.info(`TimerCardEditor: setConfig PRESERVING existing timer_instance_id: '${cfg.timer_instance_id}'`);
    } else {
        console.info(`TimerCardEditor: setConfig - no timer_instance_id in config, will be auto-selected later`);
    }

    if (cfg.entity) newConfigData.entity = cfg.entity;
    if (cfg.sensor_entity) newConfigData.sensor_entity = cfg.sensor_entity;
    if (cfg.notification_entity) newConfigData.notification_entity = cfg.notification_entity;

    this._config = newConfigData;
    this._configFullyLoaded = true;
    
    console.log(`TimerCardEditor: setConfig result:`, this._config);
    
    if (JSON.stringify(oldConfig) !== JSON.stringify(this._config)) {
        console.log(`TimerCardEditor: Config changed, dispatching config-changed event`);
        this.dispatchEvent(
            new CustomEvent("config-changed", { detail: { config: this._config } })
        );
    } else {
        console.log(`TimerCardEditor: Config unchanged, not dispatching event`);
    }
    
    this.requestUpdate();
  }

  get _schema(): any[] {
    const timerInstances = this._timerInstancesOptions || [];
    const notificationServiceTargets = this._getNotificationServiceTargets();

    const instanceOptions = timerInstances.length > 0
        ? timerInstances
        : [{ value: "none_found", label: "No Simple Timer Instances Found" }];

    const notificationOptions = [{ value: "none_selected", label: "None" }];
    notificationServiceTargets.forEach(target => notificationOptions.push(target));

    return [
      {
        name: "card_title",
        label: "Card Title (Optional)",
        selector: {
          text: {
            type: "text"
          }
        }
      },
      {
        name: "timer_instance_id",
        label: "Simple Timer Instance",
        required: true,
        selector: {
          select: {
            options: instanceOptions,
            mode: "dropdown",
          },
        },
      },
      {
        name: "show_seconds",
        label: "Show Seconds in Daily Usage",
        selector: {
          boolean: {}
        }
      },
      {
        name: "notification_entity",
        label: "Notification Service Target (Optional)",
        selector: {
          select: {
            options: notificationOptions,
            custom_value: false,
          },
        },
      },
    ];
  }

  connectedCallback() {
      super.connectedCallback();
      if (this.hass) {
          this._fetchTimerInstances();
      } else {
          console.warn("TimerCardEditor: hass not available on connectedCallback. Deferring instance fetch.");
      }
  }

  updated(changedProperties: Map<string | number | symbol, unknown>): void {
      super.updated(changedProperties);
      if (changedProperties.has("hass") && this.hass) {
          if ((changedProperties.get("hass") as any)?.states !== this.hass.states || this._timerInstancesOptions.length === 0) {
               console.log("TimerCardEditor: hass.states changed or instances not yet fetched, re-fetching instances.");
               this._fetchTimerInstances();
          }
      }
  }

  async _fetchTimerInstances() {
      if (this.hass) {
          console.log(`TimerCardEditor: _fetchTimerInstances called. Config loaded: ${this._configFullyLoaded}, Current config timer_instance_id: '${this._config?.timer_instance_id}'`);
          
          this._timerInstancesOptions = await this._getSimpleTimerInstances();
          console.log(`TimerCardEditor: Found ${this._timerInstancesOptions.length} instances:`, this._timerInstancesOptions);
          
          if (!this._configFullyLoaded) {
              console.info(`TimerCardEditor: Config not fully loaded yet, skipping any auto-selection logic`);
              this.requestUpdate();
              return;
          }
          
          const hasNoInstanceConfigured = !this._config?.timer_instance_id || 
                                        this._config.timer_instance_id === "none_found" ||
                                        this._config.timer_instance_id === "";
          const hasAvailableInstances = this._timerInstancesOptions.length > 0;
          
          console.log(`TimerCardEditor: hasNoInstanceConfigured: ${hasNoInstanceConfigured}, hasAvailableInstances: ${hasAvailableInstances}`);
          
          if (hasNoInstanceConfigured && hasAvailableInstances) {
              const firstInstance = this._timerInstancesOptions[0];
              console.info(`TimerCardEditor: AUTO-SELECTING first available instance (no valid instance configured): '${firstInstance.value}' (${firstInstance.label})`);
              
              const updatedConfig: TimerCardConfig = {
                  ...this._config,
                  timer_instance_id: firstInstance.value
              };
              
              this._config = updatedConfig;
              this.dispatchEvent(
                  new CustomEvent("config-changed", {
                      detail: { config: this._config },
                      bubbles: true,
                      composed: true,
                  }),
              );
          } else if (this._config?.timer_instance_id && hasAvailableInstances) {
              const currentInstanceExists = this._timerInstancesOptions.some(
                  instance => instance.value === this._config!.timer_instance_id
              );
              
              if (!currentInstanceExists) {
                  console.warn(`TimerCardEditor: Previously configured instance '${this._config.timer_instance_id}' no longer exists. Auto-selecting first available instance.`);
                  const firstInstance = this._timerInstancesOptions[0];
                  
                  const updatedConfig: TimerCardConfig = {
                      ...this._config,
                      timer_instance_id: firstInstance.value
                  };
                  
                  this._config = updatedConfig;
                  this.dispatchEvent(
                      new CustomEvent("config-changed", {
                          detail: { config: this._config },
                          bubbles: true,
                          composed: true,
                      }),
                  );
              } else {
                  console.info(`TimerCardEditor: PRESERVING existing valid instance: '${this._config.timer_instance_id}'`);
              }
          } else if (!hasAvailableInstances) {
              console.warn(`TimerCardEditor: No simple timer instances found.`);
          }
          
          this.requestUpdate();
      }
  }

  _allTimerOptions: number[] = [1, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165, 180];

  _handleTimerCheckboxChange(event: Event): void {
    const inputElement = event.target as HTMLInputElement;
    const value = parseInt(inputElement.value);
    const isChecked = inputElement.checked;
    let currentButtons = Array.isArray(this._config?.timer_buttons) ? [...this._config!.timer_buttons] : [];

    if (isChecked) {
      if (!currentButtons.includes(value)) {
        currentButtons.push(value);
      }
    } else {
      currentButtons = currentButtons.filter(button => button !== value);
    }

    currentButtons.sort((a, b) => a - b);

    const updatedConfig: TimerCardConfig = {
        type: this._config!.type,
        timer_buttons: currentButtons,
        show_seconds: this._config!.show_seconds || false
    };
    if (this._config?.timer_instance_id) updatedConfig.timer_instance_id = this._config.timer_instance_id;
    if (this._config?.entity) updatedConfig.entity = this._config.entity;
    if (this._config?.sensor_entity) updatedConfig.sensor_entity = this._config.sensor_entity;
    if (this._config?.notification_entity) updatedConfig.notification_entity = this._config.notification_entity;
    if (this._config?.card_title) updatedConfig.card_title = this._config.card_title;

    this._config = updatedConfig;
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: this._config },
        bubbles: true,
        composed: true,
      }),
    );
    this.requestUpdate();
  }

  render() {
    if (!this.hass) return html``;

    return html`
      <ha-form
        .hass=${this.hass}
        .data=${this._config}
        .schema=${this._schema}
        @value-changed=${this._valueChanged}
      ></ha-form>

      <div class="card-config-group">
        <h3>Select your timers (Minutes)</h3>
        <div class="checkbox-grid">
          ${this._allTimerOptions.map(value => html`
            <label class="checkbox-label">
              <input
                type="checkbox"
                value="${value}"
                .checked=${Array.isArray(this._config?.timer_buttons) && this._config!.timer_buttons.includes(value)}
                @change=${this._handleTimerCheckboxChange}
              >
              ${value}
            </label>
          `)}
        </div>
        <div class="timer-buttons-info">
          ${!this._config?.timer_buttons?.length ? html`
            <p class="info-text">ℹ️ No timer buttons selected. Only power toggle and daily usage will be shown.</p>
          ` : ''}
        </div>
      </div>
    `;
  }

  _valueChanged(ev: CustomEvent): void {
    ev.stopPropagation();
    const newFormValues = ev.detail.value;

    if (!this._config) {
      console.warn("TimerCardEditor: _config is null in _valueChanged, deferring update.");
      return;
    }

    const updatedConfig: TimerCardConfig = {
        type: newFormValues.type || this._config.type || "custom:timer-card",
        timer_buttons: this._config.timer_buttons,
        show_seconds: newFormValues.show_seconds !== undefined ? newFormValues.show_seconds : (this._config.show_seconds || false)
    };

    if (newFormValues.timer_instance_id && newFormValues.timer_instance_id !== "none_found") {
        updatedConfig.timer_instance_id = newFormValues.timer_instance_id;
    } else {
        delete updatedConfig.timer_instance_id;
    }

    if (this._config.entity) updatedConfig.entity = this._config.entity;
    if (this._config.sensor_entity) updatedConfig.sensor_entity = this._config.sensor_entity;

    if (newFormValues.notification_entity && newFormValues.notification_entity !== "none_selected") {
        updatedConfig.notification_entity = newFormValues.notification_entity;
    } else if (newFormValues.notification_entity === "none_selected") {
        delete updatedConfig.notification_entity;
    } else if (this._config.notification_entity) {
        updatedConfig.notification_entity = this._config.notification_entity;
    }

    if (newFormValues.card_title && newFormValues.card_title !== '') {
        updatedConfig.card_title = newFormValues.card_title;
    } else {
        delete updatedConfig.card_title;
    }

    if (JSON.stringify(this._config) !== JSON.stringify(updatedConfig)) {
        this._config = updatedConfig;
        this.dispatchEvent(
            new CustomEvent("config-changed", {
                detail: { config: this._config },
                bubbles: true,
                composed: true,
            }),
        );
        this.requestUpdate();
    }
  }

  static get styles() {
    return editorCardStyles;
  }
}

customElements.define("timer-card-editor", TimerCardEditor);
