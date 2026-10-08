# Seguimiento de vuelos baratos desde Colombia

Pequeña herramienta de línea de comandos que:

1. **Escanea** periódicamente los precios de vuelos desde ciudades colombianas
   (Bogotá, Medellín, Cali por defecto) hacia destinos nacionales e internacionales,
   para los próximos meses.
2. **Guarda** cada observación en una base SQLite local (`vuelos.db`), construyendo un
   histórico por ruta.
3. **Detecta chollos**: precios absurdamente bajos comparados con la mediana histórica de
   esa ruta, o por debajo de un tope absoluto que tú defines.
4. **Avisa** por consola o Telegram cuando aparece un chollo nuevo.

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env          # y rellena credenciales
```

## Fuentes de datos

| Proveedor | Coste | Cómo obtener credenciales | Notas |
|-----------|-------|---------------------------|-------|
| **Travelpayouts / Aviasales** (recomendado) | Gratis | Cuenta en [travelpayouts.com](https://www.travelpayouts.com) → Herramientas → API → token | 1 llamada = precios de todo un mes para una ruta. Son precios cacheados de búsquedas recientes, no en tiempo real, pero perfectos para detectar tendencias y chollos. |
| **Amadeus Self-Service** | Gratis con cuota mensual | [developers.amadeus.com](https://developers.amadeus.com) → crear app | El entorno `test` tiene datos limitados. En `production` da precios reales pero consume más llamadas (1 por fecha). |
| **mock** | – | Ninguna | Datos simulados para probar el flujo sin credenciales. |

Con `provider: auto` en `config.yaml` se usa el primero que tenga credenciales en `.env`;
si no hay ninguna, se usa `mock`.

## Uso

```bash
python main.py scan                 # descarga precios de todas las rutas
python main.py deals                # muestra los chollos del último escaneo
python main.py deals --kind nacional --top 20 --links
python main.py calendar BOG CTG     # precio por fecha para una ruta
python main.py history BOG MIA      # evolución del mínimo en el tiempo
python main.py watch --every 6      # escaneo cada 6 h con avisos de chollos nuevos
python main.py watch --once         # un ciclo (ideal para Programador de tareas / cron)
python main.py routes               # rutas configuradas
python main.py status               # estado de la base de datos
```

Prueba rápida sin credenciales:

```bash
python main.py scan --provider mock
python main.py deals
```

## Enlaces de compra

Cada chollo lleva enlaces directos a la búsqueda exacta (ruta, fecha, solo ida) en
Google Flights, Skyscanner, Kayak y Aviasales, más el enlace del proveedor cuando el
precio viene de Travelpayouts.

```bash
python main.py deals --links          # imprime las URL de cada chollo
python main.py report --open          # HTML con botones de compra, abre el navegador
python main.py report --kind nacional --top 30 --out nacionales.html
```

La tabla de `deals` también muestra la columna **Comprar** con enlaces clicables en
terminales compatibles (Windows Terminal, VS Code). El modo `watch` regenera el HTML
(`chollos-<db>.html`) cada vez que aparece un chollo nuevo y, si Telegram está activo,
incluye los enlaces en el aviso.

## Cómo decide qué es un chollo

Para cada ruta y fecha de salida toma el vuelo más barato del último escaneo y lo marca
como chollo si cumple **alguna** condición de `config.yaml`:

- `ratio`: precio ≤ `ratio` × mediana histórica de la ruta (ventana `lookback_days`).
  La mediana solo se usa si hay al menos `min_observations` observaciones, por eso los
  primeros escaneos solo detectarán chollos por tope absoluto.
- `absolute_caps`: precio ≤ tope fijo por tipo de ruta (nacional / internacional).

Cuantos más escaneos acumules, mejor será la mediana y más fiable la detección.

## Automatizar en Windows

Programador de tareas → Crear tarea básica → cada 6 horas → acción:

```
Programa: D:\GitHub\Seguimiento vuelos\.venv\Scripts\python.exe
Argumentos: main.py watch --once
Iniciar en: D:\GitHub\Seguimiento vuelos
```

Para avisos por Telegram: crea un bot con @BotFather, obtén tu `chat_id` (por ejemplo con
@userinfobot), rellena `.env` y pon `telegram: true` en `config.yaml`.

## Versión Ibagué

`config-ibague.yaml` rastrea solo salidas desde Ibagué (Perales, `IBE`) y guarda el
histórico en su propia base `vuelos-ibague.db`. Todos los comandos aceptan `--config`:

```bash
python main.py --config config-ibague.yaml scan
python main.py --config config-ibague.yaml deals
python main.py --config config-ibague.yaml calendar IBE BOG
python main.py --config config-ibague.yaml watch --once
```

Desde Ibagué solo hay directos regulares a Bogotá y Medellín; el resto de destinos
aparecerán con escala y el precio guardado es el del itinerario completo. Puedes tener
las dos versiones programadas a la vez (cada una con su `--config`).

## Personalizar rutas

Edita `origins` y `destinations` en `config.yaml` con códigos IATA. Cada origen se cruza
con todos los destinos (excepto consigo mismo).
