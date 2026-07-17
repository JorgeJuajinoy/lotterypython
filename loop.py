# -*- coding: utf-8 -*-
"""
loop.py -- Paso 5 del Loop
Orquesta el ciclo completo:
  Scraping -> Analisis -> Sugerencias -> Verificacion -> Ajuste -> Informe
Repite hasta alcanzar el objetivo de acierto o agotar iteraciones.
"""
import json
import os
from datetime import datetime
import config
import scraper
import analisis as an
import sugerencias as sug
import verificacion as ver
import informe


LOOP_LOG_FILE = os.path.join(config.DATA_DIR, "loop_log.json")


# ─────────────────────────────────────────────
# Log persistente del loop
# ─────────────────────────────────────────────
def cargar_log() -> list[dict]:
    if os.path.exists(LOOP_LOG_FILE):
        try:
            with open(LOOP_LOG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def guardar_log(log: list[dict]):
    with open(LOOP_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2, default=str)


# ─────────────────────────────────────────────
# CICLO PRINCIPAL
# ─────────────────────────────────────────────
def ejecutar_loop(n_sorteos: int = 300,
                  max_iter: int = None,
                  objetivo: float = None,
                  usar_ia: bool = True,
                  verbose: bool = True) -> dict:
    """
    Ejecuta el loop completo.

    Parámetros
    ----------
    n_sorteos : int
        Número de sorteos históricos a obtener por juego.
    max_iter : int
        Máximo de iteraciones (default: config.MAX_ITERACIONES).
    objetivo : float
        % de acierto objetivo 0-1 (default: config.OBJETIVO_ACIERTO).
    usar_ia : bool
        Si True, llama a Gemini para enriquecer sugerencias.
    verbose : bool
        Si True, imprime progreso detallado.

    Retorna
    -------
    dict con el estado final del loop.
    """
    if max_iter is None:
        max_iter = config.MAX_ITERACIONES
    if objetivo is None:
        objetivo = config.OBJETIVO_ACIERTO

    log = cargar_log()

    print("=" * 60)
    print("  LOTTERY LOOP - INICIO")
    print(f"  Objetivo: {objetivo * 100:.0f}% | Max iter: {max_iter}")
    print("=" * 60)

    pesos_actuales = sug.cargar_pesos()
    acierto_actual = 0.0
    iteracion      = 0
    datos_cache    = None
    an_cache       = {}

    while iteracion < max_iter and acierto_actual < objetivo:
        iteracion += 1
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{'-'*60}")
        print(f"  ITERACION {iteracion}/{max_iter}  --  {ts}")
        print(f"{'-'*60}")

        # ── PASO 1: SCRAPING ────────────────────────────────────────
        if iteracion == 1 or datos_cache is None:
            print("\n[1] SCRAPING...")
            datos_cache = scraper.actualizar_datos(n_sorteos)
        else:
            print("\n[1] Usando datos en caché (no se re-scrapea cada iteración)")

        # ── PASO 2: ANÁLISIS ─────────────────────────────────────────
        print("\n[2] ANÁLISIS...")
        an_cache = {}
        for juego_key in ["BALOTO", "MILOTO"]:
            df = datos_cache.get(juego_key)
            if df is not None and not df.empty:
                an_cache[juego_key] = an.analizar(juego_key, df)
        an_cache["REVANCHA"] = an_cache.get("BALOTO", {})

        # ── PASO 3: SUGERENCIAS ──────────────────────────────────────
        print("\n[3] GENERANDO SUGERENCIAS...")
        todas_sug = sug.generar_todas(datos_cache, an_cache, usar_ia=usar_ia)
        todas_lista = [j for jl in todas_sug.values() for j in jl]
        sug.guardar_sugerencias_excel(todas_lista)

        # ── PASO 4: VERIFICACIÓN (backtest histórico) ────────────────
        print("\n[4] VERIFICANDO ACIERTOS (backtest con datos históricos)...")
        veri = ver.backtest_historico(
            datos=datos_cache,
            analisis_todos=an_cache,
            pesos=pesos_actuales,
            ventana_test=min(50, n_sorteos // 6),
        )
        acierto_actual = veri.get("global_pct", 0.0)

        print(f"\n  Simulaciones: {veri['n_evaluadas']}")
        print(f"  Hits:         {veri.get('n_hits', 0)}")
        print(f"  % Acierto:   {acierto_actual * 100:.1f}%  (objetivo: {objetivo * 100:.0f}%)")
        for j, d in veri.get("por_juego", {}).items():
            print(f"    {j}: {d.get('hits',0)}/{d.get('total',0)} hits | prom aciertos: {d.get('acierto_prom',0)}")


        # Registro en log
        pesos_antes = pesos_actuales.copy()

        # ── PASO 5: AJUSTE DE PESOS (si no alcanzó objetivo) ─────────
        if acierto_actual < objetivo and iteracion < max_iter:
            print(f"\n[5] AJUSTANDO PESOS (acierto {acierto_actual*100:.1f}% < objetivo {objetivo*100:.0f}%)...")
            pesos_nuevos = ver.ajustar_pesos(veri, pesos_actuales)
            delta = {k: round(pesos_nuevos[k] - pesos_actuales.get(k, 0), 3)
                     for k in pesos_nuevos
                     if pesos_nuevos[k] != pesos_actuales.get(k)}
            pesos_actuales = pesos_nuevos
            sug.guardar_pesos(pesos_actuales)
            if delta:
                print(f"  Cambios pesos: {delta}")
            else:
                print("  Sin cambios en pesos (datos insuficientes)")
        else:
            delta = {}

        # Guardar entrada en log
        log_entry = {
            "iteracion":   iteracion,
            "timestamp":   ts,
            "acierto_pct": acierto_actual,
            "n_evaluadas": veri["n_evaluadas"],
            "n_hits":      veri.get("n_hits", 0),
            "pesos_delta": delta,
        }
        log.append(log_entry)
        guardar_log(log)

        # ── PASO 6: INFORME PARCIAL ─────────────────────────────────
        print("\n[6] GENERANDO INFORME PARCIAL...")
        informe.generar_html(todas_sug, veri, log)
        informe.generar_excel(todas_sug, veri, log)

        if acierto_actual >= objetivo:
            print(f"\n  [OK] OBJETIVO ALCANZADO: {acierto_actual * 100:.1f}% >= {objetivo * 100:.0f}%")
            break
        elif iteracion < max_iter:
            print(f"\n  >> Continuando con iteracion {iteracion + 1}...")

    # ── RESUMEN FINAL ────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  LOOP FINALIZADO")
    
    calificaciones_ia = {}
    if usar_ia and 'todas_sug' in locals() and an_cache:
        print("\n  [IA] SOLICITANDO ANÁLISIS DE PATRONES A GEMINI...")
        for juego in ["BALOTO", "REVANCHA", "MILOTO"]:
            ar = an_cache.get(juego)
            jugs = todas_sug.get(juego, [])
            if ar and jugs:
                calif = an.calificar_patrones_ia(juego, ar, jugs)
                if calif:
                    calificaciones_ia[juego] = calif
                    print(f"    - {juego}: {calif['score']}/100 -> {calif['analisis']}")
        
        if calificaciones_ia:
            print("  >> Actualizando informes con análisis IA...")
            informe.generar_html(todas_sug, veri, log, calificaciones_ia=calificaciones_ia)
            # generar_excel no cambia por ahora, pero se le puede pasar si se desea
    
    print(f"\n  Iteraciones realizadas: {iteracion}")
    print(f"  Acierto final:          {acierto_actual * 100:.1f}%")
    print(f"  Objetivo:               {objetivo * 100:.0f}%")
    alcanzado = acierto_actual >= objetivo
    print(f"  Objetivo alcanzado:     {'SI' if alcanzado else 'NO (datos insuficientes para verificar)'}")
    print(f"  Informe HTML:           {config.INFORME_HTML}")
    print(f"  Informe Excel:          {config.INFORME_XLSX}")
    print(f"{'='*60}\n")

    return {
        "iteraciones":    iteracion,
        "acierto_final":  acierto_actual,
        "objetivo_logrado": alcanzado,
        "sugerencias":    todas_sug if 'todas_sug' in locals() else {},
        "verificacion":   veri if 'veri' in locals() else {},
        "log":            log,
    }


if __name__ == "__main__":
    resultado = ejecutar_loop(
        n_sorteos=300,
        max_iter=config.MAX_ITERACIONES,
        objetivo=config.OBJETIVO_ACIERTO,
        usar_ia=True,
        verbose=True,
    )
