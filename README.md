# Stechome for Home Assistant

Integración personalizada para Home Assistant que conecta con la web de Stechome y crea un sensor de consumo acumulado para agua caliente sanitaria (ACS).

La integración:
- Hace login en Stechome con tus credenciales.
- Detecta automáticamente tu `ID_PISO`.
- Programa un refresco automático diario a la hora configurada.
- Publica una entidad ACS lista para estadísticas en Home Assistant.
- Permite importar histórico por rango de fechas desde los controles del propio dispositivo.

## Qué aporta esta integración

- Sensores de consumo acumulado (tipo `total_increasing`) para que Home Assistant calcule consumos diarios, semanales y mensuales.
- Actualización automática diaria configurable en opciones de la integración.
- Controles de dispositivo para importar histórico por fecha inicio/fin.

## Requisitos

- Home Assistant con `recorder` activo (necesario para estadísticas y panel de Energía).
- HACS instalado.
- Cuenta válida en Stechome.

## Instalación con HACS (repositorio personalizado)

1. Abre HACS en Home Assistant.
2. Entra en el menú de 3 puntos (arriba a la derecha) y elige `Custom repositories`.
3. En `Repository`, pega la URL de este repositorio:
	 - `https://github.com/jmprof/stechome-ha-integration`
4. En `Category`, selecciona `Integration`.
5. Pulsa `Add`.
6. Busca `Stechome` dentro de HACS e instálalo.
7. Reinicia Home Assistant.

## Configuración inicial

1. Ve a `Settings > Devices & Services`.
2. Pulsa `Add Integration`.
3. Busca `Stechome`.
4. Introduce tu email y contraseña de Stechome.
5. La integración valida el login y detecta el `ID_PISO` automáticamente.

Si todo va bien, se creará un dispositivo con sus sensores asociados.

## Refresco automático diario

Puedes configurar en las opciones de la integración:
- Hora diaria (`HH:MM`) usando la zona horaria de Home Assistant.
- Días hacia atrás (`1` a `7`) para refrescar desde ese punto hasta ayer.

Por defecto:
- Hora: `00:30`
- Días hacia atrás: `1` (solo ayer)

## Cómo funciona internamente

- La integración se refresca automáticamente una vez al día a la hora configurada.
- En cada refresco automático:
	- Inicia sesión en Stechome.
	- Consulta lecturas diarias del rango configurado (N días hasta ayer).
	- Reimporta el rango para mantener coherencia con posibles solapes.
	- Actualiza la lectura de la entidad ACS.
	- Actualiza la entidad en Home Assistant.

Esto permite que Home Assistant gestione estadísticas de largo plazo sin que tengas que recalcular nada manualmente.

## Sensores y estadísticas

Los sensores principales están pensados para estadísticas (`state_class: total_increasing`), lo que los hace aptos para análisis histórico y panel de Energía.

Además, se incluyen atributos con información del mes actual (serie diaria, fecha, edificio, etc.) para análisis avanzado en dashboards.

## Importar histórico por rango de fechas

Puedes importar histórico de ACS desde la propia ventana del dispositivo:

1. Abre el dispositivo de Stechome.
2. En la sección de controles, selecciona:
	- Fecha inicio de importación.
	- Fecha fin de importación.
3. Pulsa el botón de importar ACS.

Validaciones:
- El rango máximo permitido por importación es de 90 días.
- Los rangos solapados se normalizan por día y pueden reimportarse.

Recomendación:
- Importa en orden cronológico para mantener una serie consistente.

## Panel de Energía

Para sacar el máximo partido:

1. Ve a `Settings > Dashboards > Energy`.
2. En la sección de agua/energía térmica, selecciona los sensores de Stechome.
3. Deja que Home Assistant calcule los consumos por diferencia entre lecturas acumuladas.

Este enfoque es más robusto que guardar solo consumos diarios calculados externamente.

## Resolución de problemas

### Error de autenticación o `ID_PISO`

- Verifica usuario y contraseña.
- Reinicia Home Assistant tras actualizar archivos de la integración.
- Revisa logs para ver respuesta HTTP y contenido devuelto por Stechome.

### La importación desde controles no aparece o falla

- Asegúrate de haber reiniciado Home Assistant después de instalar/actualizar.
- Verifica que las fechas sean válidas y que el rango no supere 90 días.

### No veo datos en Energía

- Comprueba que `recorder` está activo.
- Espera a que se acumulen muestras (puede tardar un poco en reflejarse).
- Verifica que el sensor seleccionado es el de consumo acumulado correcto.

## Estado del proyecto

Proyecto en evolución. Se aceptan issues y sugerencias para mejorar:
- Estabilidad de login y parseo de respuestas.
- Mejora de importación histórica.
- Mejoras de UX en entidades y acciones.

## Contribuir

1. Haz un fork del repositorio.
2. Crea una rama para tu cambio.
3. Abre un Pull Request con contexto técnico y pasos de prueba.

---