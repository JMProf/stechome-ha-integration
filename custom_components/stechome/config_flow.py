import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN
from .api import StechomeAPI

class StechomeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flujo de configuración para Stechome."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Paso inicial de configuración por el usuario."""
        errors = {}

        if user_input is not None:
            api = StechomeAPI(user_input["username"], user_input["password"], self.hass)
            id_piso = await api.async_authenticate()

            if id_piso:
                return self.async_create_entry(
                    title=user_input["username"],
                    data={
                        "username": user_input["username"],
                        "password": user_input["password"],
                        "id_piso": id_piso
                    }
                )
            errors["base"] = "auth_error"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("username"): str,
                vol.Required("password"): str,
            }),
            errors=errors
        )