"""
informe.py — Paso 6 del Loop
Genera reporte HTML premium + Excel con sugerencias, verificaciones y métricas.
"""
import pandas as pd
import os
from datetime import datetime
import config


# ─────────────────────────────────────────────
# HTML helpers
# ─────────────────────────────────────────────
def _badge(texto: str, color: str = "#38BDF8") -> str:
    return (
        f'<span style="background:{color};color:#0F172A;padding:3px 10px;'
        f'border-radius:20px;font-size:0.78em;font-weight:700">{texto}</span>'
    )


def _numero_pill(n: int, score: float = 0.5) -> str:
    """Bola de número con color según score."""
    hue = int(200 + score * 80)  # azul → verde según score
    return (
        f'<span style="display:inline-flex;align-items:center;justify-content:center;'
        f'width:38px;height:38px;border-radius:50%;'
        f'background:hsl({hue},80%,50%);color:#fff;'
        f'font-weight:800;font-size:1em;margin:2px;'
        f'box-shadow:0 2px 8px rgba(0,0,0,0.4)">{n}</span>'
    )


def _metodo_color(metodo: str) -> str:
    colors = {
        "LOOP-MULTI": "#22C55E",
        "LOOP-RELAX": "#F59E0B",
        "IA-GEMINI":  "#A855F7",
    }
    return colors.get(metodo, "#38BDF8")


def _tabla_sugerencias(sugerencias_por_juego: dict) -> str:
    """Genera la sección de tarjetas de sugerencias."""
    html = ""
    for juego, jugadas in sugerencias_por_juego.items():
        if not jugadas:
            continue
        html += f"""
        <div class="card">
          <div class="card-header">
            <span class="game-title">{juego}</span>
            {_badge("HOY", "#22C55E")}
          </div>
          <div class="plays-list">
        """
        for i, j in enumerate(jugadas, 1):
            nums    = j.get("numeros", [])
            metodo  = j.get("metodo", "")
            score   = j.get("score", 0.5)
            extra   = j.get("extra")
            en      = j.get("extra_nombre", "")
            pct_conf = int(min(score * 100, 99)) if score <= 1 else int(min(score, 99))

            bolas   = "".join(_numero_pill(n, score) for n in nums)
            extra_html = (
                f'<span class="extra-pill">{en}: <strong>{extra}</strong></span>'
                if extra else ""
            )
            color_m = _metodo_color(metodo)

            html += f"""
            <div class="play-row">
              <div class="play-num">{i}</div>
              <div class="balls">{bolas}{extra_html}</div>
              <div class="play-meta">
                {_badge(metodo, color_m)}
                <span class="confidence">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                       stroke="#22C55E" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/></svg>
                  {pct_conf}% conf.
                </span>
              </div>
            </div>
            """
        html += "</div></div>"
    return html


def _tabla_verificacion(veri: dict) -> str:
    """Genera tabla de verificación de aciertos por juego."""
    por_juego = veri.get("por_juego", {})
    if not por_juego:
        return '<p class="dim-text">Sin datos de verificación aún.</p>'

    rows = ""
    for j, d in por_juego.items():
        pct = d.get("pct", 0) * 100
        color = "#22C55E" if pct >= 90 else ("#F59E0B" if pct >= 60 else "#EF4444")
        bar_w = int(pct)
        rows += f"""
        <tr>
          <td class="td-game">{j}</td>
          <td>{d.get('total', 0)}</td>
          <td>{d.get('hits', 0)}</td>
          <td>{d.get('acierto_prom', 0):.1f}</td>
          <td>
            <div class="bar-bg">
              <div class="bar-fill" style="width:{bar_w}%;background:{color}"></div>
            </div>
            <span style="color:{color};font-weight:700">{pct:.1f}%</span>
          </td>
        </tr>
        """
    return f"""
    <table class="data-table">
      <thead><tr>
        <th>Juego</th><th>Evaluadas</th><th>Hits (≥{config.ACIERTO_MIN_NUMS}✓)</th>
        <th>Prom. aciertos</th><th>% Éxito</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
    """


