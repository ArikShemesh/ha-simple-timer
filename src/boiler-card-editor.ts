/* boiler-card-editor.ts ─ GUI editor for Boiler Control Card
 * Bundler-friendly: no HA-internal imports, no CDN URLs.
 */
import { LitElement, html, css } from 'lit';

// Ensure HomeAssistant and BoilerCardConfig are recognized from global.d.ts

const DOMAIN = "boiler_control";

class BoilerCardEditor extends LitElement {
  static properties = {
    hass: { type: Object },
    _config: { type: Object },
  };

  hass?: HomeAssistant;
  _config: BoilerCardConfig;

  constructor() {
    super();
    this._config = {
      type: "custom:boiler-card",
      entity: "switch.none_selected",
      sensor_entity: null,
      timer_buttons: [15, 30, 60, 90, 120, 150],
      notification_entity: null,
    };
  }

  /*
   * Helper function to find ALL switch entities available in Home Assistant.
   * This is for the 'entity' (switch) selection in the card, which can be any switch.
   */
  _getAllSwitches(): string[] {
    if (!this.hass) {
      return [];
    }
    const switches: string[] = [];
    for (const entityId in this.hass.states) {
      if (entityId.startsWith("switch.")) {
        switches.push(entityId);
      }
    }
    return switches.sort();
  }

  /*
   * Helper function to find the boiler_control sensor entity created by our integration.
   * There should only be one instance of this integration now.
   */
  _getBoilerControlSensor(): string | null {
    if (!this.hass) {
      return null;
    }
    for (const entityId in this.hass.states) {
      const state = this.hass.states[entityId];
      // Check if it's a sensor AND its attributes contain 'entry_id' AND it's from our DOMAIN
      // The entry_id attribute is explicitly set by your sensor.py, making it a reliable identifier.
      if (entityId.startsWith("sensor.") && typeof state.attributes.entry_id === 'string' && state.attributes.entry_id.length > 0) {
        return entityId;
      }
    }
    console.warn("BoilerCardEditor: No Boiler Control sensor found by _getBoilerControlSensor. Make sure the boiler_control integration is installed and its sensor entity exists, and that it has an 'entry_id' attribute.");
    return null;
  }

  /*
   * Helper function to find all notification services available under the 'notify' domain.
   * These are targets like 'mobile_app_your_phone', 'telegram', etc.
   */
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
      if (domain.includes("telegram")) {
        const domainServices = this.hass.services[domain];
        for (const serviceName in domainServices) {
          if (serviceName.includes("send") || serviceName.includes("message")) {
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
    console.log("FINAL Notification Service Targets:", targets);
    return targets;
  }

  /*
   * When the editor opens, update config based on provided cfg and auto-select entity.
   */
  setConfig(cfg: BoilerCardConfig): void {
    const allSwitches = this._getAllSwitches();
    const boilerControlSensor = this._getBoilerControlSensor();
    const oldConfig = { ...this._config };

    const entityToSet = cfg.entity || (allSwitches.length > 0 ? allSwitches[0] : "switch.none_selected");
    const sensorEntityToSet = cfg.sensor_entity || boilerControlSensor || null;

    const timerButtonsToSet = Array.isArray(cfg.timer_buttons)
      ? [...cfg.timer_buttons]
      : [15, 30, 45, 60, 90, 120, 150];

    const newConfigData: BoilerCardConfig = {
      type: cfg.type || "custom:boiler-card",
      entity: entityToSet,
      sensor_entity: sensorEntityToSet,
      timer_buttons: timerButtonsToSet.sort((a, b) => a - b),
      notification_entity: cfg.notification_entity || null,
    };

    this._config = null!;
    this.requestUpdate();

    setTimeout(() => {
        this._config = newConfigData;
        if (JSON.stringify(oldConfig) !== JSON.stringify(this._config)) {
            this.dispatchEvent(
                new CustomEvent("config-changed", { detail: { config: this._config } })
            );
        }
        this.requestUpdate();
    }, 0);
  }

  /*
   * Schema for the entity selection
   */
  get _schema(): any[] {
    const allSwitches = this._getAllSwitches();
    const notificationServiceTargets = this._getNotificationServiceTargets();

    const switchOptions = allSwitches.map(entityId => ({
      value: entityId,
      label: this.hass?.states[entityId]?.attributes.friendly_name || entityId,
    }));

    const boilerControlSensor = this._getBoilerControlSensor();
    const sensorOptions = boilerControlSensor ? [{
        value: boilerControlSensor,
        label: this.hass?.states[boilerControlSensor]?.attributes.friendly_name || boilerControlSensor,
    }] : [{value: "sensor.none_selected", label: "No Boiler Control Sensor Found"}];

    const notificationOptions = [{ value: "none_selected", label: "None" }];
    notificationServiceTargets.forEach(target => notificationOptions.push(target));

    return [
      {
        name: "entity",
        label: "Boiler Switch Entity (to control)",
        selector: {
          select: {
            options: switchOptions,
            custom_value: true,
          },
        },
      },
      {
        name: "sensor_entity",
        label: "Boiler Control Sensor (Daily Runtime)",
        selector: {
          select: {
            options: sensorOptions,
            custom_value: false,
          },
        },
      },
      {
        name: "notification_entity",
        label: "Notification Service Target",
        selector: {
          select: {
            options: notificationOptions,
            custom_value: false,
          },
        },
      },
    ];
  }

  // All possible timer options for checkboxes
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

    this._config = {
      ...this._config!,
      timer_buttons: currentButtons,
    };
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
    const newConfigFromForm = ev.detail.value as BoilerCardConfig;

    if (!this._config) {
      console.warn("BoilerCardEditor: _config is null in _valueChanged, deferring update.");
      return;
    }

    const updatedConfig: BoilerCardConfig = {
        ...this._config,
        entity: newConfigFromForm.entity,
        sensor_entity: newConfigFromForm.sensor_entity,
        notification_entity: newConfigFromForm.notification_entity === "none_selected" ? null : newConfigFromForm.notification_entity,
        type: newConfigFromForm.type || (this._config.type || "custom:boiler-card"),
        timer_buttons: this._config.timer_buttons
    };

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