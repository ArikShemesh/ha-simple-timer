# config_flow.py
"""Config flow for Boiler Control."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN # Import switch domain
from .const import DOMAIN

class BoilerControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Boiler Control."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """
        Handle the initial user step to configure the integration instance.
        This step now asks for a name for the instance and the associated switch entity.
        """
        errors = {}

        if user_input is not None:
            # Create the config entry with the provided name and switch entity ID.
            return self.async_create_entry(
                title=user_input["name"],
                data={
                    "name": user_input["name"],
                    "switch_entity_id": user_input["switch_entity_id"]
                }
            )

        # Get all switch entities from Home Assistant to populate the dropdown
        all_switches = []
        if self.hass:
            # Use self.hass.states.async_entity_ids(SWITCH_DOMAIN) for a more robust way
            # to get all switch entity IDs.
            all_switches = sorted(self.hass.states.async_entity_ids(SWITCH_DOMAIN))
            
            if not all_switches:
                errors["base"] = "no_switches_found" # Custom error if no switches exist

        # Define the schema for the user input form
        data_schema = vol.Schema({
            vol.Required("name", default="Boiler Control"): str,
            vol.Required("switch_entity_id"): vol.In(all_switches)
        })

        # Show the form to the user
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"example_name": "Main Boiler"}
        )

    async def async_step_init(self, user_input=None):
        """Handle a flow initiated by the user."""
        return await self.async_step_user(user_input)

