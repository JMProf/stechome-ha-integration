from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([StechomeImportACSButton(coordinator, config_entry)])


class StechomeImportACSButton(CoordinatorEntity, ButtonEntity):
    _attr_name = "Stechome Importar ACS"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.id_piso}_acs_import_button_v2"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.id_piso)},
            name=f"Stechome {config_entry.data.get('username')}",
            manufacturer="Stechome",
            model="Modulo de Contadores",
        )

    async def async_press(self) -> None:
        await self.coordinator.async_import_acs_selected_range()
        await self.coordinator.async_request_refresh()
