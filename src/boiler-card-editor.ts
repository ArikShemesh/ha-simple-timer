// boiler-card-editor.ts

import { LitElement, html, css } from 'lit';

// Define necessary interfaces directly in this file for compilation robustness.
// In a full project setup, these might reside in a shared 'global.d.ts' or types file.

interface BoilerCardConfig {
  type: string;
  boiler_instance_id?: string | null;
  entity?: string | null;
  sensor_entity?: string | null;
  timer_buttons: number[];
  notification_entity?: string | null;
  card_title?: string | null;
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

const DOMAIN = "boiler_control";

class BoilerCardEditor extends LitElement {
  static properties = {
    hass: { type: Object },
    _config: { type: Object },
  };

  hass?: HomeAssistant;
  _config: BoilerCardConfig;
  _configFullyLoaded: boolean = false; // Track if we've received a complete config

  private _boilerInstancesOptions: Array<{ value: string; label: string }> = [];

  constructor() {
    super();
    this._config = {
      type: "custom:boiler-card",
      timer_buttons: [15, 30, 60, 90, 120, 150],
      notification_entity: null,
      boiler_instance_id: null,
      card_title: null
    };
  }

  async _getBoilerControlInstances(): Promise<Array<{ value: string; label: string }>> {
    if (!this.hass || !this.hass.states) {
      console.warn("BoilerCardEditor: hass.states not available when trying to fetch instances from states.");
      return [];
    }

    const instancesMap = new Map<string, { value: string; label: string }>();

    for (const entityId in this.hass.states) {
      const state = this.hass.states[entityId];
      
      // UPDATED: Look for sensors that have the required boiler control attributes
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

        let instanceLabel = `Boiler Control (${entryId.substring(0, 8)})`;

        console.debug(`BoilerCardEditor: Processing sensor ${entityId} (Entry: ${entryId})`);
        console.debug(`BoilerCardEditor: Found raw attribute '${ATTR_INSTANCE_TITLE}': ${instanceTitle}`);
        console.debug(`BoilerCardEditor: Type of raw attribute: ${typeof instanceTitle}`);

        if (instanceTitle && typeof instanceTitle === 'string' && instanceTitle.trim() !== '') {
            instanceLabel = instanceTitle.trim();
            console.debug(`BoilerCardEditor: Using '${ATTR_INSTANCE_TITLE}' for label: "${instanceLabel}"`);
        } else {
            console.warn(`BoilerCardEditor: Sensor '${entityId}' has no valid '${ATTR_INSTANCE_TITLE}' attribute. Falling back to entry ID based label: "${instanceLabel}".`);
        }
        
        if (!instancesMap.has(entryId)) {
          instancesMap.set(entryId, { value: entryId, label: instanceLabel });
          console.debug(`BoilerCardEditor: Added instance: ${instanceLabel} (${entryId}) from sensor: ${entityId}`);
        } else {
            console.debug(`BoilerCardEditor: Skipping duplicate entry_id: ${entryId}`);
        }
      }
    }

    const instances = Array.from(instancesMap.values());
    instances.sort((a, b) => a.label.localeCompare(b.label));

