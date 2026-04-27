import logging
from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.components import persistent_notification
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util
from .api import StechomeAPI
from .coordinator import StechomeDataUpdateCoordinator
from .const import (
    DOMAIN,
    CONF_DAILY_REFRESH_TIME,
    CONF_DAILY_REFRESH_DAYS_BACK,
    DEFAULT_DAILY_REFRESH_TIME,
    DEFAULT_DAILY_REFRESH_DAYS_BACK,
)

_LOGGER = logging.getLogger(__name__)


def _notification_id(entry: ConfigEntry) -> str:
    return f"{DOMAIN}_refresh_error_{entry.entry_id}"


async def _async_create_refresh_error_notification(
    hass: HomeAssistant,
    entry: ConfigEntry,
    error_text: str,
) -> None:
    persistent_notification.async_create(
        hass,
        (
            "Stechome no pudo completar el refresco diario.\\n\\n"
            f"Error: {error_text}\\n\\n"
            "La integracion seguira reintentando automaticamente."
        ),
        title="Stechome: error de refresco",
        notification_id=_notification_id(entry),
    )


async def _async_dismiss_refresh_error_notification(hass: HomeAssistant, entry: ConfigEntry) -> None:
    persistent_notification.async_dismiss(hass, _notification_id(entry))


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


async def _async_daily_refresh(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: StechomeDataUpdateCoordinator,
    days_back: int,
) -> None:
    today = dt_util.now().date()
    end = today - timedelta(days=1)
    start = end - timedelta(days=days_back - 1)
    if end < start:
        _LOGGER.warning("Refresco diario omitido por rango inválido: %s a %s", start, end)
        return
    _LOGGER.info("Iniciando refresco diario ACS: %s a %s", start, end)
    try:
        await coordinator.async_import_acs_range(start, end)
        _LOGGER.info("Refresco diario ACS completado correctamente")
        await _async_dismiss_refresh_error_notification(hass, entry)
    except Exception as exc:  # noqa: BLE001
        _LOGGER.error("Refresco diario Stechome fallido: %s", exc)
        await _async_create_refresh_error_notification(hass, entry, str(exc))


def _schedule_daily_refresh(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: StechomeDataUpdateCoordinator,
    hour: int,
    minute: int,
    days_back: int,
):
    @callback
    def _on_time(_now):
        hass.async_create_task(_async_daily_refresh(hass, entry, coordinator, days_back))

    return async_track_time_change(hass, _on_time, hour=hour, minute=minute, second=0)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reprograma el scheduler diario sin recargar la integración completa."""
    coordinator: StechomeDataUpdateCoordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator is None:
        return
    if coordinator.unsub_daily_refresh:
        coordinator.unsub_daily_refresh()
    hour, minute, days_back = _get_daily_options(entry)
    coordinator.unsub_daily_refresh = _schedule_daily_refresh(
        hass, entry, coordinator, hour, minute, days_back
    )
    _LOGGER.info(
        "Opciones actualizadas: refresco diario reprogramado a las %02d:%02d (%d dias hacia atras)",
        hour,
        minute,
        days_back,
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configura Stechome desde una entrada de configuración."""
    api = StechomeAPI(entry.data["username"], entry.data["password"])
    coordinator = StechomeDataUpdateCoordinator(hass, api, entry.data["id_piso"])

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    hour, minute, days_back = _get_daily_options(entry)
    coordinator.unsub_daily_refresh = _schedule_daily_refresh(
        hass,
        entry,
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
