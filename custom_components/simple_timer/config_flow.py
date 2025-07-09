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