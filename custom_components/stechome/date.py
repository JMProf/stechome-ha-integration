from __future__ import annotations

from datetime import date
from homeassistant.components.date import DateEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            StechomeImportStartDateEntity(coordinator, config_entry),
            StechomeImportEndDateEntity(coordinator, config_entry),
        ]
    )


class _StechomeBaseDateEntity(CoordinatorEntity, DateEntity):
    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.id_piso)},
            name=f"Stechome {config_entry.data.get('username')}",
            manufacturer="Stechome",
            model="Modulo de Contadores",
        )


class StechomeImportStartDateEntity(_StechomeBaseDateEntity):
    _attr_name = "Stechome Inicio importacion ACS"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{coordinator.id_piso}_acs_import_start_v2"

    @property
    def native_value(self) -> date | None:
        return self.coordinator.import_start_date

    async def async_set_value(self, value: date) -> None:
        self.coordinator.set_import_start_date(value)
        self.async_write_ha_state()


class StechomeImportEndDateEntity(_StechomeBaseDateEntity):
    _attr_name = "Stechome Fin importacion ACS"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{coordinator.id_piso}_acs_import_end_v2"

    @property
    def native_value(self) -> date | None:
        return self.coordinator.import_end_date

    async def async_set_value(self, value: date) -> None:
        self.coordinator.set_import_end_date(value)
        self.async_write_ha_state()
