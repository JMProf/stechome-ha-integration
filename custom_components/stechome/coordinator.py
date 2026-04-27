from datetime import date, datetime, timedelta
import logging
import async_timeout
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class StechomeDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api, id_piso):
        self.api = api
        self.id_piso = id_piso
        self.unsub_daily_refresh = None
        today = dt_util.now().date()
        self.import_start_date = today - timedelta(days=30)
        self.import_end_date = today
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            # Refresco de estado cada 6 h como red de seguridad.
            # La importación de estadísticas la gestiona el scheduler diario en __init__.py
            update_interval=timedelta(hours=6),
        )

    def _to_float(self, value):
        try:
            return float(str(value).replace(",", "."))
        except (TypeError, ValueError):
            return None

    def _build_daily_series(self, lecturas, key):
        series = []
        prev = None
        for lectura in lecturas:
            fecha = lectura.get("FECHA")
            current = self._to_float(lectura.get(key))
            if fecha is None or current is None:
                continue

            consumo = 0.0 if prev is None else max(current - prev, 0.0)
            series.append(
                {
                    "fecha": fecha,
                    "consumo": round(consumo, 3),
                    "lectura": round(current, 3),
                }
            )
            prev = current
        return series

    def set_import_start_date(self, value: date) -> None:
        self.import_start_date = value

    def set_import_end_date(self, value: date) -> None:
        self.import_end_date = value

    async def async_import_acs_selected_range(self) -> None:
        start = self.import_start_date
        end = self.import_end_date
        if end < start:
            raise UpdateFailed("La fecha fin no puede ser anterior a la fecha inicio")
        if (end - start).days + 1 > 90:
            raise UpdateFailed("El rango máximo permitido es de 90 días")
        await self.async_import_acs_range(start, end)

    async def async_import_acs_range(self, start: date, end: date) -> None:
        """Importa ACS para un rango inclusivo de fechas."""
        try:
            from homeassistant.helpers import entity_registry as er
            from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
            from homeassistant.components.recorder.statistics import async_import_statistics
        except ImportError as exc:
            raise UpdateFailed("El componente recorder no está disponible") from exc

        entity_reg = er.async_get(self.hass)
        entity_id = entity_reg.async_get_entity_id("sensor", DOMAIN, f"{self.id_piso}_acs_v2")
        if not entity_id:
            raise UpdateFailed("No se encontró la entidad ACS para importar histórico")

        res = await self.api.async_get_data_range(self.id_piso, start, end)
        if not res:
            raise UpdateFailed("Sin datos de Stechome para el rango solicitado")

        rows = res.get("response", [])
        if not isinstance(rows, list) or not rows:
            raise UpdateFailed("Respuesta vacía de Stechome para el rango solicitado")

        # Normalizamos por día para que una importación solapada pueda sobrescribir sin ruido.
        by_day = {}
        for row in rows:
            fecha = row.get("FECHA")
            if fecha:
                by_day[fecha] = row

        tz = dt_util.get_default_time_zone()
        stats = []
        prev_sum = None
        for fecha in sorted(by_day.keys()):
            row = by_day[fecha]
            try:
                # Stechome etiqueta cada lectura con el día siguiente al que corresponde
                # (off-by-one en la API). La lectura de FECHA=X refleja el acumulado
                # a finales del día X-1, por tanto le asignamos start = (X-1) 00:00:00
                # para que HA calcule correctamente el consumo del día X-1.
                day_start = (datetime.strptime(fecha, "%Y-%m-%d") - timedelta(days=1)).replace(tzinfo=tz)
            except ValueError:
                _LOGGER.warning("Fecha inválida en importación ACS: %s", fecha)
                continue

            lectura = self._to_float(row.get("LECTURA_ACS"))
            if lectura is None:
                continue

            state = round(lectura, 3)
            sum_value = state if prev_sum is None else round(max(state, prev_sum), 3)
            prev_sum = sum_value

            stats.append(StatisticData(start=day_start, state=state, sum=sum_value))

        if not stats:
            raise UpdateFailed("No se pudieron construir estadísticas ACS válidas")

        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name="Stechome ACS",
            source="recorder",
            statistic_id=entity_id,
            unit_of_measurement="m³",
        )

        async_import_statistics(self.hass, metadata, stats)
        _LOGGER.info(
            "Importación ACS completada: %d registros (%s a %s)",
            len(stats),
            start.isoformat(),
            end.isoformat(),
        )

    async def _async_update_data(self):
        """Actualiza el estado en vivo del sensor.

        Intenta obtener la lectura de ayer. Si la API aún no la tiene disponible,
        amplía la ventana hasta 7 días para garantizar que el sensor nunca quede
        en estado 'unknown' por datos aún no procesados por Stechome.
        """
        today = dt_util.now().date()
        yesterday = today - timedelta(days=1)

        # Intentamos primero solo ayer; si la respuesta viene vacía, ampliamos
        # la ventana a los últimos 7 días y cogemos la lectura más reciente.
        for days_window in (1, 7):
            start = yesterday - timedelta(days=days_window - 1)
            try:
                async with async_timeout.timeout(30):
                    res = await self.api.async_get_data_range(self.id_piso, start, yesterday)
            except Exception as err:
                raise UpdateFailed(f"Error comunicando con Stechome: {err}") from err

            if not res:
                raise UpdateFailed("Sin respuesta de Stechome (login/cookies/respuesta invalida)")

            lecturas = res.get("response", [])
            if isinstance(lecturas, list) and lecturas:
                lecturas_ordenadas = sorted(lecturas, key=lambda row: row.get("FECHA", ""))
                acs_series = self._build_daily_series(lecturas_ordenadas, "LECTURA_ACS")
                ultima = lecturas_ordenadas[-1]
                _LOGGER.debug(
                    "Estado ACS actualizado desde fecha %s (ventana %d dias)",
                    ultima.get("FECHA"),
                    days_window,
                )
                return {
                    "LECTURA_ACS": self._to_float(ultima.get("LECTURA_ACS")),
                    "series_acs": acs_series,
                    "consumo_mes_acs": round(sum(x["consumo"] for x in acs_series), 3),
                    "FECHA": ultima.get("FECHA"),
                    "EDIFICIO": ultima.get("EDIFICIO"),
                    "PISO": ultima.get("PISO"),
                }

            _LOGGER.debug("Sin lecturas en ventana de %d dias, ampliando...", days_window)

        raise UpdateFailed("Stechome no devolvió lecturas en los últimos 7 dias")