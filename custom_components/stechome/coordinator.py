from datetime import timedelta
import logging
import async_timeout
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class StechomeDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api, id_piso):
        self.api = api
        self.id_piso = id_piso
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=1),
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

    async def _async_update_data(self):
        try:
            async with async_timeout.timeout(30):
                res = await self.api.async_get_data(self.id_piso)
                if not res:
                    raise UpdateFailed("Sin datos de Stechome (login/cookies/respuesta invalida)")
                lecturas = res.get("response", [])
                if isinstance(lecturas, list) and len(lecturas) > 0:
                    lecturas_ordenadas = sorted(lecturas, key=lambda row: row.get("FECHA", ""))
                    acs_series = self._build_daily_series(lecturas_ordenadas, "LECTURA_ACS")
                    calef_series = self._build_daily_series(lecturas_ordenadas, "LECTURA_CALEF")
                    ultima = lecturas_ordenadas[-1]

                    return {
                        # Lecturas acumuladas: fuente principal para panel de Energía
                        "LECTURA_ACS": self._to_float(ultima.get("LECTURA_ACS")),
                        "LECTURA_CALEF": self._to_float(ultima.get("LECTURA_CALEF")),
                        # Serie diaria del mes (atributos de visualización)
                        "series_acs": acs_series,
                        "series_calef": calef_series,
                        "consumo_mes_acs": round(sum(x["consumo"] for x in acs_series), 3),
                        "consumo_mes_calef": round(sum(x["consumo"] for x in calef_series), 3),
                        "FECHA": ultima.get("FECHA"),
                        "EDIFICIO": ultima.get("EDIFICIO"),
                        "PISO": ultima.get("PISO"),
                    }
                raise UpdateFailed("Respuesta de datos vacía")
        except Exception as err:
            raise UpdateFailed(f"Error comunicando con Stechome: {err}")