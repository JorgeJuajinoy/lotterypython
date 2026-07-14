"""
scraper.py — Paso 1 del Loop
Obtiene los últimos 300 sorteos de Baloto/Revancha y Miloto.
Guarda en data/baloto_300.xlsx y data/miloto_300.xlsx
"""
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import re
import shutil
import tempfile
import config

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ─────────────────────────────────────────────
# Utilidades de archivo
# ─────────────────────────────────────────────
def safe_save(df: pd.DataFrame, filepath: str) -> bool:
    """Guarda un DataFrame de forma atómica (evita corrupción)."""
    try:
        dir_name = os.path.dirname(os.path.abspath(filepath))
        fd, tmp = tempfile.mkstemp(suffix=".xlsx", dir=dir_name)
        os.close(fd)
        df.to_excel(tmp, index=False)
        if os.path.exists(filepath):
            os.remove(filepath)
        shutil.move(tmp, filepath)
        return True
    except Exception as e:
        print(f"[ERROR] No se pudo guardar {filepath}: {e}")
        return False


def _seed_from_legacy(filepath: str, legacy: str) -> pd.DataFrame:
    """Si el archivo propio no existe, carga el legado como punto de partida."""
    if not os.path.exists(filepath) and os.path.exists(legacy):
        print(f"  ↪ Semilla legado: {legacy}")
        return pd.read_excel(legacy)
    if os.path.exists(filepath):
        return pd.read_excel(filepath)
    return pd.DataFrame()


# ─────────────────────────────────────────────
# SCRAPER BALOTO / REVANCHA
# ─────────────────────────────────────────────
def _parse_baloto_page(html: str) -> list[dict]:
    """Extrae filas de resultados de Baloto/Revancha de una página HTML."""
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.find_all("tr"):
        link = tr.find("a", href=re.compile(r'/resultados-(baloto|revancha)/'))
        if not link:
            continue
        date_td = tr.find("td", class_="creation-date-results")
        if not date_td:
            continue
        date_str = date_td.text.strip()
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue
        nums_text = tds[2].text.strip().replace('\n', '').replace('\r', '')
        nums = [int(n.strip()) for n in nums_text.split("-") if n.strip().isdigit()]
        if len(nums) < 6:
            continue
        sb = nums[-1]
        nums = nums[:-1]
        is_revancha = "resultados-revancha" in link["href"]
        sorteo_id = link["href"].strip('/').split("/")[-1]
        rows.append({
            "Sorteo": sorteo_id,
            "Fecha":  date_str,
            "N1": nums[0], "N2": nums[1], "N3": nums[2],
            "N4": nums[3], "N5": nums[4],
            "SB": sb,
            "Tipo": "Revancha" if is_revancha else "Baloto",
        })
    return rows


def scrape_baloto(n_sorteos: int = 300) -> pd.DataFrame:
    """Scrapea hasta n_sorteos de Baloto+Revancha paginando el sitio."""
    print(f"[SCRAPER] Baloto — objetivo {n_sorteos} sorteos...")
    all_rows: list[dict] = []
    page = 1
    base_url = "https://www.baloto.com/resultados"

    while len(all_rows) < n_sorteos:
        url = base_url if page == 1 else f"{base_url}?page={page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                print(f"  HTTP {resp.status_code} en página {page}. Deteniendo.")
                break
            rows = _parse_baloto_page(resp.text)
            if not rows:
                print(f"  Sin filas en página {page}. Fin de datos.")
                break
            all_rows.extend(rows)
            print(f"  Página {page}: {len(rows)} filas | Total: {len(all_rows)}")
            page += 1
        except Exception as e:
            print(f"  [ERROR] Página {page}: {e}")
            break

    df = pd.DataFrame(all_rows[:n_sorteos])
    return df