def _seccion_iteraciones(log: list[dict]) -> str:
    if not log:
        return '<p class="dim-text">Sin iteraciones registradas.</p>'
    rows = ""
    for i, it in enumerate(log, 1):
        pct = it.get("acierto_pct", 0) * 100
        color = "#22C55E" if pct >= 90 else ("#F59E0B" if pct >= 60 else "#EF4444")
        rows += f"""
        <tr>
          <td>#{i}</td>
          <td>{it.get('timestamp', '')}</td>
          <td style="color:{color};font-weight:700">{pct:.1f}%</td>
          <td>{it.get('n_evaluadas', 0)}</td>
          <td>{", ".join(f"{k}={v}" for k,v in it.get('pesos_delta', {}).items())}</td>
        </tr>
        """
    return f"""
    <table class="data-table">
      <thead><tr><th>It.</th><th>Fecha</th><th>% Acierto</th>
      <th>Evaluadas</th><th>Ajustes pesos</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    """


def _chart_js_script(veri: dict) -> str:
    """Genera Chart.js para gráfica de frecuencias (si hay detalle)."""
    por_metodo = veri.get("por_metodo", {})
    if not por_metodo:
        return ""
    labels = list(por_metodo.keys())
    valores = [round(d.get("pct", 0) * 100, 1) for d in por_metodo.values()]
    colores = [_metodo_color(m) for m in labels]
    return f"""
    <canvas id="metodoChart" style="max-height:220px"></canvas>
    <script>
    new Chart(document.getElementById('metodoChart'), {{
      type: 'bar',
      data: {{
        labels: {labels},
        datasets: [{{
          label: '% Éxito por Método',
          data: {valores},
          backgroundColor: {colores},
          borderRadius: 8,
        }}]
      }},
      options: {{
        responsive: true,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{
          y: {{ beginAtZero: true, max: 100,
               grid: {{ color: 'rgba(255,255,255,0.05)' }},
               ticks: {{ color: '#94A3B8' }} }},
          x: {{ grid: {{ display: false }},
               ticks: {{ color: '#94A3B8' }} }},
        }}
      }}
    }});
    </script>
    """


def _seccion_ia(calificaciones_ia: dict) -> str:
    if not calificaciones_ia:
        return ""
    html = '<div class="section"><h2 class="section-title">🧠 Análisis IA de Patrones</h2><div class="games-grid">'
    for juego, calif in calificaciones_ia.items():
        score = calif.get("score", 50)
        analisis = calif.get("analisis", "")
        color = "#22C55E" if score >= 80 else ("#F59E0B" if score >= 50 else "#EF4444")
        html += f"""
        <div class="card" style="border-left: 4px solid {color}">
          <div class="card-header">
            <span class="game-title">{juego}</span>
            <span style="background:{color};color:#0F172A;padding:3px 10px;border-radius:20px;font-size:0.78em;font-weight:700">{score}/100</span>
          </div>
          <div style="padding: 16px; font-size: 0.9rem; color: #E2E8F0; line-height: 1.5; font-style: italic;">
            "{analisis}"
          </div>
        </div>
        """
    html += '</div></div>'
    return html


