from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfVolume
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    sensors = [
        StechomeSensor(
            coordinator,
            config_entry,
            "LECTURA_ACS",
            "ACS",
            UnitOfVolume.CUBIC_METERS,
            SensorDeviceClass.WATER,
            "series_acs",
            "consumo_mes_acs",
        ),
    ]
    async_add_entities(sensors)


class StechomeSensor(CoordinatorEntity):
    def __init__(self, coordinator, config_entry, data_key, name_suffix, unit, device_class, series_key, total_key):
        super().__init__(coordinator)
        self.data_key = data_key
        self.series_key = series_key
        self.total_key = total_key
        self._attr_name = f"Stechome {name_suffix}"
        self._attr_unique_id = f"{coordinator.id_piso}_acs_v2"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        # total_increasing: HA almacena estadísticas y calcula deltas automáticamente
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.id_piso)},
            name=f"Stechome {config_entry.data.get('username')}",
            manufacturer="Stechome",
            model="Módulo de Contadores",
        )

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        val = self.coordinator.data.get(self.data_key)
        return float(val) if val is not None else None

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {}
        return {
            "fecha_lectura": self.coordinator.data.get("FECHA"),
            "edificio": self.coordinator.data.get("EDIFICIO"),
            "piso": self.coordinator.data.get("PISO"),
            "consumo_mes_actual": self.coordinator.data.get(self.total_key),
            "consumos_diarios_mes": self.coordinator.data.get(self.series_key),
        }