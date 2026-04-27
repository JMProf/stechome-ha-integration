import aiohttp
import json
import logging
from datetime import date, timedelta
from typing import Any

_LOGGER = logging.getLogger(__name__)


class StechomeAPI:
    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        self.base_url = "https://www.stechome.net/stechome-app/php"
        self.headers = {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-language": "es-ES,es;q=0.8",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://www.stechome.net",
            "x-requested-with": "XMLHttpRequest",
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            "referer": "https://www.stechome.net/stechome-app/"
        }

    async def _parse_json_from_response(
        self,
        response: aiohttp.ClientResponse,
        request_name: str,
    ) -> dict[str, Any] | None:
        """Parsea JSON incluso cuando el servidor responde con mimetype text/html."""
        text = await response.text()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            content_type = response.headers.get("Content-Type", "")
            _LOGGER.error(
                "%s devolvio contenido no JSON. HTTP=%s Content-Type=%s Body=%s",
                request_name,
                response.status,
                content_type,
                text[:500],
            )
            return None

    async def async_authenticate(self) -> str | None:
        """Valida login y obtiene el ID_PISO."""
        async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar()) as session:
            try:
                # Login inicial
                async with session.post(
                    f"{self.base_url}/stechome_login.php",
                    data={"user": self.username, "pass": self.password},
                    headers=self.headers
                ) as login_resp:
                    login_text = await login_resp.text()
                    if login_resp.status != 200:
                        _LOGGER.error(
                            "Login HTTP %s. Respuesta: %s",
                            login_resp.status,
                            login_text[:300],
                        )
                        return None

                # Obtener ID_PISO
                headers_mvc = self.headers.copy()
                headers_mvc["referer"] = "https://www.stechome.net/stechome-app/inicio-postpago.php"
                async with session.post(
                    f"{self.base_url}/mvc.php",
                    data={"usuario": self.username, "peticion": "inicio"},
                    headers=headers_mvc
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        _LOGGER.error("mvc.php(inicio) HTTP %s. Respuesta: %s", resp.status, text[:300])
                        return None

                    data = await self._parse_json_from_response(resp, "mvc.php(inicio)")
                    if not data:
                        return None
                    id_piso = data.get("response", {}).get("ID_PISO")
                    if not id_piso:
                        _LOGGER.error("ID_PISO no encontrado en respuesta: %s", str(data)[:500])
                        return None
                    return str(id_piso)
            except Exception as err:
                _LOGGER.error("Error en autenticación: %s", err)
                return None

    async def _fetch_lecturas(
        self,
        id_piso: str,
        fechaini_str: str,
        fechafin_str: str,
    ) -> dict[str, Any] | None:
        """Petición interna de lecturas por rango de fechas."""
        async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar()) as session:
            try:
                await session.post(
                    f"{self.base_url}/stechome_login.php",
                    data={"user": self.username, "pass": self.password},
                    headers=self.headers
                )
                headers_mvc = self.headers.copy()
                headers_mvc["referer"] = "https://www.stechome.net/stechome-app/historial-consumos-postpago.php"
                payload = {
                    "peticion": "lecturadiariapostpagofechas",
                    "id_piso": id_piso,
                    "fechaini": fechaini_str,
                    "fechafin": fechafin_str,
                }
                async with session.post(f"{self.base_url}/mvc.php", data=payload, headers=headers_mvc) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        _LOGGER.error("mvc.php(lecturas) HTTP %s. Respuesta: %s", resp.status, text[:300])
                        return None
                    return await self._parse_json_from_response(resp, "mvc.php(lecturas)")
            except Exception as err:
                _LOGGER.error("Error obteniendo datos: %s", err)
                return None

    async def async_get_data_range(
        self,
        id_piso: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any] | None:
        """Petición de lecturas diarias en un rango inclusivo de fechas."""
        if end_date < start_date:
            return None

        # La API usa fechafin exclusivo; sumamos un día para incluir end_date.
        end_exclusive = end_date + timedelta(days=1)
        return await self._fetch_lecturas(
            id_piso,
            start_date.strftime("%Y-%m-%d"),
            end_exclusive.strftime("%Y-%m-%d"),
        )