# ─────────────────────────────────────────────
# GENERAR HTML
# ─────────────────────────────────────────────
def generar_html(sugerencias_por_juego: dict,
                 veri: dict,
                 loop_log: list[dict],
                 calificaciones_ia: dict = None,
                 filepath: str = None) -> str:

    if filepath is None:
        filepath = config.INFORME_HTML

    fecha_hoy   = datetime.now().strftime("%d/%m/%Y %H:%M")
    global_pct  = veri.get("global_pct", 0) * 100
    n_ev        = veri.get("n_evaluadas", 0)
    color_g     = "#22C55E" if global_pct >= 90 else ("#F59E0B" if global_pct >= 60 else "#EF4444")

    html_sug    = _tabla_sugerencias(sugerencias_por_juego)
    html_veri   = _tabla_verificacion(veri)
    html_iters  = _seccion_iteraciones(loop_log)
    html_chart  = _chart_js_script(veri)
    html_ia     = _seccion_ia(calificaciones_ia)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Lottery Loop — Informe de Sugerencias</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin:0; padding:0; }}
    :root {{
      --bg:       #070D1A;
      --surface:  #0F1E33;
      --card:     #162236;
      --border:   rgba(56,189,248,0.15);
      --accent:   #38BDF8;
      --text:     #E2E8F0;
      --dim:      #64748B;
      --green:    #22C55E;
      --amber:    #F59E0B;
      --red:      #EF4444;
      --purple:   #A855F7;
    }}
    body {{
      background: var(--bg);
      font-family: 'Inter', sans-serif;
      color: var(--text);
      min-height: 100vh;
    }}

    /* ─── HEADER ─────────────────────────── */
    .header {{
      background: linear-gradient(135deg, #0F1E33 0%, #0A1628 60%, #070D1A 100%);
      border-bottom: 1px solid var(--border);
      padding: 32px 40px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
    }}
    .header-left h1 {{
      font-size: 2rem;
      font-weight: 800;
      background: linear-gradient(90deg, var(--accent), var(--purple));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      letter-spacing: -0.5px;
    }}
    .header-left p {{ color: var(--dim); font-size: 0.9rem; margin-top: 4px; }}
    .header-badge {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .big-badge {{
      padding: 10px 24px;
      border-radius: 50px;
      font-weight: 800;
      font-size: 1.4rem;
      color: var(--bg);
      background: {color_g};
      box-shadow: 0 0 24px {color_g}60;
    }}
    .big-badge-label {{ color: var(--dim); font-size: 0.8rem; text-align:right; }}

    /* ─── LAYOUT ─────────────────────────── */
    .container {{ max-width: 1100px; margin: 0 auto; padding: 36px 24px; }}
    .section {{ margin-bottom: 48px; }}
    .section-title {{
      font-size: 1.1rem;
      font-weight: 700;
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 1px;
      margin-bottom: 20px;
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .section-title::after {{
      content: '';
      flex: 1;
      height: 1px;
      background: var(--border);
    }}

    /* ─── CARDS DE JUEGO ─────────────────── */
    .games-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 24px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      overflow: hidden;
      transition: transform .2s, box-shadow .2s;
    }}
    .card:hover {{
      transform: translateY(-3px);
      box-shadow: 0 12px 40px rgba(56,189,248,0.12);
    }}
    .card-header {{
      background: linear-gradient(90deg, rgba(56,189,248,0.08), transparent);
      padding: 14px 20px;
      display: flex;
      align-items: center;
      gap: 12px;
      border-bottom: 1px solid var(--border);
    }}
    .game-title {{
      font-weight: 800;
      font-size: 1.1rem;
      color: var(--accent);
      flex: 1;
    }}
    .plays-list {{ padding: 16px; display: flex; flex-direction: column; gap: 14px; }}
    .play-row {{
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 14px;
      background: rgba(255,255,255,0.03);
      border-radius: 12px;
      border: 1px solid rgba(255,255,255,0.06);
    }}
    .play-num {{
      font-size: 0.75rem;
      font-weight: 700;
      color: var(--dim);
      width: 20px;
      text-align: center;
    }}
    .balls {{ display: flex; flex-wrap: wrap; gap: 2px; flex: 1; align-items:center; }}
    .extra-pill {{
      background: rgba(168,85,247,0.2);
      color: #C084FC;
      border-radius: 8px;
      padding: 3px 10px;
      font-size: 0.8em;
      margin-left: 6px;
    }}
    .play-meta {{
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 5px;
      min-width: 90px;
    }}
    .confidence {{
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 0.78rem;
      color: var(--green);
    }}

    /* ─── TABLAS ─────────────────────────── */
    .data-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.9rem;
    }}
    .data-table th {{
      background: rgba(56,189,248,0.07);
      color: var(--accent);
      font-weight: 700;
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      padding: 12px 16px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }}
    .data-table td {{
      padding: 11px 16px;
      border-bottom: 1px solid rgba(255,255,255,0.04);
      color: var(--text);
    }}
    .data-table tr:hover td {{ background: rgba(255,255,255,0.02); }}
    .td-game {{ font-weight: 700; color: var(--accent); }}
    .bar-bg {{
      width: 100px; height: 6px;
      background: rgba(255,255,255,0.08);
      border-radius: 3px; overflow: hidden;
      display: inline-block; vertical-align: middle; margin-right: 8px;
    }}
    .bar-fill {{ height: 100%; border-radius: 3px; transition: width .5s; }}

    /* ─── STATS TOP ROW ──────────────────── */
    .stats-row {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 16px;
      margin-bottom: 40px;
    }}
    .stat-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 20px;
      text-align: center;
    }}
    .stat-value {{
      font-size: 2rem;
      font-weight: 800;
      color: var(--accent);
      line-height: 1;
      margin-bottom: 6px;
    }}
    .stat-label {{ font-size: 0.78rem; color: var(--dim); text-transform: uppercase; letter-spacing: 0.5px; }}
    .dim-text {{ color: var(--dim); font-style: italic; }}

    /* ─── CHART WRAPPER ──────────────────── */
    .chart-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 24px;
      margin-top: 24px;
    }}

    /* ─── FOOTER ─────────────────────────── */
    footer {{
      text-align: center;
      padding: 24px;
      color: var(--dim);
      font-size: 0.8rem;
      border-top: 1px solid var(--border);
      margin-top: 20px;
    }}
  </style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <h1>🎯 Lottery Loop</h1>
    <p>Sistema de predicción estadística + IA | {fecha_hoy}</p>
  </div>
  <div class="header-badge">
    <div>
      <div class="big-badge-label">Acierto global</div>
      <div class="big-badge">{global_pct:.1f}%</div>
    </div>
  </div>
