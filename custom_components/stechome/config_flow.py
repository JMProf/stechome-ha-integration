import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_DAILY_REFRESH_TIME,
    CONF_DAILY_REFRESH_DAYS_BACK,
    DEFAULT_DAILY_REFRESH_TIME,
    DEFAULT_DAILY_REFRESH_DAYS_BACK,
)
from .api import StechomeAPI


class StechomeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flujo de configuración para Stechome."""
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Paso inicial de configuración por el usuario."""
        errors = {}

        if user_input is not None:
            api = StechomeAPI(user_input["username"], user_input["password"])
            id_piso = await api.async_authenticate()

            if id_piso:
                return self.async_create_entry(
                    title=user_input["username"],
                    data={
                        "username": user_input["username"],
                        "password": user_input["password"],
                        "id_piso": id_piso
                    },
                )
            errors["base"] = "auth_error"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry) -> "StechomeOptionsFlow":
        return StechomeOptionsFlow(config_entry)


class StechomeOptionsFlow(config_entries.OptionsFlow):
    """Opciones para refresco diario automático."""

    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        errors = {}

        if user_input is not None:
            time_value = user_input[CONF_DAILY_REFRESH_TIME]
            try:
                parts = time_value.split(":")
                if len(parts) != 2:
                    raise ValueError
                hh = int(parts[0])
                mm = int(parts[1])
                if not (0 <= hh <= 23 and 0 <= mm <= 59):
                    raise ValueError
            except (TypeError, ValueError):
                errors[CONF_DAILY_REFRESH_TIME] = "invalid_time"

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        options = self._config_entry.options
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_DAILY_REFRESH_TIME,
                    default=options.get(CONF_DAILY_REFRESH_TIME, DEFAULT_DAILY_REFRESH_TIME),
                ): str,
                vol.Required(
                    CONF_DAILY_REFRESH_DAYS_BACK,
                    default=options.get(CONF_DAILY_REFRESH_DAYS_BACK, DEFAULT_DAILY_REFRESH_DAYS_BACK),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=7)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema, errors=errors)