    if (instances.length === 0) {
        console.info(`BoilerCardEditor: No Boiler Control integration instances found by scanning hass.states.`);
    } else {
        console.info("BoilerCardEditor: Found Boiler Control instances by scanning states:", instances);
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

  async setConfig(cfg: BoilerCardConfig): Promise<void> {
    console.log(`BoilerCardEditor: setConfig called with:`, cfg);
    const oldConfig = { ...this._config };

    const timerButtonsToSet = Array.isArray(cfg.timer_buttons)
      ? [...cfg.timer_buttons].filter(val => Number.isInteger(val) && val > 0 && val <= 1000)
      : [15, 30, 60, 90, 120, 150];

    const newConfigData: BoilerCardConfig = {
      type: cfg.type || "custom:boiler-card",
      timer_buttons: timerButtonsToSet.sort((a, b) => a - b),
      card_title: cfg.card_title || null
    };

    // SIMPLIFIED: Just preserve the boiler_instance_id as-is from the config
    // Don't do any auto-selection here - let _fetchBoilerInstances handle that
    if (cfg.boiler_instance_id) {
        newConfigData.boiler_instance_id = cfg.boiler_instance_id;
        console.info(`BoilerCardEditor: setConfig PRESERVING existing boiler_instance_id: '${cfg.boiler_instance_id}'`);
    } else {
        console.info(`BoilerCardEditor: setConfig - no boiler_instance_id in config, will be auto-selected later`);
    }

    // Preserve other legacy config fields if they exist
    if (cfg.entity) newConfigData.entity = cfg.entity;
    if (cfg.sensor_entity) newConfigData.sensor_entity = cfg.sensor_entity;
    if (cfg.notification_entity) newConfigData.notification_entity = cfg.notification_entity;

    // IMPORTANT: Set the config immediately, don't use setTimeout tricks
    this._config = newConfigData;
    
    // Mark that we've received a complete config (this prevents premature auto-selection)
    this._configFullyLoaded = true;
    
    console.log(`BoilerCardEditor: setConfig result:`, this._config);
    
    // Only dispatch if config actually changed
    if (JSON.stringify(oldConfig) !== JSON.stringify(this._config)) {
        console.log(`BoilerCardEditor: Config changed, dispatching config-changed event`);
        this.dispatchEvent(
            new CustomEvent("config-changed", { detail: { config: this._config } })
        );
    } else {
        console.log(`BoilerCardEditor: Config unchanged, not dispatching event`);
    }
    
    this.requestUpdate();
  }

  get _schema(): any[] {
    const boilerInstances = this._boilerInstancesOptions || [];
    const notificationServiceTargets = this._getNotificationServiceTargets();

    const instanceOptions = boilerInstances.length > 0
        ? boilerInstances
        : [{ value: "none_found", label: "No Boiler Control Instances Found" }];

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
        name: "boiler_instance_id",
        label: "Boiler Control Instance",
        required: true,
        selector: {
          select: {
            options: instanceOptions,
            mode: "dropdown",
          },
        },
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
          this._fetchBoilerInstances();
      } else {
          console.warn("BoilerCardEditor: hass not available on connectedCallback. Deferring instance fetch.");
      }
  }

  updated(changedProperties: Map<string | number | symbol, unknown>): void {
      super.updated(changedProperties);
      if (changedProperties.has("hass") && this.hass) {
          if ((changedProperties.get("hass") as any)?.states !== this.hass.states || this._boilerInstancesOptions.length === 0) {
               console.log("BoilerCardEditor: hass.states changed or instances not yet fetched, re-fetching instances.");
               this._fetchBoilerInstances();
          }
      }
  }

