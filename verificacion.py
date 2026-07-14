"""
verificacion.py — Paso 4 del Loop

Dos modos de verificación:
  1. BACKTEST histórico: usa los 300 sorteos descargados para simular predicciones
     y medir su tasa de acierto de forma inmediata (sin esperar sorteos futuros).
  2. VERIFICACIÓN real: compara sugerencias pasadas con resultados reales cuando
     ya han ocurrido los sorteos.

El backtest permite que el loop ajuste pesos desde la primera ejecución.
"""
import pandas as pd
import numpy as np
import os
from datetime import datetime
import config


# ─────────────────────────────────────────────
# Utilidades
# ─────────────────────────────────────────────
def _parse_nums(val) -> list[int]:
    if isinstance(val, list):
        return [int(n) for n in val]
    if isinstance(val, str):
        try:
            import ast
            return [int(n) for n in ast.literal_eval(val)]
        except Exception:
            return []
    return []


def _aciertos_jugada(nums_sug: list[int], nums_real: list[int]) -> int:
    return len(set(nums_sug) & set(nums_real))


def cargar_sugerencias() -> pd.DataFrame:
    if not os.path.exists(config.SUGERENCIAS_FILE):
        return pd.DataFrame()
    return pd.read_excel(config.SUGERENCIAS_FILE)


def cargar_resultados(juego: str) -> pd.DataFrame:
    data_key = config.JUEGOS.get(juego, {}).get("data_key", juego)
    filepath = config.FILES.get(data_key, "")
    if not filepath or not os.path.exists(filepath):
        return pd.DataFrame()
    return pd.read_excel(filepath)


# ─────────────────────────────────────────────
# BACKTESTING HISTÓRICO
# ─────────────────────────────────────────────
def backtest_historico(datos: dict, analisis_todos: dict, pesos: dict,
                        ventana_test: int = 50) -> dict:
    """
    Simula predicciones usando los datos históricos descargados.

    Para cada juego:
      - Usa los sorteos [ventana_test+1 .. 300] como entrenamiento
      - Para cada uno de los últimos [ventana_test] sorteos:
          * Genera una jugada con los datos previos a ese sorteo
          * Compara con el resultado real de ese sorteo
      - Mide la tasa de acierto (>= ACIERTO_MIN_NUMS coincidencias)

    Esto permite obtener un % real de acierto histórico en la primera ejecución.
    """
    import analisis as an
    import sugerencias as sug

    detalle = []
    por_juego = {}

    for juego in ["BALOTO", "MILOTO"]:
        cfg = config.JUEGOS.get(juego, {})
        n_nums = cfg.get("n_nums", 5)
        data_key = cfg.get("data_key", juego)
        df = datos.get(data_key, pd.DataFrame())

        if df.empty or len(df) < ventana_test + 20:
            print(f"  [BACKTEST] {juego}: datos insuficientes ({len(df)} sorteos)")
            continue

        print(f"  [BACKTEST] {juego}: simulando {ventana_test} predicciones...")

        hits = 0
        total = 0
        aciertos_suma = 0

        # df está ordenado descendente (más reciente primero)
        # índices 0..ventana_test-1 = los más recientes (se usan como "resultado real")
        # índices ventana_test.. = historial de entrenamiento
        for i in range(min(ventana_test, len(df) - 20)):
            # El "resultado real" es el sorteo en posición i
            fila_real = df.iloc[i]
            nums_real = [
                int(fila_real[f"N{j+1}"])
                for j in range(n_nums)
                if pd.notna(fila_real.get(f"N{j+1}"))
            ]
            if len(nums_real) != n_nums:
                continue

            # El "historial de entrenamiento" son los sorteos posteriores a ese (i+1 en adelante)
            df_train = df.iloc[i + 1:].reset_index(drop=True)
            if len(df_train) < 10:
                continue

            # Analizar con datos de entrenamiento
            try:
                ar = an.analizar(juego, df_train)
                jugadas = sug.generar_jugadas(juego, df_train, ar, pesos, n_jugadas=2)
            except Exception as e:
                continue

            if not jugadas:
                continue

            # Comparar la mejor jugada generada contra el resultado real
            mejor = jugadas[0]["numeros"]
            aciertos = _aciertos_jugada(mejor, nums_real)
            es_hit = aciertos >= config.ACIERTO_MIN_NUMS

            if es_hit:
                hits += 1
            aciertos_suma += aciertos
            total += 1

            detalle.append({
                "juego": juego,
                "fecha": str(fila_real.get("Fecha", "")),
                "metodo": "BACKTEST",
                "sugerencia": mejor,
                "resultado": nums_real,
                "aciertos": aciertos,
                "es_hit": es_hit,
            })

        if total > 0:
            pct = hits / total
            por_juego[juego] = {
                "hits": hits,
                "total": total,
                "pct": round(pct, 3),
                "acierto_prom": round(aciertos_suma / total, 2),
            }
            print(f"    -> {hits}/{total} hits  ({pct*100:.1f}%)  | prom aciertos: {aciertos_suma/total:.2f}")

        # También evaluar REVANCHA con los mismos datos de BALOTO
        if juego == "BALOTO":
            por_juego["REVANCHA"] = por_juego.get("BALOTO", {})

    if not detalle:
        return {"global_pct": 0.0, "n_evaluadas": 0, "n_hits": 0,
                "detalle": [], "por_juego": {}, "por_metodo": {}}

    n_evaluadas = len(detalle)
    n_hits = sum(1 for d in detalle if d["es_hit"])
    global_pct = n_hits / n_evaluadas if n_evaluadas else 0.0

    return {
        "global_pct":  round(global_pct, 4),
        "n_evaluadas": n_evaluadas,
        "n_hits":      n_hits,
        "detalle":     detalle,
        "por_juego":   por_juego,
        "por_metodo":  {"BACKTEST": {"hits": n_hits, "total": n_evaluadas,
                                     "pct": round(global_pct, 3)}},
    }


