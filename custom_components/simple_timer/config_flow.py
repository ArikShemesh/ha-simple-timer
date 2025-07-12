# config_flow.py
"""Config flow for Simple Timer."""
import voluptuous as vol
import logging

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import selector
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class SimpleTimerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Simple Timer."""
    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._switch_entity_id = None

    async def async_step_user(self, user_input=None):
        """
        First step: Select the switch entity.
        """
        errors = {}
        
        _LOGGER.info(f"Simple Timer: Starting config flow step 'user'")

        if user_input is not None:
            try:
                # EntitySelector returns the entity_id directly as a string
                switch_entity_id = user_input.get("switch_entity_id")
                
                _LOGGER.debug(f"Simple Timer: config_flow: switch_entity_id = {switch_entity_id}")
                
                # Validate switch entity
                if not switch_entity_id:
                    errors["switch_entity_id"] = "Please select an entity"
                elif not isinstance(switch_entity_id, str):
                    errors["switch_entity_id"] = "Invalid entity format"
                else:
                    # Check if entity exists
                    entity_state = self.hass.states.get(switch_entity_id)
                    if entity_state is None:
                        errors["switch_entity_id"] = "Entity not found"
                    else:
                        # Store the selected entity and move to name step
                        self._switch_entity_id = switch_entity_id
                        return await self.async_step_name()
                        
            except Exception as e:
                _LOGGER.error(f"Simple Timer: config_flow: Exception in step_user: {e}")
                errors["base"] = "An error occurred. Please try again."

        # Check if we have any compatible entities
        compatible_entities_exist = False
        if self.hass:
            SWITCH_LIKE_DOMAINS = ["switch", "input_boolean", "light", "fan"]
            for domain in SWITCH_LIKE_DOMAINS:
                try:
                    domain_entities = self.hass.states.async_entity_ids(domain)
                    if domain_entities:
                        compatible_entities_exist = True
                        break
                except Exception as e:
                    _LOGGER.warning(f"Simple Timer: config_flow: Error checking domain {domain}: {e}")
            
            if not compatible_entities_exist:
                errors["base"] = "No controllable entities found"

        # Show entity selector
        data_schema = vol.Schema({
            vol.Required("switch_entity_id"): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["switch", "input_boolean", "light", "fan"]
                )
            ),
        })

        _LOGGER.info(f"Simple Timer: Showing form for step 'user'")
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={},
            last_step=False  # This tells HA there are more steps coming
        )

    async def async_step_name(self, user_input=None):
        """
        Second step: Set the name (auto-populated from entity).
        """
        errors = {}
        
        _LOGGER.info(f"Simple Timer: Starting config flow step 'name'")

        if user_input is not None:
            try:
                name = user_input.get("name", "").strip()
                
                # Validate name
                if not name:
                    errors["name"] = "Please enter a name"
                else:
                    # Create the config entry
                    _LOGGER.info(f"Simple Timer: config_flow: Creating entry with name={name}, switch_entity_id={self._switch_entity_id}")
                    return self.async_create_entry(
                        title=name,
                        data={
                            "name": name,
                            "switch_entity_id": self._switch_entity_id
                        }
                    )
                    
            except Exception as e:
                _LOGGER.error(f"Simple Timer: config_flow: Exception in step_name: {e}")
                errors["base"] = "An error occurred. Please try again."

        # Auto-generate name from the selected entity
        suggested_name = ""
        if self._switch_entity_id:
            entity_state = self.hass.states.get(self._switch_entity_id)
            if entity_state:
                # Try to get friendly name first, then fall back to entity_id
                friendly_name = entity_state.attributes.get("friendly_name")
                if friendly_name:
                    suggested_name = friendly_name
                else:
                    # Fall back to entity_id based name
                    suggested_name = self._switch_entity_id.split(".")[-1].replace("_", " ").title()

        _LOGGER.info(f"Simple Timer: Auto-generated name: '{suggested_name}' from entity: {self._switch_entity_id}")

        # Show name form with auto-populated value
        data_schema = vol.Schema({
            vol.Required("name", default=suggested_name): str,
        })

        _LOGGER.info(f"Simple Timer: Showing form for step 'name' with suggested_name='{suggested_name}'")
        return self.async_show_form(
            step_id="name",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "selected_entity": self._switch_entity_id,
                "entity_name": suggested_name
            }
        )

    async def async_step_init(self, user_input=None):
        """Handle a flow initiated by the user."""
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return SimpleTimerOptionsFlow(config_entry)


class SimpleTimerOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Simple Timer."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        # Don't set self.config_entry to avoid deprecation warning
        pass

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}

        # Force sync when options flow opens
        await self._force_name_sync_on_open()

        if user_input is not None:
            try:
                name = user_input.get("name", "").strip()
                switch_entity_id = user_input.get("switch_entity_id")
                
                # Validate inputs
                if not name:
                    errors["name"] = "Please enter a name"
                elif not switch_entity_id:
                    errors["switch_entity_id"] = "Please select an entity"
                else:
                    # Check if entity exists
                    entity_state = self.hass.states.get(switch_entity_id)
                    if entity_state is None:
                        errors["switch_entity_id"] = "Entity not found"
                    else:
                        # Update config entry
                        await self._update_config_entry(name, switch_entity_id)
                        return self.async_create_entry(title="", data={})
                        
            except Exception as e:
                _LOGGER.error(f"Simple Timer: options_flow: Exception: {e}")
                errors["base"] = "An error occurred. Please try again."

        # Get current values
        current_name = self.config_entry.data.get("name") or self.config_entry.title or "Timer"
        current_switch_entity = self.config_entry.data.get("switch_entity_id", "")

        # Validate current switch entity
        current_switch_exists = True
        if current_switch_entity:
            entity_state = self.hass.states.get(current_switch_entity)
            if entity_state is None:
                current_switch_exists = False
                errors["switch_entity_id"] = f"Current entity '{current_switch_entity}' not found. Please select a new one."

        # Show form
        data_schema = vol.Schema({
            vol.Required("name", default=current_name): str,
            vol.Required("switch_entity_id", default=current_switch_entity if current_switch_exists else ""): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["switch", "input_boolean", "light", "fan"]
                )
            ),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors
        )

    async def _force_name_sync_on_open(self):
        """Force name sync when options flow opens."""
        current_title = self.config_entry.title
        current_data_name = self.config_entry.data.get("name")
        
        _LOGGER.info(f"Simple Timer: Options flow opened - title: '{current_title}', data_name: '{current_data_name}'")
        
        # If they differ, sync them
        if current_title and current_data_name != current_title:
            _LOGGER.info(f"Simple Timer: FORCE SYNCING '{current_title}' to entry.data['name']")
            
            # Update entry data
            new_data = dict(self.config_entry.data)
            new_data["name"] = current_title
            
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data
            )

    async def _update_config_entry(self, name: str, switch_entity_id: str):
        """Update config entry and force immediate sensor sync."""
        new_data = {
            "name": name,
            "switch_entity_id": switch_entity_id
        }
        
        _LOGGER.info(f"Simple Timer: Updating entry {self.config_entry.entry_id} with name='{name}', switch='{switch_entity_id}'")
        
        # Update both data and title
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=new_data,
            title=name
        )
        
        # Force immediate sensor update
        await self._force_sensor_update()

    async def _force_sensor_update(self):
        """Force immediate sensor update with multiple methods."""
        try:
            if DOMAIN in self.hass.data and self.config_entry.entry_id in self.hass.data[DOMAIN]:
                sensor_data = self.hass.data[DOMAIN][self.config_entry.entry_id]
                if "sensor" in sensor_data and sensor_data["sensor"]:
                    sensor = sensor_data["sensor"]
                    
                    # Method 1: Update tracking variables
                    sensor._last_known_title = self.config_entry.title
                    sensor._last_known_data_name = self.config_entry.data.get("name")
                    
                    # Method 2: Force name change handler
                    await sensor._handle_name_change()
                    
                    # Method 3: Force state write
                    sensor.async_write_ha_state()
                    
                    # Method 4: Force entity registry update
                    from homeassistant.helpers import entity_registry as er
                    entity_registry = er.async_get(self.hass)
                    if entity_registry:
                        entity_registry.async_update_entity(
                            sensor.entity_id,
                            name=sensor.name
                        )
                    
                    _LOGGER.info(f"Simple Timer: FORCED complete sensor update - new name: '{sensor.name}'")
                else:
                    _LOGGER.warning(f"Simple Timer: Sensor not found in hass.data for entry {self.config_entry.entry_id}")
        except Exception as e:
            _LOGGER.error(f"Simple Timer: Failed to force sensor update: {e}")