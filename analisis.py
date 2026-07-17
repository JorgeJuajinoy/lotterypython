"""
analisis.py — Paso 2 del Loop
Procesa el historial de 300 sorteos aplicando 10 métodos estadísticos + IA.
Retorna un diccionario de análisis por juego para alimentar sugerencias.py
"""
import pandas as pd
import numpy as np
from collections import Counter
from itertools import combinations
from datetime import datetime
import json
import os
import config

# ─────────────────────────────────────────────
# Utilidades internas
# ─────────────────────────────────────────────
def _get_nums(df: pd.DataFrame, n_cols: int) -> np.ndarray:
    """Aplana las columnas N1..N<n> a un array 1D sin NaN."""
    cols = [f"N{i+1}" for i in range(n_cols)]
    flat = df[cols].values.flatten()
    return flat[~np.isnan(flat)].astype(int)


def _get_rows_as_lists(df: pd.DataFrame, n_cols: int) -> list[list[int]]:
    cols = [f"N{i+1}" for i in range(n_cols)]
    result = []
    for _, row in df[cols].iterrows():
        nums = [int(v) for v in row if not pd.isna(v)]
        if nums:
            result.append(nums)
    return result


# ─────────────────────────────────────────────
# Método 1 — Frecuencia Absoluta
# ─────────────────────────────────────────────
def frecuencia_absoluta(df: pd.DataFrame, n_cols: int, rango: int) -> dict:
    """Cuenta cuántas veces aparece cada número en el historial completo."""
    flat = _get_nums(df, n_cols)
    conteo = Counter(flat.tolist())
    freq = {n: conteo.get(n, 0) for n in range(1, rango + 1)}
    total = sum(freq.values())
    prob  = {n: v / total if total else 0 for n, v in freq.items()}
    return {"frecuencia": freq, "probabilidad": prob}


# ─────────────────────────────────────────────
# Método 2 — Frecuencia por Posición
# ─────────────────────────────────────────────
def frecuencia_por_posicion(df: pd.DataFrame, n_cols: int, rango: int) -> dict:
    """Para cada posición N1..N5 calcula la frecuencia de cada número."""
    pos_freq = {}
    for i in range(n_cols):
        col = f"N{i+1}"
        if col not in df.columns:
            continue
        vals = df[col].dropna().astype(int).tolist()
        c = Counter(vals)
        pos_freq[f"N{i+1}"] = {n: c.get(n, 0) for n in range(1, rango + 1)}
    return pos_freq


# ─────────────────────────────────────────────
# Método 3 — Análisis de Rachas (Gap)
# ─────────────────────────────────────────────
def analisis_rachas(df: pd.DataFrame, n_cols: int, rango: int) -> dict:
    """
    Para cada número calcula cuántos sorteos lleva sin aparecer (gap actual)
    y el gap promedio histórico.
    """
    rows = _get_rows_as_lists(df, n_cols)
    last_seen = {}   # número → índice de última aparición (0 = más reciente)
    gap_hist  = {n: [] for n in range(1, rango + 1)}

    for idx, nums in enumerate(rows):
        for n in range(1, rango + 1):
            if n in nums:
                if n in last_seen:
                    gap_hist[n].append(idx - last_seen[n])
                last_seen[n] = idx

    total_rows = len(rows)
    resultado = {}
    for n in range(1, rango + 1):
        gap_actual = total_rows - last_seen.get(n, total_rows)
        gap_prom   = np.mean(gap_hist[n]) if gap_hist[n] else total_rows
        resultado[n] = {"gap_actual": gap_actual, "gap_promedio": round(gap_prom, 2)}

    return resultado


# ─────────────────────────────────────────────
# Método 4 — Suma Estadística
# ─────────────────────────────────────────────
def suma_estadistica(df: pd.DataFrame, n_cols: int) -> dict:
    """Calcula la distribución de sumas y el rango P25-P75."""
    cols = [f"N{i+1}" for i in range(n_cols) if f"N{i+1}" in df.columns]
    sumas = df[cols].sum(axis=1)
    return {
        "media":  round(sumas.mean(), 2),
        "std":    round(sumas.std(), 2),
        "p25":    round(sumas.quantile(0.25), 2),
        "p75":    round(sumas.quantile(0.75), 2),
        "min":    int(sumas.min()),
        "max":    int(sumas.max()),
    }


