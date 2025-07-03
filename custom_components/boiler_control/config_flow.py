# config_flow.py
"""Config flow for Boiler Control."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from .const import DOMAIN

class BoilerControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Boiler Control."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """
        Handle the initial user step.
        This integration is now "zero-config". It doesn't ask the user for any
        information, like a switch entity. It simply creates a single instance
        for the sensor. The switch is selected later in the Lovelace card.
        """
        # Abort if an instance of the integration is already configured.
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # Create the config entry directly with no data.
        # The title will be "Boiler Control" as seen in the Integrations page.
        return self.async_create_entry(
            title="Boiler Control",
            data={}
        )

    async def async_step_init(self, user_input=None):
        """Handle a flow initiated by the user."""
        return await self.async_step_user(user_input)