# ─────────────────────────────────────────────
# VERIFICACIÓN REAL (sugerencias vs sorteos reales)
# ─────────────────────────────────────────────
def verificar(df_sug: pd.DataFrame = None) -> dict:
    """
    Compara sugerencias guardadas con resultados reales del mismo día.
    Solo aplica cuando ya ocurrieron los sorteos sugeridos.
    """
    if df_sug is None:
        df_sug = cargar_sugerencias()

    if df_sug.empty:
        return {"global_pct": 0.0, "n_evaluadas": 0, "detalle": [], "por_juego": {}, "por_metodo": {}}

    n_cols = {"BALOTO": 5, "REVANCHA": 5, "MILOTO": 5}
    detalle = []
    cache_res = {}

    for _, row in df_sug.iterrows():
        juego    = str(row.get("juego", "")).upper()
        fecha    = str(row.get("fecha", ""))
        metodo   = str(row.get("metodo", ""))
        nums_sug = _parse_nums(row.get("numeros", []))

        if not nums_sug or juego not in config.JUEGOS:
            continue

        if juego not in cache_res:
            cache_res[juego] = cargar_resultados(juego)
        df_res = cache_res[juego]

        if df_res.empty:
            continue

        nc = n_cols.get(juego, 5)

        if juego == "REVANCHA" and "Tipo" in df_res.columns:
            df_filtered = df_res[df_res["Tipo"].str.upper() == "REVANCHA"]
        elif juego == "BALOTO" and "Tipo" in df_res.columns:
            df_filtered = df_res[df_res["Tipo"].str.upper() == "BALOTO"]
        else:
            df_filtered = df_res

        match = df_filtered[df_filtered["Fecha"].astype(str).str.contains(fecha[:10])]
        if match.empty:
            continue

        nums_real_row = match.iloc[0]
        nums_real = [
            int(nums_real_row[f"N{i+1}"])
            for i in range(nc)
            if pd.notna(nums_real_row.get(f"N{i+1}"))
        ]

        aciertos = _aciertos_jugada(nums_sug, nums_real)
        es_hit   = aciertos >= config.ACIERTO_MIN_NUMS

        detalle.append({
            "juego":      juego,
            "fecha":      fecha,
            "metodo":     metodo,
            "sugerencia": nums_sug,
            "resultado":  nums_real,
            "aciertos":   aciertos,
            "es_hit":     es_hit,
        })

    if not detalle:
        return {"global_pct": 0.0, "n_evaluadas": 0, "detalle": [], "por_juego": {}, "por_metodo": {}}

    n_evaluadas = len(detalle)
    n_hits      = sum(1 for d in detalle if d["es_hit"])
    global_pct  = n_hits / n_evaluadas if n_evaluadas else 0.0

    por_juego = {}
    for d in detalle:
        j = d["juego"]
        if j not in por_juego:
            por_juego[j] = {"hits": 0, "total": 0, "aciertos_suma": 0}
        por_juego[j]["total"] += 1
        por_juego[j]["aciertos_suma"] += d["aciertos"]
        if d["es_hit"]:
            por_juego[j]["hits"] += 1
    for j in por_juego:
        por_juego[j]["pct"] = round(por_juego[j]["hits"] / por_juego[j]["total"], 3)
        por_juego[j]["acierto_prom"] = round(por_juego[j]["aciertos_suma"] / por_juego[j]["total"], 2)

    por_metodo = {}
    for d in detalle:
        m = d["metodo"]
        if m not in por_metodo:
            por_metodo[m] = {"hits": 0, "total": 0}
        por_metodo[m]["total"] += 1
        if d["es_hit"]:
            por_metodo[m]["hits"] += 1
    for m in por_metodo:
        por_metodo[m]["pct"] = round(por_metodo[m]["hits"] / por_metodo[m]["total"], 3)

    return {
        "global_pct":  round(global_pct, 4),
        "n_evaluadas": n_evaluadas,
        "n_hits":      n_hits,
        "detalle":     detalle,
        "por_juego":   por_juego,
        "por_metodo":  por_metodo,
    }