  async _fetchBoilerInstances() {
      if (this.hass) {
          console.log(`BoilerCardEditor: _fetchBoilerInstances called. Config loaded: ${this._configFullyLoaded}, Current config boiler_instance_id: '${this._config?.boiler_instance_id}'`);
          
          this._boilerInstancesOptions = await this._getBoilerControlInstances();
          console.log(`BoilerCardEditor: Found ${this._boilerInstancesOptions.length} instances:`, this._boilerInstancesOptions);
          
          // CRITICAL: Only allow auto-selection if we're sure the config is fully loaded
          // This prevents overriding user selections when the editor is re-opened
          if (!this._configFullyLoaded) {
              console.info(`BoilerCardEditor: Config not fully loaded yet, skipping any auto-selection logic`);
              this.requestUpdate();
              return;
          }
          
          // AUTO-SELECT: Only auto-select if NO instance is currently configured
          // AND instances are available. Don't override existing valid selections.
          const hasNoInstanceConfigured = !this._config?.boiler_instance_id || 
                                        this._config.boiler_instance_id === "none_found" ||
                                        this._config.boiler_instance_id === "";
          const hasAvailableInstances = this._boilerInstancesOptions.length > 0;
          
          console.log(`BoilerCardEditor: hasNoInstanceConfigured: ${hasNoInstanceConfigured}, hasAvailableInstances: ${hasAvailableInstances}`);
          
          if (hasNoInstanceConfigured && hasAvailableInstances) {
              const firstInstance = this._boilerInstancesOptions[0];
              console.info(`BoilerCardEditor: AUTO-SELECTING first available instance (no valid instance configured): '${firstInstance.value}' (${firstInstance.label})`);
              
              // Update the config to include the auto-selected instance
              const updatedConfig: BoilerCardConfig = {
                  ...this._config,
                  boiler_instance_id: firstInstance.value
              };
              
              this._config = updatedConfig;
              this.dispatchEvent(
                  new CustomEvent("config-changed", {
                      detail: { config: this._config },
                      bubbles: true,
                      composed: true,
                  }),
              );
          } else if (this._config?.boiler_instance_id && hasAvailableInstances) {
              // Verify that the currently configured instance still exists
              const currentInstanceExists = this._boilerInstancesOptions.some(
                  instance => instance.value === this._config!.boiler_instance_id
              );
              
              if (!currentInstanceExists) {
                  console.warn(`BoilerCardEditor: Previously configured instance '${this._config.boiler_instance_id}' no longer exists. Auto-selecting first available instance.`);
                  const firstInstance = this._boilerInstancesOptions[0];
                  
                  const updatedConfig: BoilerCardConfig = {
                      ...this._config,
                      boiler_instance_id: firstInstance.value
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
                  console.info(`BoilerCardEditor: PRESERVING existing valid instance: '${this._config.boiler_instance_id}'`);
              }
          } else if (!hasAvailableInstances) {
              console.warn(`BoilerCardEditor: No boiler control instances found.`);
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

    const updatedConfig: BoilerCardConfig = {
        type: this._config!.type,
        timer_buttons: currentButtons,
    };
    if (this._config?.boiler_instance_id) updatedConfig.boiler_instance_id = this._config.boiler_instance_id;
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
      </div>
    `;
  }

  _valueChanged(ev: CustomEvent): void {
    ev.stopPropagation();
    const newFormValues = ev.detail.value;

    if (!this._config) {
      console.warn("BoilerCardEditor: _config is null in _valueChanged, deferring update.");
      return;
    }

    const updatedConfig: BoilerCardConfig = {
        type: newFormValues.type || this._config.type || "custom:boiler-card",
        timer_buttons: this._config.timer_buttons
    };

    if (newFormValues.boiler_instance_id && newFormValues.boiler_instance_id !== "none_found") {
        updatedConfig.boiler_instance_id = newFormValues.boiler_instance_id;
    } else {
        delete updatedConfig.boiler_instance_id;
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

    // Handle card_title from newFormValues
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
    return css`
      .card-config-group {
        padding: 16px;
        background-color: var(--card-background-color);
        border-top: 1px solid var(--divider-color);
        margin-top: 16px;
      }
      h3 {
        margin-top: 0;
        margin-bottom: 16px;
        font-size: 1.1em;
        font-weight: normal;
        color: var(--primary-text-color);
      }
      .checkbox-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(70px, 1fr));
        gap: 8px 16px;
      }
      @media (min-width: 400px) {
        .checkbox-grid {
          grid-template-columns: repeat(5, 1fr);
        }
      }
      .checkbox-label {
        display: flex;
        align-items: center;
        cursor: pointer;
        color: var(--primary-text-color);
      }
      .checkbox-label input[type="checkbox"] {
        margin-right: 8px;
        min-width: 20px;
        min-height: 20px;
      }
    `;
  }
}

customElements.define("boiler-card-editor", BoilerCardEditor);