import logging
from datetime import datetime

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from .api import StechomeAPI
from .coordinator import StechomeDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Sensores que se importarán al histórico: (data_key_en_api, unique_id_suffix, unidad, nombre)
_IMPORT_SENSORS = [
    ("LECTURA_ACS",   "LECTURA_ACS",   "m³",  "Agua Caliente Sanitaria"),
    ("LECTURA_CALEF", "LECTURA_CALEF", "kWh", "Calefacción"),
]

_IMPORT_SCHEMA = vol.Schema(
    {
        vol.Required("year"):  vol.All(vol.Coerce(int), vol.Range(min=2020, max=2035)),
        vol.Required("month"): vol.All(vol.Coerce(int), vol.Range(min=1, max=12)),
    },
    extra=vol.ALLOW_EXTRA,  # HA añade entity_id/device_id cuando se usa target
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configura Stechome desde una entrada de configuración."""
    api = StechomeAPI(entry.data["username"], entry.data["password"], hass)
    coordinator = StechomeDataUpdateCoordinator(hass, api, entry.data["id_piso"])

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    # Registrar el servicio solo la primera vez (puede haber varias config entries)
    if not hass.services.has_service(DOMAIN, "import_history"):
        hass.services.async_register(
            DOMAIN, "import_history", _handle_import_history, schema=_IMPORT_SCHEMA
        )

    return True


async def _handle_import_history(call: ServiceCall) -> None:
    """Handler del servicio import_history."""
    hass = call.hass
    year  = call.data["year"]
    month = call.data["month"]

    coordinators = hass.data.get(DOMAIN, {})
    if not coordinators:
        _LOGGER.error("import_history: no hay ninguna integración Stechome configurada")
        return

    for coordinator in coordinators.values():
        await _import_month(hass, coordinator, year, month)


async def _import_month(hass: HomeAssistant, coordinator, year: int, month: int) -> None:
    """Obtiene lecturas de un mes y las inyecta en las estadísticas del recorder de HA."""
    try:
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
        from homeassistant.components.recorder.statistics import (
            async_import_statistics,
            get_last_statistics,
        )
    except ImportError:
        _LOGGER.error("import_history: el componente recorder no está disponible")
        return

    data = await coordinator.api.async_get_data_month(coordinator.id_piso, year, month)
    if not data:
        _LOGGER.error("import_history: sin respuesta de la API para %02d/%d", month, year)
        return

    lecturas = data.get("response", [])
    if not isinstance(lecturas, list) or not lecturas:
        _LOGGER.error("import_history: respuesta vacía para %02d/%d", month, year)
        return

    lecturas_sorted = sorted(lecturas, key=lambda r: r.get("FECHA", ""))
    entity_reg = er.async_get(hass)
    tz = dt_util.get_default_time_zone()

    for api_key, uid_suffix, unit, display_name in _IMPORT_SENSORS:
        unique_id = f"{coordinator.id_piso}_{uid_suffix}"
        entity_id = entity_reg.async_get_entity_id("sensor", DOMAIN, unique_id)
        if not entity_id:
            _LOGGER.warning(
                "import_history: entidad no encontrada para unique_id=%s. "
                "Asegúrate de que la integración esté cargada antes de importar.",
                unique_id,
            )
            continue

        # Obtener el último sum conocido antes del mes que vamos a importar
        import_start = datetime(year, month, 1, tzinfo=tz)
        try:
            last_stats_raw = await get_instance(hass).async_add_executor_job(
                get_last_statistics, hass, 1, entity_id, False, {"sum", "state"}
            )
        except Exception as exc:
            _LOGGER.error("import_history: error consultando estadísticas previas: %s", exc)
            last_stats_raw = {}

        last_sum = 0.0
        prev_lectura = None
        if last_stats_raw and entity_id in last_stats_raw:
            last = last_stats_raw[entity_id][0]
            last_sum = float(last.get("sum") or 0.0)
            prev_lectura = last.get("state")
            if prev_lectura is not None:
                prev_lectura = float(prev_lectura)

        # Construir objetos StatisticData con la lectura acumulada y el sum acumulado
        stats: list[StatisticData] = []
        for lectura in lecturas_sorted:
            fecha_str = lectura.get("FECHA")
            if not fecha_str:
                continue
            try:
                day_start = datetime.strptime(fecha_str, "%Y-%m-%d").replace(tzinfo=tz)
            except ValueError:
                _LOGGER.warning("import_history: fecha inválida ignorada: %s", fecha_str)
                continue

            raw = lectura.get(api_key)
            try:
                current = float(str(raw).replace(",", "."))
            except (TypeError, ValueError):
                continue

            if prev_lectura is None:
                # Primer punto: delta = 0, usamos como referencia
                prev_lectura = current

            delta = max(current - prev_lectura, 0.0)
            last_sum = round(last_sum + delta, 3)
            prev_lectura = current

            stats.append(StatisticData(
                start=day_start,
                state=round(current, 3),
                sum=last_sum,
            ))

        if not stats:
            _LOGGER.warning("import_history: no se generaron estadísticas para %s %02d/%d", entity_id, month, year)
            continue

        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name=f"Stechome {display_name}",
            source="recorder",
            statistic_id=entity_id,
            unit_of_measurement=unit,
        )

        async_import_statistics(hass, metadata, stats)
        _LOGGER.info(
            "import_history: importados %d registros para %s (%02d/%d)",
            len(stats), entity_id, month, year,
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Descarga una entrada de configuración."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    # Eliminar el servicio si ya no queda ninguna entrada activa
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, "import_history")
    return unload_ok
