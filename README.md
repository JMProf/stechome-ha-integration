# Stechome for Home Assistant

Integración personalizada para Home Assistant que conecta con la web de Stechome y crea sensores de consumo para agua caliente sanitaria (ACS) y calefacción.

La integración:
- Hace login en Stechome con tus credenciales.
- Detecta automáticamente tu `ID_PISO`.
- Descarga lecturas del mes actual.
- Publica sensores listos para estadísticas en Home Assistant.
- Permite importar meses históricos para completar gráficas y panel de Energía.

## Qué aporta esta integración

- Sensores de consumo acumulado (tipo `total_increasing`) para que Home Assistant calcule consumos diarios, semanales y mensuales.
- Actualización automática periódica (no necesitas lanzar consultas manualmente para el día a día).
- Servicio para importar histórico mensual desde la API (`import_history`).

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

## Cómo funciona internamente

- La integración se actualiza automáticamente de forma periódica.
- En cada ciclo:
	- Inicia sesión en Stechome.
	- Consulta lecturas diarias por rango de fechas del mes actual.
	- Obtiene la última lectura acumulada para ACS y calefacción.
	- Actualiza sensores en Home Assistant.

Esto permite que Home Assistant gestione estadísticas de largo plazo sin que tengas que recalcular nada manualmente.

## Sensores y estadísticas

Los sensores principales están pensados para estadísticas (`state_class: total_increasing`), lo que los hace aptos para análisis histórico y panel de Energía.

Además, se incluyen atributos con información del mes actual (serie diaria, fecha, edificio, etc.) para análisis avanzado en dashboards.

## Importar histórico de meses anteriores

Puedes importar meses pasados (por ejemplo, marzo 2026) usando el servicio:

- `stechome.import_history`

Parámetros:
- `year`: año a importar (ejemplo: `2026`)
- `month`: mes a importar (`1` a `12`)

Recomendación importante:
- Importa en orden cronológico (del mes más antiguo al más reciente).

Ejemplo:

```yaml
service: stechome.import_history
data:
	year: 2026
	month: 3
```

Después de importar, Home Assistant incorporará esos datos en las estadísticas y podrás verlos en paneles y tarjetas históricas.

## Panel de Energía

Para sacar el máximo partido:

1. Ve a `Settings > Dashboards > Energy`.
2. En la sección de agua/energía térmica, selecciona los sensores de Stechome.
3. Deja que Home Assistant calcule los consumos por diferencia entre lecturas acumuladas.

Consejo:
- Este enfoque es más robusto que guardar solo consumos diarios calculados externamente.

## Buenas prácticas

- No compartas credenciales reales en el repositorio.
- Si cambias contraseña en Stechome, vuelve a configurar la integración si fuese necesario.
- Mantén Home Assistant y HACS actualizados.
- Revisa logs de Home Assistant si observas datos vacíos o cortes puntuales.

## Resolución de problemas

### Error de autenticación o `ID_PISO`

- Verifica usuario y contraseña.
- Reinicia Home Assistant tras actualizar archivos de la integración.
- Revisa logs para ver respuesta HTTP y contenido devuelto por Stechome.

### El servicio `import_history` no aparece o falla

- Asegúrate de haber reiniciado Home Assistant después de instalar/actualizar.
- Comprueba que el dominio del servicio es `stechome`.
- Verifica que envías `year` y `month` con valores válidos.

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