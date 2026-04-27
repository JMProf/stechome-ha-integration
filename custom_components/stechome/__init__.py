import logging
from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util
from .api import StechomeAPI
from .coordinator import StechomeDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_DAILY_REFRESH_TIME = "daily_refresh_time"
CONF_DAILY_REFRESH_DAYS_BACK = "daily_refresh_days_back"
DEFAULT_DAILY_REFRESH_TIME = "00:30"
DEFAULT_DAILY_REFRESH_DAYS_BACK = 1


def _get_daily_options(entry: ConfigEntry) -> tuple[int, int, int]:
    time_value = entry.options.get(CONF_DAILY_REFRESH_TIME, DEFAULT_DAILY_REFRESH_TIME)
    days_back = int(entry.options.get(CONF_DAILY_REFRESH_DAYS_BACK, DEFAULT_DAILY_REFRESH_DAYS_BACK))
    try:
        hh, mm = time_value.split(":")
        hour = int(hh)
        minute = int(mm)
    except (TypeError, ValueError):
        hour = 0
        minute = 30
    if not (0 <= hour <= 23):
        hour = 0
    if not (0 <= minute <= 59):
        minute = 30
    days_back = max(1, min(days_back, 7))
    return hour, minute, days_back


async def _async_daily_refresh(hass: HomeAssistant, coordinator: StechomeDataUpdateCoordinator, days_back: int) -> None:
    today = dt_util.now().date()
    end = today - timedelta(days=1)
    start = end - timedelta(days=days_back - 1)
    if end < start:
        _LOGGER.warning("Refresco diario omitido por rango inválido: %s a %s", start, end)
        return
    await coordinator.async_import_acs_range(start, end)
    await coordinator.async_request_refresh()


def _schedule_daily_refresh(hass: HomeAssistant, coordinator: StechomeDataUpdateCoordinator, hour: int, minute: int, days_back: int):
    def _on_time(_now):
        hass.async_create_task(_async_daily_refresh(hass, coordinator, days_back))

    return async_track_time_change(hass, _on_time, hour=hour, minute=minute, second=0)


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configura Stechome desde una entrada de configuración."""
    api = StechomeAPI(entry.data["username"], entry.data["password"], hass)
    coordinator = StechomeDataUpdateCoordinator(hass, api, entry.data["id_piso"])

    await coordinator.async_config_entry_first_refresh()

    entity_reg = er.async_get(hass)
    for legacy_unique_id in (
        f"{coordinator.id_piso}_LECTURA_ACS",
        f"{coordinator.id_piso}_LECTURA_CALEF",
    ):
        legacy_entity_id = entity_reg.async_get_entity_id("sensor", DOMAIN, legacy_unique_id)
        if legacy_entity_id:
            entity_reg.async_remove(legacy_entity_id)
            _LOGGER.info("Entidad heredada eliminada: %s", legacy_entity_id)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    hour, minute, days_back = _get_daily_options(entry)
    coordinator.unsub_daily_refresh = _schedule_daily_refresh(
        hass,
        coordinator,
        hour,
        minute,
        days_back,
    )
    _LOGGER.info(
        "Refresco diario programado a las %02d:%02d (%d dias hacia atras hasta ayer)",
        hour,
        minute,
        days_back,
    )

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "date", "button"])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Descarga una entrada de configuración."""
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator and getattr(coordinator, "unsub_daily_refresh", None):
        coordinator.unsub_daily_refresh()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor", "date", "button"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