</div>

<div class="container">

  <!-- STATS RÁPIDAS -->
  <div class="stats-row">
    <div class="stat-card">
      <div class="stat-value" style="color:{color_g}">{global_pct:.1f}%</div>
      <div class="stat-label">Acierto Global</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{n_ev}</div>
      <div class="stat-label">Jugadas Evaluadas</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{veri.get("n_hits", 0)}</div>
      <div class="stat-label">Hits (≥{config.ACIERTO_MIN_NUMS}✓)</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{config.N_SUGERENCIAS}</div>
      <div class="stat-label">Jugadas/Juego</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{config.ACIERTO_MIN_NUMS}</div>
      <div class="stat-label">Mín. Aciertos Hit</div>
    </div>
  </div>

  <!-- SUGERENCIAS HOY -->
  <div class="section">
    <h2 class="section-title">🃏 Sugerencias de Hoy</h2>
    <div class="games-grid">
      {html_sug}
    </div>
  </div>

  {html_ia}

  <!-- VERIFICACIÓN -->
  <div class="section">
    <h2 class="section-title">✅ Verificación de Aciertos</h2>
    {html_veri}
    <div class="chart-card">
      <h3 style="font-size:.85rem;color:var(--dim);margin-bottom:16px">
        RENDIMIENTO POR MÉTODO
      </h3>
      {html_chart}
    </div>
  </div>

  <!-- ITERACIONES DEL LOOP -->
  <div class="section">
    <h2 class="section-title">🔁 Historial de Iteraciones</h2>
    {html_iters}
  </div>

</div>

<footer>
  Generado por Lottery Loop · {fecha_hoy} · 
  Criterio: ≥{config.ACIERTO_MIN_NUMS} aciertos por jugada = HIT · Objetivo: {config.OBJETIVO_ACIERTO*100:.0f}%
