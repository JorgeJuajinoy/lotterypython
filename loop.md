# Lottery Loop — Documentación del Proyecto

## Configuración
- **API Key Gemini:** Se gestiona en `.env` (no hardcodeada)
  - Archivo: `D:\Proyectos_Programacion\Python\Lottery\.env`
  - Variable: `GOOGLE_API_KEY=tu_key_aqui`
- **Modelo IA:** gemini-2.0-flash
- **Scraper base:** `D:\Proyectos_Programacion\machineLearning\baloto`

---

## Objetivo
Obtener jugadas con >90% de acierto (criterio: ≥2 números acertados por jugada).

---

## Arquitectura del Loop

```
scraper.py → analisis.py → sugerencias.py → verificacion.py → informe.py
```

### Paso 1 — Scraping (`scraper.py`)
- Descarga los últimos 300 sorteos de **Baloto**, **Revancha** y **Miloto**
- Usa el scraper del proyecto legado: `machineLearning\baloto`
- Guarda en Excel:
  - `data/baloto_300.xlsx`
  - `data/miloto_300.xlsx`
- Solo re-scrapea en la iteración 1; las siguientes usan caché

### Paso 2 — Análisis (`analisis.py`)
Aplica 9 métodos estadísticos sobre los 300 sorteos descargados:

| Método | Descripción |
|--------|-------------|
| M1 | Frecuencia absoluta de cada número |
| M2 | Frecuencia por posición (N1..N5) |
| M3 | Análisis de rachas / gaps |
| M4 | Estadística de sumas (P25-P75) |
| M5 | Correlación de pares |
| M6 | Análisis de paridad (par/impar) |
| M7 | Análisis por décadas |
| M8 | Tendencia temporal (ventana 30 sorteos) |
| M9 | Cadenas de Markov |
| M10 | IA Gemini (requiere API key activa) |

### Paso 3 — Sugerencias (`sugerencias.py`)
- Combina los métodos con **pesos ponderados** (ajustables por el loop)
- Genera **máximo 2 jugadas** por juego
- Filtra por suma estadística y distribución par/impar histórica
- Guarda historial en `data/sugerencias_historico.xlsx`

### Paso 4 — Verificación con Backtest (`verificacion.py`)
**Modo backtest histórico** (activo por defecto):
- Simula 50 predicciones usando los 300 sorteos descargados
- Para cada sorteo reciente: entrena con datos anteriores → predice → compara con resultado real
- Calcula % de acierto real **sin esperar sorteos futuros**
- Resultados actuales:
  - BALOTO: ~10-12% | MILOTO: ~8% | Global: ~9-10%

**Modo verificación real** (automático cuando hay sorteos futuros):
- Compara sugerencias pasadas con resultados reales ya ocurridos

### Paso 5 — Ajuste de Pesos
- Si acierto < 90%, ajusta los pesos de cada método (±10%)
- Los pesos se persisten en `data/pesos_metodos.json`

### Paso 6 — Informe (`informe.py`)
- HTML: `reports/informe_loop.html` (abrir con doble clic)
- Excel: `reports/informe_loop.xlsx`
- Si el Excel está abierto, guarda con sufijo de hora automáticamente

---

## Estructura de Archivos

```
D:\Proyectos_Programacion\Python\Lottery\
│
├── .env                        ← API Key Gemini (editar aquí)
├── config.py                   ← Configuración central
├── scraper.py                  ← Paso 1: descarga 300 sorteos
├── analisis.py                 ← Paso 2: 9 métodos estadísticos
├── sugerencias.py              ← Paso 3: genera 2 jugadas por juego
├── verificacion.py             ← Paso 4: backtest + verificación real
├── informe.py                  ← Paso 6: HTML y Excel
├── loop.py                     ← Orquestador principal
├── requirements.txt
│
├── data/
│   ├── baloto_300.xlsx         ← 300 sorteos Baloto/Revancha
│   ├── miloto_300.xlsx         ← 300 sorteos Miloto
│   ├── sugerencias_historico.xlsx
│   └── pesos_metodos.json      ← Pesos ajustados por el loop
│
└── reports/
    ├── informe_loop.html       ← Abrir en navegador
    └── informe_loop.xlsx
```

---

## Cómo Ejecutar

### Instalación (solo primera vez)
```powershell
cd D:\Proyectos_Programacion\Python\Lottery
pip install -r requirements.txt
```

### Ejecución normal
```powershell
$env:PYTHONIOENCODING="utf-8"
python loop.py
```

### Ver resultados
```powershell
Start-Process "D:\Proyectos_Programacion\Python\Lottery\reports\informe_loop.html"
```

---

## Parámetros Configurables (`config.py`)

| Parámetro | Valor actual | Descripción |
|-----------|-------------|-------------|
| `OBJETIVO_ACIERTO` | 0.90 | Meta de % de acierto |
| `MAX_ITERACIONES` | 10 | Iteraciones máximas del loop |
| `N_SUGERENCIAS` | 2 | Jugadas por juego |
| `ACIERTO_MIN_NUMS` | 2 | Mínimo de números acertados para contar hit |

---

## Sugerencias Actuales (2026-07-14)

| Juego | Jugada 1 | Jugada 2 |
|-------|----------|----------|
| BALOTO | 11-17-24-26-38 + SB:3 | 10-14-22-28-29 + SB:15 |
| REVANCHA | 15-18-22-28-38 + SB:13 | 8-9-22-37-39 + SB:10 |
| MILOTO | 5-12-16-26-37 | 10-11-25-26-29 |

---

## Estado del Modelo

- **Backtest global:** ~9-10% (objetivo: 90%)
- **Pesos ajustados:** M1, M3, M8, M9 reducidos (rendimiento < 50%)
- **Próximo paso:** Más iteraciones para refinar pesos; activar IA Gemini con key válida