# ─────────────────────────────────────────────
# Método 5 — Correlación de Pares
# ─────────────────────────────────────────────
def correlacion_pares(df: pd.DataFrame, n_cols: int, top_n: int = 20) -> list[tuple]:
    """Detecta los pares de números que más veces han salido juntos."""
    rows = _get_rows_as_lists(df, n_cols)
    par_count = Counter()
    for nums in rows:
        for par in combinations(sorted(nums), 2):
            par_count[par] += 1
    return par_count.most_common(top_n)


# ─────────────────────────────────────────────
# Método 6 — Análisis de Paridad
# ─────────────────────────────────────────────
def analisis_paridad(df: pd.DataFrame, n_cols: int) -> dict:
    """Distribución histórica de pares vs impares por sorteo."""
    rows = _get_rows_as_lists(df, n_cols)
    dist = Counter()
    for nums in rows:
        pares = sum(1 for n in nums if n % 2 == 0)
        dist[pares] += 1
    total = len(rows)
    prob = {k: round(v / total, 3) for k, v in dist.items()}
    mejor = max(dist, key=dist.get) if dist else 0
    return {"distribucion": dict(dist), "probabilidad": prob, "mejor_combo_pares": mejor}


# ─────────────────────────────────────────────
# Método 7 — Análisis por Décadas
# ─────────────────────────────────────────────
def analisis_decadas(df: pd.DataFrame, n_cols: int, rango: int) -> dict:
    """Frecuencia por rangos (1-10, 11-20, 21-30, 31-43)."""
    flat = _get_nums(df, n_cols).tolist()
    decadas = {}
    step = 10
    ini = 1
    while ini <= rango:
        fin = min(ini + step - 1, rango)
        key = f"{ini}-{fin}"
        decadas[key] = sum(1 for n in flat if ini <= n <= fin)
        ini = fin + 1
    total = sum(decadas.values())
    prob  = {k: round(v / total, 3) for k, v in decadas.items()}
    return {"conteo": decadas, "probabilidad": prob}


# ─────────────────────────────────────────────
# Método 8 — Tendencia Temporal (ventana deslizante)
# ─────────────────────────────────────────────
def tendencia_temporal(df: pd.DataFrame, n_cols: int, rango: int,
                        ventana: int = 30) -> dict:
    """
    Frecuencia en los últimos <ventana> sorteos vs. el historial completo.
    Identifica números 'en alza' y 'en baja'.
    """
    reciente = df.head(ventana)
    freq_total   = frecuencia_absoluta(df, n_cols, rango)["probabilidad"]
    freq_recient = frecuencia_absoluta(reciente, n_cols, rango)["probabilidad"]

    delta = {n: round(freq_recient.get(n, 0) - freq_total.get(n, 0), 4)
             for n in range(1, rango + 1)}

    en_alza  = sorted(delta, key=delta.get, reverse=True)[:10]
    en_baja  = sorted(delta, key=delta.get)[:10]
    return {"delta": delta, "en_alza": en_alza, "en_baja": en_baja}


# ─────────────────────────────────────────────
# Método 9 — Cadenas de Markov
# ─────────────────────────────────────────────
def cadenas_markov(df: pd.DataFrame, n_cols: int, rango: int) -> dict:
    """
    Probabilidad de transición: dado que salió número A en el sorteo anterior,
    ¿cuál es la probabilidad de que salga B en el siguiente?
    (simplificado: frecuencia conjunta en sorteos consecutivos)
    """
    rows = _get_rows_as_lists(df, n_cols)
    trans = {n: Counter() for n in range(1, rango + 1)}

    for i in range(len(rows) - 1):
        prev_set = set(rows[i + 1])  # sorteo anterior (df está desc)
        curr_set = set(rows[i])      # sorteo actual
        for p in prev_set:
            for c in curr_set:
                if 1 <= p <= rango and 1 <= c <= rango:
                    trans[p][c] += 1

    # Para cada número anterior → top 5 sucesores más probables
    sucesores = {}
    for n, cntr in trans.items():
        total = sum(cntr.values())
        if total:
            sucesores[n] = [(k, round(v / total, 3)) for k, v in cntr.most_common(5)]
        else:
            sucesores[n] = []

    return {"sucesores": sucesores}