</footer>
</body>
</html>"""

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✓ HTML guardado: {filepath}")
    return html


# ─────────────────────────────────────────────
# GENERAR EXCEL
# ─────────────────────────────────────────────
def generar_excel(sugerencias_por_juego: dict,
                  veri: dict,
                  loop_log: list[dict],
                  filepath: str = None):
    if filepath is None:
        filepath = config.INFORME_XLSX

    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    # Si el archivo está abierto en Excel, guardamos con timestamp para no interrumpir el loop
    def _excel_writer(path):
        try:
            return pd.ExcelWriter(path, engine="openpyxl")
        except PermissionError:
            from datetime import datetime
            ts = datetime.now().strftime("%H%M%S")
            alt = path.replace(".xlsx", f"_{ts}.xlsx")
            print(f"  [INFORME] Archivo bloqueado, guardando en: {alt}")
            return pd.ExcelWriter(alt, engine="openpyxl")

    with _excel_writer(filepath) as writer:

        # Hoja 1: Sugerencias
        rows_sug = []
        for juego, jugadas in sugerencias_por_juego.items():
            for j in jugadas:
                row = {
                    "Juego":   juego,
                    "Método":  j.get("metodo", ""),
                    "Números": "-".join(map(str, j.get("numeros", []))),
                    "Extra":   j.get("extra", ""),
                    "Score":   j.get("score", ""),
                    "Suma":    j.get("suma", ""),
                    "Fecha":   j.get("fecha", ""),
                }
                rows_sug.append(row)
        pd.DataFrame(rows_sug).to_excel(writer, sheet_name="Sugerencias", index=False)

        # Hoja 2: Verificación detalle
        detalle = veri.get("detalle", [])
        if detalle:
            rows_det = []
            for d in detalle:
                rows_det.append({
                    "Juego":      d["juego"],
                    "Fecha":      d["fecha"],
                    "Método":     d["metodo"],
                    "Sugerencia": "-".join(map(str, d["sugerencia"])),
                    "Resultado":  "-".join(map(str, d["resultado"])),
                    "Aciertos":   d["aciertos"],
                    "Hit":        "✓" if d["es_hit"] else "✗",
                })
            pd.DataFrame(rows_det).to_excel(writer, sheet_name="Verificación", index=False)

        # Hoja 3: Resumen por juego
        por_juego = veri.get("por_juego", {})
        if por_juego:
            rows_j = [{"Juego": k, **v} for k, v in por_juego.items()]
            pd.DataFrame(rows_j).to_excel(writer, sheet_name="Por Juego", index=False)

        # Hoja 4: Loop Log
        if loop_log:
            pd.DataFrame(loop_log).to_excel(writer, sheet_name="Loop Log", index=False)

    print(f"  ✓ Excel guardado: {filepath}")


if __name__ == "__main__":
    # Test rápido sin datos reales
    sug_test = {
        "BALOTO":   [{"juego": "BALOTO",   "numeros": [5, 14, 21, 34, 42], "extra": 7,  "extra_nombre": "SuperBalota", "score": 0.73, "suma": 116, "metodo": "LOOP-MULTI", "fecha": "2026-07-14"}],
        "REVANCHA": [{"juego": "REVANCHA", "numeros": [3, 11, 27, 38, 40], "extra": 12, "extra_nombre": "SuperBalota", "score": 0.61, "suma": 119, "metodo": "LOOP-MULTI", "fecha": "2026-07-14"}],
        "MILOTO":   [{"juego": "MILOTO",   "numeros": [2, 10, 19, 28, 35], "score": 0.68, "suma": 94, "metodo": "LOOP-MULTI", "fecha": "2026-07-14"}],
    }
    veri_test = {"global_pct": 0.0, "n_evaluadas": 0, "n_hits": 0, "detalle": [], "por_juego": {}, "por_metodo": {}}
    generar_html(sug_test, veri_test, [])
    generar_excel(sug_test, veri_test, [])
    print("Test de informe completado.")
