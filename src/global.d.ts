// global.d.ts

interface TimerCardConfig {
  type: string;
  timer_instance_id?: string | null;
  entity?: string | null;
  sensor_entity?: string | null;
  timer_buttons: number[];
  notification_entity?: string | null;
  card_title?: string | null; // NEW: Add this line
}

// Define the structure for a Home Assistant state object
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
    [key: string]: any; // Allow for other unknown attributes
  };
  last_changed: string;
  last_updated: string;
  context: {
    id: string;
    parent_id: string | null;
    user_id: string | null;
  };
}

// Define the structure for a Home Assistant service object
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
  // Correctly define states as an index signature
  states: {
    [entityId: string]: HAState;
  };
  // Correctly define services with specific domains and services
  services: {
    notify?: { [service: string]: HAService };
    switch?: { [service: string]: HAService };
    [domain: string]: { [service: string]: HAService } | undefined; // Allow other domains
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
  // Add async_entity_ids if your code uses it directly on hass.states
  // It's usually on hass.states.async_entity_ids
  // If config_flow.py uses hass.states.async_entity_ids directly, this is where to add it
  // async_entity_ids(domain?: string): string[];
}

// New Interfaces for config entries API response
interface HAConfigEntry {
  entry_id: string;
  title: string;
	domain: string;
  // Add other properties if you need them, e.g., domain, disabled_by
}

interface HAConfigEntriesByDomainResponse {
  entry_by_domain: {
    [domain: string]: HAConfigEntry[];
  };
}

interface Window {
  customCards: Array<{
    type: string;
    name: string;
    description: string;
  }>;
}