# ─────────────────────────────────────────────
# Método 10 — IA Gemini (Calificación de Patrones)
# ─────────────────────────────────────────────
def calificar_patrones_ia(juego: str, analisis_result: dict, jugadas: list[dict]) -> dict | None:
    """
    Llama a Gemini para evaluar los patrones estadísticos detectados y las 
    jugadas generadas, retornando un breve texto de análisis y un score.
    """
    if not config.GOOGLE_API_KEY:
        return None
    try:
        from google import genai
        from google.genai import types
        import time

        client = genai.Client(api_key=config.GOOGLE_API_KEY)

        # Resumen de patrones
        M1 = analisis_result.get("M1_frecuencia", {}).get("frecuencia", {})
        top5 = [str(k) for k, _ in sorted(M1.items(), key=lambda x: -x[1])[:5]]
        
        M8 = analisis_result.get("M8_tendencia", {})
        alza = [str(x) for x in M8.get("en_alza", [])[:3]]

        j_nums = []
        for j in jugadas:
            j_nums.append("-".join(map(str, j.get("numeros", []))))

        prompt = (
            f"Juego:{juego}. Top históricos: {','.join(top5)}. En alza reciente: {','.join(alza)}. "
            f"Jugadas propuestas por alg: {' | '.join(j_nums)}. "
            f"Evalúa brevemente los patrones y califica de 0 a 100. "
            f'JSON: {{"analisis":"texto breve max 150 chars","score": 85}}'
        )

        time.sleep(2)
        resp = client.models.generate_content(
            model=config.IA_MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=150,
                temperature=0.7,
            ),
        )
        text = resp.text.replace("```json", "").replace("```", "").strip()
        
        import json
        data = json.loads(text)
        return {
            "analisis": data.get("analisis", "Análisis no disponible"),
            "score": data.get("score", 50)
        }
    except Exception as e:
        print(f"  [IA] Error calificando {juego}: {e}")
        return None


# ─────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────
def analizar(juego: str, df: pd.DataFrame) -> dict:
    """
    Ejecuta todos los métodos de análisis para un juego dado.
    Retorna un diccionario con los resultados de cada método.
    """
    cfg = config.JUEGOS.get(juego, {})
    n_cols = cfg.get("n_nums", 5)
    rango  = cfg.get("rango", 43)

    if df.empty:
        print(f"  [ANÁLISIS] Sin datos para {juego}")
        return {}

    print(f"  [ANÁLISIS] {juego} ({len(df)} sorteos)...")

    result = {
        "juego":    juego,
        "n_sorteos": len(df),
        "fecha_analisis": datetime.now().isoformat(),
        "M1_frecuencia":    frecuencia_absoluta(df, n_cols, rango),
        "M2_pos_freq":      frecuencia_por_posicion(df, n_cols, rango),
        "M3_rachas":        analisis_rachas(df, n_cols, rango),
        "M4_suma":          suma_estadistica(df, n_cols),
        "M5_pares":         correlacion_pares(df, n_cols),
        "M6_paridad":       analisis_paridad(df, n_cols),
        "M7_decadas":       analisis_decadas(df, n_cols, rango),
        "M8_tendencia":     tendencia_temporal(df, n_cols, rango),
        "M9_markov":        cadenas_markov(df, n_cols, rango),
    }

    return result


if __name__ == "__main__":
    import scraper
    datos = scraper.actualizar_datos(300)
    for juego in ["BALOTO", "MILOTO"]:
        df = datos.get(juego, pd.DataFrame())
        r  = analizar(juego, df)
        print(f"\n{juego} — Suma media: {r.get('M4_suma', {}).get('media')}")
        print(f"  Top calientes: {sorted(r.get('M1_frecuencia', {}).get('frecuencia', {}).items(), key=lambda x: -x[1])[:5]}")
