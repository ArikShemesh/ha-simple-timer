// src/global.d.ts   ✅ new version
export {};                       // keep the file a module

declare global {
  /** One state object inside hass.states */
  interface HassEntity {
    state: string;
    attributes: {
      entry_id?: string;
      switch_entity_id?: string;
      timer_state?: string;
      timer_duration?: number;
      timer_finishes_at?: string | number;
      watchdog_message?: string;
      friendly_name?: string;
      [key: string]: any;        // catch-all for un-listed keys
    };
    last_changed?: string;
    last_updated?: string;
  }

  /** The HA object Lovelace passes to every card */
  interface HomeAssistant {
    callService(
      domain: string,
      service: string,
      data?: unknown
    ): Promise<void>;
    states: Record<string, HassEntity>;
    // ADD THIS NEW PROPERTY:
    services: Record<string, Record<string, { description: string; fields: Record<string, any> }>>;
  }

  /** Card configuration */
  interface BoilerCardConfig {
    type: string;
    entity: string;
    sensor_entity?: string | null;
    timer_buttons?: number[];
    notification_entity?: string | null;
  }

  /** Let `window.customCards` compile without TS2339 */
  interface Window {
    customCards: unknown[];
  }
}