# ─────────────────────────────────────────────
# SCRAPER MILOTO
# ─────────────────────────────────────────────
def _parse_miloto_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.find_all("tr"):
        link = tr.find("a", href=re.compile(r'/miloto/resultados-miloto/'))
        if not link:
            continue
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        date_str = tds[0].text.strip()
        nums_text = tds[1].text.strip().replace('\n', '').replace('\r', '')
        nums = [int(n.strip()) for n in nums_text.split("-") if n.strip().isdigit()]
        if len(nums) < 5:
            continue
        sorteo_id = link["href"].strip('/').split("/")[-1]
        rows.append({
            "Sorteo": sorteo_id,
            "Fecha":  date_str,
            "N1": nums[0], "N2": nums[1], "N3": nums[2],
            "N4": nums[3], "N5": nums[4],
        })
    return rows


def scrape_miloto(n_sorteos: int = 300) -> pd.DataFrame:
    """Scrapea hasta n_sorteos de Miloto paginando el sitio."""
    print(f"[SCRAPER] Miloto — objetivo {n_sorteos} sorteos...")
    all_rows: list[dict] = []
    page = 1
    base_url = "https://www.baloto.com/miloto/resultados/"

    while len(all_rows) < n_sorteos:
        url = base_url if page == 1 else f"{base_url}?page={page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                print(f"  HTTP {resp.status_code} en página {page}. Deteniendo.")
                break
            rows = _parse_miloto_page(resp.text)
            if not rows:
                print(f"  Sin filas en página {page}. Fin de datos.")
                break
            all_rows.extend(rows)
            print(f"  Página {page}: {len(rows)} filas | Total: {len(all_rows)}")
            page += 1
        except Exception as e:
            print(f"  [ERROR] Página {page}: {e}")
            break

    df = pd.DataFrame(all_rows[:n_sorteos])
    return df


# ─────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────
def actualizar_datos(n_sorteos: int = 300) -> dict[str, pd.DataFrame]:
    """
    Actualiza (o crea) los archivos de datos con los últimos n_sorteos.
    Retorna dict con DataFrames: {"BALOTO": df_b, "MILOTO": df_m}
    """
    resultados = {}

    # --- BALOTO ---
    legacy_b = _seed_from_legacy(config.FILES["BALOTO"], config.BALOTO_LEGACY)
    fresh_b  = scrape_baloto(n_sorteos)

    if not fresh_b.empty:
        # Combinar con legado para no perder datos históricos
        if not legacy_b.empty:
            combined = pd.concat([fresh_b, legacy_b], ignore_index=True)
            combined.drop_duplicates(subset=["Sorteo", "Tipo"], inplace=True)
        else:
            combined = fresh_b
        combined = combined.head(n_sorteos)
        safe_save(combined, config.FILES["BALOTO"])
        resultados["BALOTO"] = combined
        print(f"  ✓ Baloto guardado: {len(combined)} registros")
    elif not legacy_b.empty:
        resultados["BALOTO"] = legacy_b
        print(f"  ↪ Usando datos legado Baloto: {len(legacy_b)} registros")
    else:
        resultados["BALOTO"] = pd.DataFrame()
        print("  ✗ Sin datos Baloto")

    # --- MILOTO ---
    legacy_m = _seed_from_legacy(config.FILES["MILOTO"], config.MILOTO_LEGACY)
    fresh_m  = scrape_miloto(n_sorteos)

    if not fresh_m.empty:
        if not legacy_m.empty:
            combined_m = pd.concat([fresh_m, legacy_m], ignore_index=True)
            combined_m.drop_duplicates(subset=["Sorteo"], inplace=True)
        else:
            combined_m = fresh_m
        combined_m = combined_m.head(n_sorteos)
        safe_save(combined_m, config.FILES["MILOTO"])
        resultados["MILOTO"] = combined_m
        print(f"  ✓ Miloto guardado: {len(combined_m)} registros")
    elif not legacy_m.empty:
        resultados["MILOTO"] = legacy_m
        print(f"  ↪ Usando datos legado Miloto: {len(legacy_m)} registros")
    else:
        resultados["MILOTO"] = pd.DataFrame()
        print("  ✗ Sin datos Miloto")

    return resultados


if __name__ == "__main__":
    datos = actualizar_datos(300)
    for juego, df in datos.items():
        print(f"\n{juego}: {len(df)} registros")
        if not df.empty:
            print(df.head(3).to_string(index=False))