# ─────────────────────────────────────────────
# Ajuste de pesos basado en verificación
# ─────────────────────────────────────────────
def ajustar_pesos(verificacion_result: dict, pesos_actuales: dict) -> dict:
    """
    Si un método tiene buen rendimiento → aumenta su peso.
    Si tiene mal rendimiento → lo reduce.
    """
    por_metodo = verificacion_result.get("por_metodo", {})
    nuevos_pesos = pesos_actuales.copy()

    METHOD_MAP = {
        "LOOP-MULTI":  ["M1_freq", "M3_gap", "M8_tendencia", "M9_markov"],
        "LOOP-RELAX":  ["M1_freq", "M2_pos"],
        "IA-GEMINI":   ["M8_tendencia"],
        "BACKTEST":    ["M1_freq", "M3_gap", "M8_tendencia", "M9_markov"],
    }

    for metodo, data in por_metodo.items():
        pct  = data.get("pct", 0.5)
        keys = METHOD_MAP.get(metodo, [])
        for k in keys:
            if k in nuevos_pesos:
                if pct >= 0.9:
                    nuevos_pesos[k] = round(min(nuevos_pesos[k] * 1.1, 3.0), 3)
                elif pct < 0.5:
                    nuevos_pesos[k] = round(max(nuevos_pesos[k] * 0.9, 0.1), 3)

    return nuevos_pesos


if __name__ == "__main__":
    resultado = verificar()
    print(f"\n=== VERIFICACION REAL ===")
    print(f"Evaluadas: {resultado['n_evaluadas']}")
    print(f"Hits (>={config.ACIERTO_MIN_NUMS} aciertos): {resultado.get('n_hits', 0)}")
    print(f"% Global: {resultado['global_pct'] * 100:.1f}%")
