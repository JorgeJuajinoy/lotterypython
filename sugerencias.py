"""
sugerencias.py — Paso 3 del Loop
Combina los 10 métodos de análisis con pesos ponderados para generar
máximo 2 jugadas por juego. Exporta a HTML y Excel.
"""
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import config
import analisis as an

# ─────────────────────────────────────────────
# Pesos por defecto de cada método
# ─────────────────────────────────────────────
PESOS_DEFAULT = {
    "M1_freq":      1.2,   # Frecuencia absoluta
    "M2_pos":       0.8,   # Frecuencia por posición
    "M3_gap":       1.0,   # Rachas (números con gap alto = "vencidos")
    "M5_pares":     0.9,   # Pares correlacionados
    "M6_paridad":   0.5,   # Paridad (par/impar)
    "M7_decadas":   0.6,   # Décadas
    "M8_tendencia": 1.3,   # Tendencia reciente (ventana 30)
    "M9_markov":    1.1,   # Cadenas de Markov
}


def cargar_pesos() -> dict:
    """Carga pesos desde archivo (ajustados por el loop iterativo)."""
    if os.path.exists(config.PESOS_FILE):
        try:
            with open(config.PESOS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return PESOS_DEFAULT.copy()


def guardar_pesos(pesos: dict):
    with open(config.PESOS_FILE, "w") as f:
        json.dump(pesos, f, indent=2)


# ─────────────────────────────────────────────
# Construcción del Score por número
# ─────────────────────────────────────────────
def _score_numeros(analisis_result: dict, pesos: dict, rango: int) -> dict[int, float]:
    """
    Combina todos los métodos en un score ponderado por número.
    Retorna {número: score_total}.
    """
    scores = {n: 0.0 for n in range(1, rango + 1)}

    # M1 — Frecuencia absoluta normalizada
    freq = analisis_result.get("M1_frecuencia", {}).get("probabilidad", {})
    if freq:
        max_f = max(freq.values()) or 1
        for n in range(1, rango + 1):
            scores[n] += pesos.get("M1_freq", 1.0) * (freq.get(n, 0) / max_f)

    # M2 — Frecuencia por posición (promedio de todas las posiciones)
    pos_freq = analisis_result.get("M2_pos_freq", {})
    if pos_freq:
        n_pos = len(pos_freq)
        for pos, pf in pos_freq.items():
            max_p = max(pf.values()) or 1
            for n in range(1, rango + 1):
                scores[n] += pesos.get("M2_pos", 0.8) * (pf.get(n, 0) / max_p) / n_pos

    # M3 — Rachas: número "vencido" (gap_actual > gap_promedio) → bonus
    rachas = analisis_result.get("M3_rachas", {})
    if rachas:
        for n in range(1, rango + 1):
            r = rachas.get(n, {})
            gap_a = r.get("gap_actual", 0)
            gap_p = r.get("gap_promedio", 1) or 1
            # Cuanto más "vencido" está el número, mayor el bonus
            ratio = min(gap_a / gap_p, 3.0)  # cap en 3x
            scores[n] += pesos.get("M3_gap", 1.0) * (ratio / 3.0)

    # M5 — Pares correlacionados: los números que forman pares top reciben bonus
    pares = analisis_result.get("M5_pares", [])
    if pares:
        max_par = pares[0][1] if pares else 1
        par_score = {n: 0.0 for n in range(1, rango + 1)}
        for (a, b), cnt in pares[:20]:
            bonus = (cnt / max_par) * 0.5
            par_score[a] += bonus
            par_score[b] += bonus
        max_ps = max(par_score.values()) or 1
        for n in range(1, rango + 1):
            scores[n] += pesos.get("M5_pares", 0.9) * (par_score[n] / max_ps)

    # M8 — Tendencia reciente: números en alza reciben bonus
    tendencia = analisis_result.get("M8_tendencia", {})
    delta = tendencia.get("delta", {})
    if delta:
        max_d = max(abs(v) for v in delta.values()) or 1
        for n in range(1, rango + 1):
            d = delta.get(n, 0)
            # Positivo = en alza, negativo = en baja
            scores[n] += pesos.get("M8_tendencia", 1.3) * (d / max_d)

    # M9 — Markov: bonus para números que tienden a seguir al último sorteo
    markov = analisis_result.get("M9_markov", {})
    sucesores = markov.get("sucesores", {})
    # Identificar el último sorteo del df para usar como punto de partida
    # (lo hacemos desde afuera si está disponible en analisis_result)
    ultimo = analisis_result.get("_ultimo_sorteo", [])
    if sucesores and ultimo:
        markov_score = {n: 0.0 for n in range(1, rango + 1)}
        for prev in ultimo:
            for sucesor, prob in sucesores.get(prev, []):
                markov_score[sucesor] += prob
        max_ms = max(markov_score.values()) or 1
        for n in range(1, rango + 1):
            scores[n] += pesos.get("M9_markov", 1.1) * (markov_score[n] / max_ms)

    return scores


def _cumple_suma(nums: list[int], p25: float, p75: float) -> bool:
    return p25 <= sum(nums) <= p75


def _cumple_paridad(nums: list[int], mejor_pares: int) -> bool:
    """Filtra jugadas cuya distribución par/impar está cerca del óptimo histórico."""
    pares_actual = sum(1 for n in nums if n % 2 == 0)
    return abs(pares_actual - mejor_pares) <= 1


# ─────────────────────────────────────────────
# Generador de jugadas
# ─────────────────────────────────────────────
def generar_jugadas(juego: str, df: pd.DataFrame,
                    analisis_result: dict,
                    pesos: dict,
                    n_jugadas: int = 2) -> list[dict]:
    """
    Genera hasta n_jugadas sugerencias para el juego dado.
    Cada jugada incluye: números, extra (si aplica), método y score.
    """
    cfg    = config.JUEGOS.get(juego, {})
    n_nums = cfg.get("n_nums", 5)
    rango  = cfg.get("rango", 43)
    extra_cfg = cfg.get("extra")

    # Incluir último sorteo para Markov
    data_key = cfg.get("data_key", juego)
    if not df.empty:
        analisis_result["_ultimo_sorteo"] = [
            int(df.iloc[0][f"N{i+1}"])
            for i in range(n_nums)
            if pd.notna(df.iloc[0].get(f"N{i+1}"))
        ]

    scores = _score_numeros(analisis_result, pesos, rango)
    suma   = analisis_result.get("M4_suma", {})
    p25    = suma.get("p25", 0)
    p75    = suma.get("p75", rango * n_nums)
    mejor_pares = analisis_result.get("M6_paridad", {}).get("mejor_combo_pares", n_nums // 2)

    jugadas = []
    intentos = 0
    max_intentos = 5000

    # Usar scores como pesos de probabilidad
    pool  = list(range(1, rango + 1))
    pesos_arr = np.array([scores.get(n, 0) for n in pool], dtype=float)
    pesos_arr = np.clip(pesos_arr, 0, None)
    pesos_arr += 0.01  # mínimo para evitar ceros absolutos
    pesos_norm = pesos_arr / pesos_arr.sum()

    seen_sets = set()
    np.random.seed(int(datetime.now().strftime("%Y%m%d")) + sum(ord(c) for c in juego))

    while len(jugadas) < n_jugadas and intentos < max_intentos:
        intentos += 1
        eleccion = np.random.choice(pool, size=n_nums, replace=False, p=pesos_norm)
        nums = sorted(eleccion.tolist())
        key  = tuple(nums)
        if key in seen_sets:
            continue
        if not _cumple_suma(nums, p25, p75):
            continue
        if not _cumple_paridad(nums, mejor_pares):
            continue
        seen_sets.add(key)

        score_total = sum(scores.get(n, 0) for n in nums) / n_nums

        jugada = {
            "juego":  juego,
            "numeros": nums,
            "score":  round(score_total, 4),
            "suma":   sum(nums),
            "metodo": "LOOP-MULTI",
            "fecha":  datetime.now().strftime("%Y-%m-%d"),
        }

        # Extra (SuperBalota / signo)
        if extra_cfg:
            extra_rango = extra_cfg["rango"]
            extra_num   = int(np.random.randint(1, extra_rango + 1))
            jugada["extra"] = extra_num
            jugada["extra_nombre"] = extra_cfg["nombre"]

        jugadas.append(jugada)

    # Si no se generaron suficientes, relajar filtros
    if len(jugadas) < n_jugadas:
        while len(jugadas) < n_jugadas and intentos < max_intentos * 2:
            intentos += 1
            eleccion = np.random.choice(pool, size=n_nums, replace=False, p=pesos_norm)
            nums = sorted(eleccion.tolist())
            key  = tuple(nums)
            if key in seen_sets:
                continue
            seen_sets.add(key)
            jugada = {
                "juego": juego, "numeros": nums,
                "score": round(sum(scores.get(n, 0) for n in nums) / n_nums, 4),
                "suma":  sum(nums), "metodo": "LOOP-RELAX",
                "fecha": datetime.now().strftime("%Y-%m-%d"),
            }
            if extra_cfg:
                jugada["extra"] = int(np.random.randint(1, extra_cfg["rango"] + 1))
                jugada["extra_nombre"] = extra_cfg["nombre"]
            jugadas.append(jugada)

    # Ordenar por score descendente
    jugadas.sort(key=lambda x: -x["score"])
    return jugadas[:n_jugadas]


# ─────────────────────────────────────────────
# Llamada IA (Método 10)
# ─────────────────────────────────────────────
def enriquecer_con_ia(jugadas: list[dict], df: pd.DataFrame,
                       analisis_result: dict) -> list[dict]:
    """
    Intenta mejorar la jugada #1 con una sugerencia de Gemini.
    Si la IA responde, la agrega como jugada extra (no reemplaza).
    """
    if not jugadas:
        return jugadas

    juego    = jugadas[0]["juego"]
    cfg      = config.JUEGOS.get(juego, {})
    n_nums   = cfg.get("n_nums", 5)
    rango    = cfg.get("rango", 43)
    extra_r  = cfg.get("extra", {}).get("rango") if cfg.get("extra") else None
    sug_base = jugadas[0]["numeros"]

    ia_data = an.sugerencia_ia(juego, df, n_nums, rango, extra_r, sug_base)
    if not ia_data:
        return jugadas

    nums_ia = ia_data.get("sugerencia", [])
    if not isinstance(nums_ia, list) or len(nums_ia) != n_nums:
        return jugadas
    nums_ia = [int(n) for n in nums_ia if 1 <= int(n) <= rango]
    if len(nums_ia) != n_nums:
        return jugadas

    jugada_ia = {
        "juego":  juego,
        "numeros": sorted(nums_ia),
        "score":  float(ia_data.get("confianza", 50)) / 100,
        "suma":   sum(nums_ia),
        "metodo": "IA-GEMINI",
        "fecha":  datetime.now().strftime("%Y-%m-%d"),
    }
    if extra_r and "especial" in ia_data:
        try:
            esp = int(ia_data["especial"])
            if 1 <= esp <= extra_r:
                jugada_ia["extra"] = esp
                jugada_ia["extra_nombre"] = cfg["extra"]["nombre"]
        except Exception:
            pass

    # La jugada IA reemplaza la de menor score si ya tenemos el máximo
    if len(jugadas) >= config.N_SUGERENCIAS:
        jugadas[-1] = jugada_ia
    else:
        jugadas.append(jugada_ia)

    return jugadas


# ─────────────────────────────────────────────
# Guardar sugerencias en Excel
# ─────────────────────────────────────────────
def guardar_sugerencias_excel(todas: list[dict]):
    """Acumula sugerencias históricas en el Excel de seguimiento."""
    import shutil, tempfile
    df_new = pd.DataFrame(todas)
    if os.path.exists(config.SUGERENCIAS_FILE):
        df_old = pd.read_excel(config.SUGERENCIAS_FILE)
        df_all = pd.concat([df_new, df_old], ignore_index=True)
    else:
        df_all = df_new

    dir_name = os.path.dirname(os.path.abspath(config.SUGERENCIAS_FILE))
    fd, tmp = tempfile.mkstemp(suffix=".xlsx", dir=dir_name)
    os.close(fd)
    df_all.to_excel(tmp, index=False)
    if os.path.exists(config.SUGERENCIAS_FILE):
        os.remove(config.SUGERENCIAS_FILE)
    shutil.move(tmp, config.SUGERENCIAS_FILE)
    print(f"  ✓ Sugerencias guardadas: {config.SUGERENCIAS_FILE}")


# ─────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────
def generar_todas(datos: dict[str, pd.DataFrame],
                   analisis_todos: dict[str, dict],
                   usar_ia: bool = True) -> dict[str, list[dict]]:
    """
    Genera sugerencias para todos los juegos.
    Retorna dict: { "BALOTO": [...], "REVANCHA": [...], "MILOTO": [...] }
    """
    pesos = cargar_pesos()
    resultado = {}

    for juego in ["BALOTO", "REVANCHA", "MILOTO"]:
        cfg = config.JUEGOS.get(juego, {})
        data_key = cfg.get("data_key", juego)
        df = datos.get(data_key, pd.DataFrame())
        ar = analisis_todos.get(juego, analisis_todos.get(data_key, {}))

        print(f"\n[SUGERENCIAS] {juego}")
        jugadas = generar_jugadas(juego, df, ar, pesos, config.N_SUGERENCIAS)

        if usar_ia and jugadas:
            jugadas = enriquecer_con_ia(jugadas, df, ar)

        resultado[juego] = jugadas
        for j in jugadas:
            nums_str = "-".join(map(str, j["numeros"]))
            extra_str = f" | {j['extra_nombre']}: {j.get('extra', '?')}" if "extra" in j else ""
            print(f"  [{j['metodo']}] {nums_str}{extra_str}  (score: {j['score']})")

    return resultado


if __name__ == "__main__":
    import scraper
    datos  = scraper.actualizar_datos(300)
    an_res = {}
    for juego in ["BALOTO", "MILOTO"]:
        df = datos.get(juego, pd.DataFrame())
        an_res[juego] = an.analizar(juego, df)
    an_res["REVANCHA"] = an_res.get("BALOTO", {})

    todas_sug = generar_todas(datos, an_res, usar_ia=False)
    guardar_sugerencias_excel([j for jl in todas_sug.values() for j in jl])
