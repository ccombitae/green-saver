# Módulo de Machine Learning — Predicción de Horas Solares Pico

## ¿Qué problema resuelve?

La calculadora anterior suponía que **un panel produce 75 kWh al mes en cualquier lugar de Colombia**.
Eso no es cierto: en La Guajira hay mucho más sol que en el Chocó, y en cada ciudad la radiación
cambia mes a mes.

Este módulo entrena un **modelo de regresión** que predice las **Horas Solares Pico (HSP)** de cada mes
para la ciudad del usuario. Con esas HSP la API calcula cuánta energía produce un panel allí y, con eso,
cuántos paneles necesita, la cobertura de cada mes, el ahorro en pesos y el CO₂ evitado.

| | |
|---|---|
| Tipo de problema | Regresión supervisada |
| Variable objetivo | `ALLSKY_SFC_SW_DWN`: irradiación global diaria (kWh/m²/día) = HSP |
| Variables de entrada | latitud, longitud, elevación, mes (codificado seno/coseno), nubosidad, temperatura, humedad, precipitación, viento |
| Fuente de datos | [NASA POWER](https://power.larc.nasa.gov), datos mensuales 2005–2024, 49 ciudades de Colombia |
| Modelos comparados | Línea base (promedio del mes), Regresión lineal, Random Forest, Gradient Boosting |
| Validación | Validación cruzada agrupada (`GroupKFold`) por zona geográfica de 1°×1° |
| Métricas | MAE, RMSE, R², MAPE |

**¿Por qué validación agrupada?** NASA entrega el dato solar en celdas de 1°×1° (~110 km), así que
ciudades cercanas (p. ej. Girardot y Melgar) comparten el mismo valor. Si una quedara en entrenamiento
y la otra en prueba, el modelo "haría trampa". Agrupando por celda, el modelo siempre se evalúa en zonas
que nunca vio.

## Cómo ejecutarlo (en tu PC, con internet)

Desde la raíz del repositorio:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (en Linux/Mac: source .venv/bin/activate)
pip install -r requirements-dev.txt

python ml/descargar_datos.py    # 1. Descarga (~2-3 min) -> ml/data/nasa_power_mensual.csv
python ml/eda.py                # 2. Análisis exploratorio -> ml/reports/figuras/01..05
python ml/entrenar.py           # 3. Entrena y evalúa       -> app/ml/artifacts/ + figuras 06..08
python -m pytest                # 4. Pruebas automáticas
```

Luego **hay que hacer commit** de `ml/data/`, `ml/reports/` y `app/ml/artifacts/`: el servidor usa esos
archivos y no entrena nada al arrancar.

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/ml/ciudades` | Catálogo de ciudades (Girardot primero) |
| POST | `/ml/estimar` | Dimensiona el sistema. Cuerpo: `{"consumo_mensual_kwh": 250, "ciudad_id": "girardot"}` (opcionales: `potencia_panel_w`, `rendimiento`, `tarifa_kwh_cop`) |
| GET | `/ml/modelo` | Algoritmo elegido, métricas de validación y fecha de entrenamiento |
| GET | `/ml/eda` | Datos agregados del análisis exploratorio para el dashboard |

Si el servidor no tiene el modelo, `/ml/estimar` no falla: usa el promedio histórico de la ciudad
(`fuente_hsp: "historico"`) o un valor nacional de 4.5 HSP (`fuente_hsp: "respaldo"`).

## Fórmula de dimensionamiento

```
Energía de un panel en el mes (kWh) = Potencia (kW) × HSP del mes × días del mes × PR
Paneles necesarios = techo( consumo mensual / energía promedio de un panel )
```

- Potencia por defecto: 550 W. PR (*performance ratio*, pérdidas del sistema): 0.80.
- Tarifa por defecto: 850 COP/kWh y factor de emisión de 0.126 kg CO₂/kWh. **Son valores de referencia:
  verifiquen la tarifa vigente del operador de red (recibo de luz) y el factor de emisión publicado por la UPME
  antes de citarlos en el documento.**

## Archivos

```
ml/
├── ciudades.csv          catálogo de 49 ciudades con coordenadas
├── descargar_datos.py    paso 1: descarga NASA POWER
├── eda.py                paso 2: análisis exploratorio + datos del dashboard
├── entrenar.py           paso 3: comparación de modelos, validación y artefactos
├── data/                 datos descargados
└── reports/              figuras y métricas para el documento
app/ml/
├── features.py           definición única de las variables de entrada
├── predictor.py          carga el modelo y predice las HSP
└── artifacts/            modelo entrenado, climatología, metadata, datos del dashboard
app/services/estimation_service.py   dimensionamiento del sistema
app/routes/ml.py                     endpoints /ml/*
tests/                               pruebas unitarias y de API (pytest)
```

Las pruebas usan **datos sintéticos** (`tests/datos_sinteticos.py`) para correr sin internet;
esos datos no se usan para el modelo real ni para reportar métricas.
