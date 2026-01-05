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
    _newTimerButtonValue: { type: String },
  };

  hass?: HomeAssistant;
  _config: TimerCardConfig;
  _configFullyLoaded: boolean = false; // Track if we've received a complete config

  private _timerInstancesOptions: Array<{ value: string; label: string }> = [];
  private _tempSliderMaxValue: string | null = null;
  private _newTimerButtonValue: string = "";

  constructor() {
    super();
    this._config = {
      type: "custom:timer-card",
      timer_buttons: [...DEFAULT_TIMER_BUTTONS], // Use centralized default
      timer_instance_id: null,
      card_title: null
    };
  }

  private _getComputedCSSVariable(variableName: string, fallback: string = "#000000"): string {
    try {
      // Get the computed style from the document root or this element
      const computedStyle = getComputedStyle(document.documentElement);
      const value = computedStyle.getPropertyValue(variableName).trim();

      // If we got a value and it's a valid color, return it
      if (value && value !== '') {
        // Handle both hex colors and rgb/rgba
        return value;
      }
    } catch (e) {
      console.warn(`Failed to get CSS variable ${variableName}:`, e);
    }

    return fallback;
  }

  private _rgbToHex(rgb: string): string {
    // Handle rgb(r, g, b) or rgba(r, g, b, a)
    const match = rgb.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*[\d.]+)?\)/);
    if (match) {
      const r = parseInt(match[1]);
      const g = parseInt(match[2]);
      const b = parseInt(match[3]);
      return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
    }
    return rgb; // Return as-is if already hex or invalid
  }

  private _getThemeColorHex(variableName: string, fallback: string = "#000000"): string {
    const value = this._getComputedCSSVariable(variableName, fallback);

    // If it's already a hex color, return it
    if (value.startsWith('#')) {
      return value;
    }

    // If it's rgb/rgba, convert to hex
    if (value.startsWith('rgb')) {
      return this._rgbToHex(value);
    }

    return fallback;
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
    }

    return instances;
  }

  _getValidatedTimerButtons(configButtons: any): (number | string)[] {
    if (Array.isArray(configButtons)) {
      const validatedButtons: (number | string)[] = [];
      const seen = new Set<string>();

      configButtons.forEach(val => {
        const strVal = String(val).trim().toLowerCase();
        // Allow pure numbers (including decimals), numbers with unit suffix, optionally ending with *
        const match = strVal.match(/^(\d+(?:\.\d+)?)\s*(s|sec|seconds|m|min|minutes|h|hr|hours|d|day|days)?(\*)?$/);

        if (match) {
          const numVal = parseFloat(match[1]);
          const isFloat = match[1].includes('.');
          const unitStr = match[2] || 'min';
          const isHours = unitStr && (unitStr.startsWith('h') || ['h', 'hr', 'hours'].includes(unitStr));
          const isDays = unitStr && (unitStr.startsWith('d') || ['d', 'day', 'days'].includes(unitStr));

          // User Restriction: Fractional numbers only allowed for hours and days
          if (isFloat && !isHours && !isDays) {
            // Skip this value, it's invalid per rule
            return;
          }

          // User Restriction: Max 1 digit after decimal for hours and days
          if (isFloat && (isHours || isDays)) {
            const decimalPart = match[1].split('.')[1];
            if (decimalPart && decimalPart.length > 1) {
              return;
            }
          }

          // User Restriction: Limit to 9999 for all units
          if (numVal > 9999) {
            return;
          }

          // Normalize pure numbers to number type for existing logic compatibility
          if (!unitStr || ['m', 'min', 'minutes'].includes(unitStr)) {
            // Minutes case (pure number or "15min")
            if (numVal > 0 && numVal <= 9999) {
              const isDefault = strVal.endsWith('*');
              if (isDefault) {
                // Default timers are allowed even if minute value exists
                validatedButtons.push(val);
              } else {
                if (!seen.has(String(numVal))) {
                  validatedButtons.push(numVal);
                  seen.add(String(numVal));
                }
              }
            }
          } else {
            // Strings with other units (e.g. "30s", "1h")
            const isDefault = strVal.endsWith('*');
            if (isDefault) {
              // Default timers are allowed even if string value exists
              validatedButtons.push(val);
            } else {
              if (!seen.has(strVal)) {
                validatedButtons.push(val);
                seen.add(strVal);
              }
            }
          }
        }
      });

      // Sort: numbers first (sorted), then strings (alphabetical or just appended)
      // Actually standard logic sorts numbers. 
      const numbers = validatedButtons.filter(b => typeof b === 'number') as number[];
      const strings = validatedButtons.filter(b => typeof b === 'string') as string[];

      numbers.sort((a, b) => a - b);
      strings.sort();

      return [...numbers, ...strings];
    }

    if (configButtons === undefined || configButtons === null) {
      console.log(`TimerCardEditor: No timer_buttons in config, using empty array.`);
      return [];
    }

    console.warn(`TimerCardEditor: Invalid timer_buttons type (${typeof configButtons}):`, configButtons, `- using empty array`);
    return [];
  }

  async setConfig(cfg: TimerCardConfig): Promise<void> {
    const oldConfig = { ...this._config };

    const timerButtonsToSet = this._getValidatedTimerButtons(cfg.timer_buttons);

    const newConfigData: TimerCardConfig = {
      type: cfg.type || "custom:timer-card",
      timer_buttons: timerButtonsToSet,
      card_title: cfg.card_title || null,
      entity_state_icon: cfg.entity_state_icon || cfg.power_button_icon || null, // Migrate legacy value
      // power_button_icon: preserved implicitly via ...oldConfig but not actively set here to avoid confusion
      slider_max: cfg.slider_max || 120,
      slider_unit: cfg.slider_unit || 'min',
      reverse_mode: cfg.reverse_mode || false,
      hide_slider: cfg.hide_slider || false,
      show_daily_usage: cfg.show_daily_usage !== false,
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
      use_default_timer: cfg.use_default_timer || false
    };

    if (cfg.timer_instance_id) {
      newConfigData.timer_instance_id = cfg.timer_instance_id;
    } else {
      console.info(`TimerCardEditor: setConfig - no timer_instance_id in config, will remain unset`);
    }

    // Legacy support for old config properties
    if (cfg.entity) newConfigData.entity = cfg.entity;
    if (cfg.sensor_entity) newConfigData.sensor_entity = cfg.sensor_entity;

    this._config = newConfigData;
    this._configFullyLoaded = true;

    if (JSON.stringify(oldConfig) !== JSON.stringify(this._config)) {
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
        this._fetchTimerInstances();
      }
    }
  }

  async _fetchTimerInstances() {
    if (this.hass) {

      this._timerInstancesOptions = await this._getSimpleTimerInstances();

      if (!this._configFullyLoaded) {
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
        }
      } else {
        console.info(`TimerCardEditor: No timer_instance_id configured or no instances available. User must manually select.`);
      }

      this.requestUpdate();
    }
  }

  _handleNewTimerInput(event: InputEvent): void {
    const target = event.target as HTMLInputElement;
    this._newTimerButtonValue = target.value;
  }

  _addTimerButton(): void {
    const val = this._newTimerButtonValue.trim();
    if (!val) return;

    // Validate using the same regex as the card
    const match = val.match(/^(\d+(?:\.\d+)?)\s*(s|sec|seconds|m|min|minutes|h|hr|hours|d|day|days)?(\*)?$/i);

    if (!match) {
      alert("Invalid format! Use format like: 30, 30s, 10m, 1.5h, 1d. Add * for default timer (e.g. 30*)");
      return;
    }

    const numVal = parseFloat(match[1]);
    const isFloat = match[1].includes('.');
    const unitStr = (match[2] || 'min').toLowerCase();
    const isDefault = !!match[3];
    const isHours = unitStr.startsWith('h');
    const isDays = unitStr.startsWith('d');

    // User Restriction: Limit to 9999 for all units
    if (numVal > 9999) {
      alert("Value cannot exceed 9999");
      return;
    }

    // User Restriction: Fractional numbers only allowed for hours and days
    if (isFloat && !isHours && !isDays) {
      alert("Fractional values are only allowed for Hours (h) and Days (d)");
      return;
    }

    // User Restriction: Max 1 digit after decimal for hours and days
    if (isFloat && (isHours || isDays)) {
      const decimalPart = match[1].split('.')[1];
      if (decimalPart && decimalPart.length > 1) {
        alert("Maximum 1 decimal place allowed (e.g. 1.5)");
        return;
      }
    }

    // Internal calculation used by card to ignore zero values
    let minutesCheck = numVal;
    if (unitStr.startsWith('s')) minutesCheck = numVal / 60;
    else if (unitStr.startsWith('h')) minutesCheck = numVal * 60;
    else if (unitStr.startsWith('d')) minutesCheck = numVal * 1440;

    if (minutesCheck <= 0) {
      alert("Timer duration must be greater than 0");
      return;
    }

    let currentButtons = Array.isArray(this._config?.timer_buttons) ? [...this._config!.timer_buttons] : [];

    // Normalize logic: Store numbers as numbers (minutes), strings as strings (with units)
    // If user enters "30", treat as 30 min (number)
    // If user enters "30m", treat as "30m" (string)? OR normalize "30m" -> 30?
    // Current backend/frontend supports mixed. Let's keep it simple: if valid, add as string unless it's pure number

    let valueToAdd: string | number = val;
    // Optional: normalize pure numbers to number type for consistency with legacy, 
    // but the regex allows units. 
    // If no unit provided, match[2] is undefined.
    if (!match[2] && !isDefault) {
      valueToAdd = numVal;
    }

    // Check for duplicates
    if (currentButtons.includes(valueToAdd)) {
      this._newTimerButtonValue = ""; // Clear input anyway
      this.requestUpdate();
      return;
    }

    if (isDefault) {
      // Remove existing default timer if any
      currentButtons = currentButtons.filter(b => !String(b).includes('*'));
    }

    currentButtons.push(valueToAdd);

    // Sort logic
    const numbers = currentButtons.filter(b => typeof b === 'number') as number[];
    const strings = currentButtons.filter(b => typeof b === 'string') as string[];
    numbers.sort((a, b) => a - b);
    strings.sort((a, b) => {
      // Try to sort strings naturally? simplified sort for now
      return a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });
    });

    currentButtons = [...numbers, ...strings];

    this._updateConfig({ timer_buttons: currentButtons });
    this._newTimerButtonValue = "";
    this.requestUpdate();
  }

  _removeTimerButton(valueToRemove: string | number): void {
    let currentButtons = Array.isArray(this._config?.timer_buttons) ? [...this._config!.timer_buttons] : [];
    currentButtons = currentButtons.filter(b => b !== valueToRemove);
    this._updateConfig({ timer_buttons: currentButtons });
  }

  _updateConfig(updates: Partial<TimerCardConfig>) {
    const updatedConfig = { ...this._config, ...updates };
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
    const v = this._tempSliderMaxValue ?? String(this._config.slider_max ?? 120);

    if (timerInstances.length > 0) {
      instanceOptions.push(...timerInstances);
    } else {
      instanceOptions.push({ value: "none_found", label: "No Simple Timer Instances Found" });
    }

    // Get actual theme colors for defaults
    const defaultSliderThumbColor = "#2ab69c";
    const defaultSliderBackgroundColor = this._getThemeColorHex('--secondary-background-color', '#424242');
    const defaultTimerButtonFontColor = this._getThemeColorHex('--primary-text-color', '#ffffff');
    const defaultTimerButtonBackgroundColor = this._getThemeColorHex('--secondary-background-color', '#424242');
    const defaultPowerButtonBackgroundColor = this._getThemeColorHex('--secondary-background-color', '#424242');
    const defaultPowerButtonIconColor = this._getThemeColorHex('--primary-color', '#03a9f4');
    const defaultEntityStateButtonBackgroundColor = this._getThemeColorHex('--ha-card-background', this._getThemeColorHex('--card-background-color', '#1c1c1c'));
    const defaultEntityStateButtonIconColor = this._getThemeColorHex('--secondary-text-color', '#727272');
    const defaultEntityStateButtonBackgroundColorOn = this._getThemeColorHex('--ha-card-background', this._getThemeColorHex('--card-background-color', '#1c1c1c'));
    const defaultEntityStateButtonIconColorOn = this._getThemeColorHex('--primary-color', '#03a9f4');

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
        
        <div class="config-row">
          <ha-textfield
            .label=${"Entity State Icon (optional)"}
            .value=${this._config?.entity_state_icon || ""}
            .configValue=${"entity_state_icon"}
            @input=${this._valueChanged}
            .placeholder=${"e.g., mdi:power, mdi:lightbulb, or leave empty for no icon"}
            .helper=${"Enter any MDI icon name (mdi:icon-name) or leave empty to default to mdi:power"}
          >
            ${this._config?.entity_state_icon ? html`
              <ha-icon icon="${this._config.entity_state_icon}" slot="leadingIcon"></ha-icon>
            ` : ''}
          </ha-textfield>
        </div>


        
        <div class="config-row">
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
             <ha-textfield
              label="Slider maximum (1–9999)"
              type="number"
              min="1"
              max="9999"
              inputmode="numeric"
              value=${v}
              helper="Enter a number between 1 and 9999"
              validationMessage="Must be 1–9999"
              ?invalid=${this._isSliderMaxInvalid()}
              @input=${this._onSliderMaxInput}
              @change=${this._handleSliderMaxBlur}
              @blur=${this._handleSliderMaxBlur}
              @keydown=${(e: KeyboardEvent) => { if (e.key === 'Enter') this._handleSliderMaxBlur(e as any); }}
            ></ha-textfield>

            <ha-select
              .label=${"Slider Unit"}
              .value=${this._config?.slider_unit || "min"}
              .configValue=${"slider_unit"}
              @selected=${this._valueChanged}
              @closed=${(ev) => ev.stopPropagation()}
              fixedMenuPosition
              naturalMenuWidth
            >
              <mwc-list-item value="sec">Seconds (s)</mwc-list-item>
              <mwc-list-item value="min">Minutes (m)</mwc-list-item>
              <mwc-list-item value="hr">Hours (h)</mwc-list-item>
              <mwc-list-item value="day">Days (d)</mwc-list-item>
            </ha-select>
          </div>
        </div>

        <ha-expansion-panel outlined style="margin-top: 16px; margin-bottom: 16px;">
          <div slot="header" style="display: flex; align-items: center;">
            <ha-icon icon="mdi:palette-outline" style="margin-right: 8px;"></ha-icon>
            Appearance
          </div>
          <div class="content" style="padding: 12px; margin-top: 12px;">
            <div class="config-row">
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                <!-- Slider Thumb Color -->
                <div style="display: flex; gap: 8px; align-items: center;">
                  <input
                    type="color"
                    value=${this._config?.slider_thumb_color || defaultSliderThumbColor}
                    @input=${(ev: Event) => {
        const target = ev.target as HTMLInputElement;
        this._valueChanged({
          target: {
            configValue: "slider_thumb_color",
            value: target.value
          },
          stopPropagation: () => { }
        } as any);
      }}
                    style="width: 40px; height: 40px; border: none; border-radius: 4px; cursor: pointer; flex-shrink: 0;"
                  />
                  <ha-textfield
                    .label=${"Slider Thumb Color"}
                    .value=${this._config?.slider_thumb_color || ""}
                    .configValue=${"slider_thumb_color"}
                    @input=${this._valueChanged}
                    .placeholder=${"Theme default"}
                    .helper=${"Leave empty to use default (#2ab69c)"}
                    style="flex: 1; min-width: 0;"
                  ></ha-textfield>
                </div>
                
                <!-- Slider Background Color -->
                <div style="display: flex; gap: 8px; align-items: center;">
                  <input
                    type="color"
                    value=${this._config?.slider_background_color || defaultSliderBackgroundColor}
                    @input=${(ev: Event) => {
        const target = ev.target as HTMLInputElement;
        this._valueChanged({
          target: {
            configValue: "slider_background_color",
            value: target.value
          },
          stopPropagation: () => { }
        } as any);
      }}
                    style="width: 40px; height: 40px; border: none; border-radius: 4px; cursor: pointer; flex-shrink: 0;"
                  />
                  <ha-textfield
                    .label=${"Slider Background Color"}
                    .value=${this._config?.slider_background_color || ""}
                    .configValue=${"slider_background_color"}
                    @input=${this._valueChanged}
                    .placeholder=${"Theme default"}
                    .helper=${"Leave empty to use theme color"}
                    style="flex: 1; min-width: 0;"
                  ></ha-textfield>
                </div>
              </div>
            </div>
            
            <div class="config-row">
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                <!-- Timer Button Font Color -->
                <div style="display: flex; gap: 8px; align-items: center;">
                  <input
                    type="color"
                    value=${this._config?.timer_button_font_color || defaultTimerButtonFontColor}
                    @input=${(ev: Event) => {
        const target = ev.target as HTMLInputElement;
        this._valueChanged({
          target: {
            configValue: "timer_button_font_color",
            value: target.value
          },
          stopPropagation: () => { }
        } as any);
      }}
                    style="width: 40px; height: 40px; border: none; border-radius: 4px; cursor: pointer; flex-shrink: 0;"
                  />
                  <ha-textfield
                    .label=${"Timer Button Font Color"}
                    .value=${this._config?.timer_button_font_color || ""}
                    .configValue=${"timer_button_font_color"}
                    @input=${this._valueChanged}
                    .placeholder=${"Theme default"}
                    .helper=${"Leave empty to use theme color"}
                    style="flex: 1; min-width: 0;"
                  ></ha-textfield>
                </div>
                
                <!-- Timer Button Background Color -->
                <div style="display: flex; gap: 8px; align-items: center;">
                  <input
                    type="color"
                    value=${this._config?.timer_button_background_color || defaultTimerButtonBackgroundColor}
                    @input=${(ev: Event) => {
        const target = ev.target as HTMLInputElement;
        this._valueChanged({
          target: {
            configValue: "timer_button_background_color",
            value: target.value
          },
          stopPropagation: () => { }
        } as any);
      }}
                    style="width: 40px; height: 40px; border: none; border-radius: 4px; cursor: pointer; flex-shrink: 0;"
                  />
                  <ha-textfield
                    .label=${"Timer Button Background Color"}
                    .value=${this._config?.timer_button_background_color || ""}
                    .configValue=${"timer_button_background_color"}
                    @input=${this._valueChanged}
                    .placeholder=${"Theme default"}
                    .helper=${"Leave empty to use theme color"}
                    style="flex: 1; min-width: 0;"
                  ></ha-textfield>
                </div>
              </div>
            </div>
            
            <div class="config-row">
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                <!-- Timer Control Button Background Color -->
                <div style="display: flex; gap: 8px; align-items: center;">
                  <input
                    type="color"
                    value=${this._config?.power_button_background_color || defaultPowerButtonBackgroundColor}
                    @input=${(ev: Event) => {
        const target = ev.target as HTMLInputElement;
        this._valueChanged({
          target: {
            configValue: "power_button_background_color",
            value: target.value
          },
          stopPropagation: () => { }
        } as any);
      }}
                    style="width: 40px; height: 40px; border: none; border-radius: 4px; cursor: pointer; flex-shrink: 0;"
                  />
                  <ha-textfield
                    .label=${"Timer Control Button Background"}
                    .value=${this._config?.power_button_background_color || ""}
                    .configValue=${"power_button_background_color"}
                    @input=${this._valueChanged}
                    .placeholder=${"Theme default"}
                    .helper=${"Button next to slider"}
                    style="flex: 1; min-width: 0;"
                  ></ha-textfield>
                </div>
                
                <!-- Timer Control Button Icon Color -->
                <div style="display: flex; gap: 8px; align-items: center;">
                  <input
                    type="color"
                    value=${this._config?.power_button_icon_color || defaultPowerButtonIconColor}
                    @input=${(ev: Event) => {
        const target = ev.target as HTMLInputElement;
        this._valueChanged({
          target: {
            configValue: "power_button_icon_color",
            value: target.value
          },
          stopPropagation: () => { }
        } as any);
      }}
                    style="width: 40px; height: 40px; border: none; border-radius: 4px; cursor: pointer; flex-shrink: 0;"
                  />
                  <ha-textfield
                    .label=${"Timer Control Button Icon Color"}
                    .value=${this._config?.power_button_icon_color || ""}
                    .configValue=${"power_button_icon_color"}
                    @input=${this._valueChanged}
                    .placeholder=${"Theme default"}
                    .helper=${"Button next to slider"}
                    style="flex: 1; min-width: 0;"
                  ></ha-textfield>
                </div>
              </div>
            </div>
            
            <!-- NEW: Entity State Button Colors -->
            <div class="config-row">
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                <!-- Entity State Button Background Color -->
                <div style="display: flex; gap: 8px; align-items: center;">
                  <input
                    type="color"
                    value=${this._config?.entity_state_button_background_color || defaultEntityStateButtonBackgroundColor}
                    @input=${(ev: Event) => {
        const target = ev.target as HTMLInputElement;
        this._valueChanged({
          target: {
            configValue: "entity_state_button_background_color",
            value: target.value
          },
          stopPropagation: () => { }
        } as any);
      }}
                    style="width: 40px; height: 40px; border: none; border-radius: 4px; cursor: pointer; flex-shrink: 0;"
                  />
                  <ha-textfield
                    .label=${"State Icon Background (Off)"}
                    .value=${this._config?.entity_state_button_background_color || ""}
                    .configValue=${"entity_state_button_background_color"}
                    @input=${this._valueChanged}
                    .placeholder=${"Theme default (Transparent)"}
                    .helper=${"Leave empty to use theme color"}
                    style="flex: 1; min-width: 0;"
                  ></ha-textfield>
                </div>
                
                
                <!-- Entity State Button Icon Color -->
                <div style="display: flex; gap: 8px; align-items: center;">
                  <input
                    type="color"
                    value=${this._config?.entity_state_button_icon_color || defaultEntityStateButtonIconColor}
                    @input=${(ev: Event) => {
        const target = ev.target as HTMLInputElement;
        this._valueChanged({
          target: {
            configValue: "entity_state_button_icon_color",
            value: target.value
          },
          stopPropagation: () => { }
        } as any);
      }}
                    style="width: 40px; height: 40px; border: none; border-radius: 4px; cursor: pointer; flex-shrink: 0;"
                  />
                  <ha-textfield
                    .label=${"State Icon Color (Off)"}
                    .value=${this._config?.entity_state_button_icon_color || ""}
                    .configValue=${"entity_state_button_icon_color"}
                    @input=${this._valueChanged}
                    .placeholder=${"Theme default"}
                    .helper=${"Leave empty to use theme color"}
                    style="flex: 1; min-width: 0;"
                  ></ha-textfield>
                </div>

                <!-- Entity State Button Background Color (On) -->
                <div style="display: flex; gap: 8px; align-items: center;">
                  <input
                    type="color"
                    value=${this._config?.entity_state_button_background_color_on || defaultEntityStateButtonBackgroundColorOn}
                    @input=${(ev: Event) => {
        const target = ev.target as HTMLInputElement;
        this._valueChanged({
          target: {
            configValue: "entity_state_button_background_color_on",
            value: target.value
          },
          stopPropagation: () => { }
        } as any);
      }}
                    style="width: 40px; height: 40px; border: none; border-radius: 4px; cursor: pointer; flex-shrink: 0;"
                  />
                  <ha-textfield
                    .label=${"State Icon Background (On)"}
                    .value=${this._config?.entity_state_button_background_color_on || ""}
                    .configValue=${"entity_state_button_background_color_on"}
                    @input=${this._valueChanged}
                    .placeholder=${"Theme default"}
                    .helper=${"Leave empty to use theme color"}
                    style="flex: 1; min-width: 0;"
                  ></ha-textfield>
                </div>

                <!-- Entity State Button Icon Color (On) -->
                <div style="display: flex; gap: 8px; align-items: center;">
                  <input
                    type="color"
                    value=${this._config?.entity_state_button_icon_color_on || defaultEntityStateButtonIconColorOn}
                    @input=${(ev: Event) => {
        const target = ev.target as HTMLInputElement;
        this._valueChanged({
          target: {
            configValue: "entity_state_button_icon_color_on",
            value: target.value
          },
          stopPropagation: () => { }
        } as any);
      }}
                    style="width: 40px; height: 40px; border: none; border-radius: 4px; cursor: pointer; flex-shrink: 0;"
                  />
                  <ha-textfield
                    .label=${"State Icon Color (On)"}
                    .value=${this._config?.entity_state_button_icon_color_on || ""}
                    .configValue=${"entity_state_button_icon_color_on"}
                    @input=${this._valueChanged}
                    .placeholder=${"Theme default"}
                    .helper=${"Leave empty to use theme color"}
                    style="flex: 1; min-width: 0;"
                  ></ha-textfield>
                </div>
              </div>
            </div>
          </div>
        </ha-expansion-panel>
        
        <div class="config-row">
          <ha-formfield .label=${"Turn off entity on timer cancel"}>
            <ha-switch
              .checked=${this._config?.turn_off_on_cancel !== false}
              .configValue=${"turn_off_on_cancel"}
              @change=${this._valueChanged}
            ></ha-switch>
          </ha-formfield>
        </div>

        <div class="config-row">
          <ha-formfield .label=${this._config?.reverse_mode ? "Use Default Timer (Disabled in Reverse Mode)" : "Use Default Timer (auto-start when entity turns on)"}
                        title=${this._config?.reverse_mode ? "Default Timer cannot be used with Reverse Mode (Delayed Start)" : ""}>
            <ha-switch
              .checked=${(this._config?.use_default_timer || false) && !this._config?.reverse_mode}
              .disabled=${this._config?.reverse_mode || false}
              .configValue=${"use_default_timer"}
              @change=${this._valueChanged}
            ></ha-switch>
          </ha-formfield>
        </div>

        <div class="config-row">
          <ha-formfield .label=${"Reverse Mode (Delayed Start)"}>
            <ha-switch
              .checked=${this._config?.reverse_mode || false}
              .configValue=${"reverse_mode"}
              @change=${this._valueChanged}
            ></ha-switch>
          </ha-formfield>
        </div>
        
        <div class="config-row">
          <ha-formfield .label=${"Hide Timer Slider"}>
            <ha-switch
              .checked=${this._config?.hide_slider || false}
              .configValue=${"hide_slider"}
              @change=${this._valueChanged}
            ></ha-switch>
          </ha-formfield>
        </div>
        
        <div class="config-row">
          <ha-formfield .label=${"Show Daily Usage"}>
            <ha-switch
              .checked=${this._config?.show_daily_usage !== false}
              .configValue=${"show_daily_usage"}
              @change=${this._valueChanged}
            ></ha-switch>
          </ha-formfield>
        </div>
        
      </div>

        <div class="config-row">
            <div class="timer-chips-container">
             <label class="config-label">Timer Presets</label>
             <div class="chips-wrapper">
                ${(this._config?.timer_buttons || DEFAULT_TIMER_BUTTONS).map(btn => {
        const isDefault = String(btn).endsWith('*');
        const displayVal = String(btn).replace('*', '');
        const label = typeof btn === 'number' ? btn + 'm' : displayVal;
        const chipClass = isDefault ? 'timer-chip default-timer' : 'timer-chip';
        return html`
                    <div class="${chipClass}" style="${isDefault ? 'border: 1px solid var(--primary-color); background-color: rgba(var(--rgb-primary-color), 0.1);' : ''}">
                        <span>${label}${isDefault ? ' (Default)' : ''}</span>
                        <span class="remove-chip" @click=${() => this._removeTimerButton(btn)}>✕</span>
                    </div>
                `;
      })}
             </div>
            </div>
            
            <div class="add-timer-row">
               <ha-textfield
                  .label=${"Add Timer (e.g. 30s, 10m, 1h)"}
                  .value=${this._newTimerButtonValue}
                  @input=${this._handleNewTimerInput}
                  @keypress=${(e: KeyboardEvent) => { if (e.key === 'Enter') this._addTimerButton(); }}
                  style="flex: 1;"
               ></ha-textfield>
               <div class="add-btn" @click=${this._addTimerButton} role="button">ADD</div>
            </div>
            <div class="helper-text" style="font-size: 0.8em; color: var(--secondary-text-color); margin-top: 4px;">
                Supports seconds (s), minutes (m), hours (h), days (d). Example: 30s, 10, 1.5h, 1d. Add * for default timer (e.g. 30*)
            </div>
        </div>
          ${(!this._config?.timer_buttons?.length && this._config?.hide_slider) ? html`
            <p class="info-text">ℹ️ No timer presets logic and the Slider is also hidden. The card will not be able to set a duration.</p>
          ` : ''}
        </div>
      </div>
    `;
  }

  private _onSliderMaxInput(ev: Event) {
    const target = ev.currentTarget as HTMLInputElement;
    this._tempSliderMaxValue = target.value;     // do NOT clamp here
    this.requestUpdate();                        // makes ?invalid update live
  }

  private _isSliderMaxInvalid(): boolean {
    const raw = this._tempSliderMaxValue ?? String(this._config.slider_max ?? "");
    if (raw === "") return true;                 // empty = invalid while editing
    const n = Number(raw);
    if (!Number.isFinite(n)) return true;
    return !(n >= 1 && n <= 9999);               // enforce 1–9999 (no negatives)
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

    // Clone existing config to ensure we preserve all fields (including entity_state_icon)
    const updatedConfig: TimerCardConfig = { ...this._config };

    // Handle specific logic for certain fields
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
        updatedConfig.timer_instance_id = null; // or undef depending on needs, null seems safe
      }
    } else if (configValue === "show_daily_usage") {
      updatedConfig.show_daily_usage = value; // boolean
    } else if (configValue === "hide_slider") {
      updatedConfig.hide_slider = value; // boolean
    } else if (configValue === "reverse_mode") {
      updatedConfig.reverse_mode = value; // boolean
    } else if (configValue === "slider_unit") {
      updatedConfig.slider_unit = value;
    } else if (configValue === "turn_off_on_cancel") {
      updatedConfig.turn_off_on_cancel = value; // boolean
    } else if (configValue === "use_default_timer") {
      updatedConfig.use_default_timer = value; // boolean
    } else {
      // For text/color fields where empty string means delete/null
      if (value && value !== '') {
        (updatedConfig as any)[configValue] = value;
      } else {
        // If the field is one that should be null when empty
        if ([
          'entity_state_icon', 'power_button_icon',
          'slider_thumb_color', 'slider_background_color',
          'timer_button_font_color', 'timer_button_background_color',
          'power_button_background_color', 'power_button_icon_color',
          'entity_state_button_background_color', 'entity_state_button_icon_color',
          'entity_state_button_background_color_on', 'entity_state_button_icon_color_on'
        ].includes(configValue)) {
          (updatedConfig as any)[configValue] = null;
        } else {
          delete (updatedConfig as any)[configValue];
        }
      }
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

  private _handleSliderMaxBlur(ev: Event) {
    const target = ev.currentTarget as HTMLInputElement;
    const raw = (target.value ?? "").trim();
    const n = Number(raw);
    const isInvalid = !raw || !Number.isFinite(n) || n < 1 || n > 9999;

    const newMax = isInvalid ? 120 : Math.trunc(n);
    target.value = String(newMax);
    this._tempSliderMaxValue = null;

    // Clamp existing timer buttons to newMax
    let newButtons = [...(this._config.timer_buttons || [])];
    newButtons = newButtons.filter(val => {
      if (typeof val === 'number') {
        return val <= newMax;
      }
      return true; // Keep custom string buttons
    });

    const updated: TimerCardConfig = {
      ...this._config,
      slider_max: newMax,
      timer_buttons: newButtons
    };

    this._config = updated;

    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: updated }, bubbles: true, composed: true
    }));
    this.requestUpdate();
  }

  static get styles() {
    return editorCardStyles;
  }
}

customElements.define("timer-card-editor", TimerCardEditor);