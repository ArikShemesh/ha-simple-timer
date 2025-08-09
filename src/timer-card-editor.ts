// timer-card-editor.ts

import { LitElement, html } from 'lit';
import { editorCardStyles } from './timer-card-editor.styles';

// Note: TimerCardConfig interface is defined in global.d.ts

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
      timer_instance_id: null,
      card_title: null
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

      // Look for sensors that have the required simple timer attributes
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
      card_title: cfg.card_title || null
    };

    if (cfg.timer_instance_id) {
        newConfigData.timer_instance_id = cfg.timer_instance_id;
        console.info(`TimerCardEditor: setConfig PRESERVING existing timer_instance_id: '${cfg.timer_instance_id}'`);
    } else {
        console.info(`TimerCardEditor: setConfig - no timer_instance_id in config, will remain unset`);
    }

    // Legacy support for old config properties
    if (cfg.entity) newConfigData.entity = cfg.entity;
    if (cfg.sensor_entity) newConfigData.sensor_entity = cfg.sensor_entity;

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
          
          // Only validate that existing configured instances still exist
          if (this._config?.timer_instance_id && this._timerInstancesOptions.length > 0) {
              const currentInstanceExists = this._timerInstancesOptions.some(
                  instance => instance.value === this._config!.timer_instance_id
              );
              
              if (!currentInstanceExists) {
                  console.warn(`TimerCardEditor: Previously configured instance '${this._config.timer_instance_id}' no longer exists. User will need to select a new instance.`);
                  // Clear the invalid instance ID so user sees "Please select an instance"
                  const updatedConfig: TimerCardConfig = {
                      ...this._config,
                      timer_instance_id: null
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
          } else {
              console.info(`TimerCardEditor: No timer_instance_id configured or no instances available. User must manually select.`);
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
        timer_buttons: currentButtons
    };
    if (this._config?.timer_instance_id) updatedConfig.timer_instance_id = this._config.timer_instance_id;
    if (this._config?.entity) updatedConfig.entity = this._config.entity;
    if (this._config?.sensor_entity) updatedConfig.sensor_entity = this._config.sensor_entity;
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

    const timerInstances = this._timerInstancesOptions || [];

    const instanceOptions = [{ value: "", label: "None" }];
    
    if (timerInstances.length > 0) {
        instanceOptions.push(...timerInstances);
    } else {
        instanceOptions.push({ value: "none_found", label: "No Simple Timer Instances Found" });
    }

    return html`
      <div class="card-config">
        <div class="config-row">
          <ha-textfield
            .label=${"Card Title (optional)"}
            .value=${this._config?.card_title || ""}
            .configValue=${"card_title"}
            @input=${this._valueChanged}
            .placeholder=${"Optional title for the card"}
          ></ha-textfield>
        </div>
        
        <div class="config-row">
          <ha-select
            .label=${"Select Simple Timer Instance"}
            .value=${this._config?.timer_instance_id || ""}
            .configValue=${"timer_instance_id"}
            @selected=${this._valueChanged}
            @closed=${(ev) => ev.stopPropagation()}
            fixedMenuPosition
            naturalMenuWidth
            required
          >
            ${instanceOptions.map(option => html`
              <mwc-list-item .value=${option.value}>
                ${option.label}
              </mwc-list-item>
            `)}
          </ha-select>
        </div>
				
      </div>

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

  _valueChanged(ev: Event): void {
    ev.stopPropagation();
    const target = ev.target as any;
    
    if (!this._config || !target.configValue) {
      return;
    }

    const configValue = target.configValue;
    let value;
    
    if (target.checked !== undefined) {
      value = target.checked;
    } else if (target.selected !== undefined) {
      value = target.value;
    } else if (target.value !== undefined) {
      value = target.value;
    } else {
      return;
    }

    const updatedConfig: TimerCardConfig = {
        type: this._config.type || "custom:timer-card",
        timer_buttons: this._config.timer_buttons
    };

    // Handle specific field updates
    if (configValue === "card_title") {
        if (value && value !== '') {
            updatedConfig.card_title = value;
        } else {
            delete updatedConfig.card_title;
        }
    } else if (configValue === "timer_instance_id") {
        if (value && value !== "none_found" && value !== "") {
            updatedConfig.timer_instance_id = value;
        } else {
            updatedConfig.timer_instance_id = null;
        }
    }

    // Preserve existing values
    if (this._config.entity) updatedConfig.entity = this._config.entity;
    if (this._config.sensor_entity) updatedConfig.sensor_entity = this._config.sensor_entity;
    if (this._config.timer_instance_id && configValue !== "timer_instance_id") {
        updatedConfig.timer_instance_id = this._config.timer_instance_id;
    }
    if (this._config.card_title && configValue !== "card_title") {
        updatedConfig.card_title = this._config.card_title;
    }

    if (JSON.stringify(this._config) !== JSON.stringify(updatedConfig)) {
        this._config = updatedConfig;
        
        // Clean up any old notification/show_seconds properties when saving
        const cleanConfig: any = { ...updatedConfig };
        delete cleanConfig.notification_entity;
        delete cleanConfig.show_seconds;
        
        this.dispatchEvent(
            new CustomEvent("config-changed", {
                detail: { config: cleanConfig },
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