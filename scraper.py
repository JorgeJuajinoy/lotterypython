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
        print(f"  -> Semilla legado: {legacy}")
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


def scrape_baloto(n_sorteos: int = 300, existing_ids: set = None) -> pd.DataFrame:
    """
    Scrapea sorteos de Baloto+Revancha paginando el sitio de forma incremental.
    Se detiene inmediatamente si encuentra un Sorteo ID ya existente localmente.
    """
    if existing_ids is None:
        existing_ids = set()
        
    print(f"[SCRAPER] Baloto — buscando nuevos sorteos...")
    all_rows: list[dict] = []
    page = 1
    base_url = "https://www.baloto.com/resultados"
    stop_scraping = False

    while len(all_rows) < n_sorteos and not stop_scraping:
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
                
            # Verificar de forma incremental
            for r in rows:
                # Si encontramos un sorteo que ya tenemos guardado localmente, paramos
                if r["Sorteo"] in existing_ids:
                    print(f"  -> Encontrado sorteo existente '{r['Sorteo']}'. Deteniendo scraping.")
                    stop_scraping = True
                    break
                all_rows.append(r)
                
            if stop_scraping:
                break
                
            print(f"  Página {page}: {len(rows)} filas | Nuevos encontrados: {len(all_rows)}")
            page += 1
        except Exception as e:
            print(f"  [ERROR] Página {page}: {e}")
            break

    df = pd.DataFrame(all_rows)
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


def scrape_miloto(n_sorteos: int = 300, existing_ids: set = None) -> pd.DataFrame:
    """
    Scrapea sorteos de Miloto de forma incremental.
    Se detiene inmediatamente si encuentra un Sorteo ID ya existente localmente.
    """
    if existing_ids is None:
        existing_ids = set()

    print(f"[SCRAPER] Miloto — buscando nuevos sorteos...")
    all_rows: list[dict] = []
    page = 1
    base_url = "https://www.baloto.com/miloto/resultados/"
    stop_scraping = False

    while len(all_rows) < n_sorteos and not stop_scraping:
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
                
            for r in rows:
                if r["Sorteo"] in existing_ids:
                    print(f"  -> Encontrado sorteo existente '{r['Sorteo']}'. Deteniendo scraping.")
                    stop_scraping = True
                    break
                all_rows.append(r)
                
            if stop_scraping:
                break
                
            print(f"  Página {page}: {len(rows)} filas | Nuevos encontrados: {len(all_rows)}")
            page += 1
        except Exception as e:
            print(f"  [ERROR] Página {page}: {e}")
            break

    df = pd.DataFrame(all_rows)
    return df



# ─────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────
def actualizar_datos(n_sorteos: int = 300) -> dict[str, pd.DataFrame]:
    """
    Actualiza (o crea) los archivos de datos con los últimos n_sorteos de forma incremental.
    Evita scrape-ar todo de nuevo leyendo los IDs ya guardados.
    """
    resultados = {}

    # --- BALOTO ---
    legacy_b = _seed_from_legacy(config.FILES["BALOTO"], config.BALOTO_LEGACY)
    
    # Extraemos los IDs de sorteos que ya tenemos guardados localmente
    existing_b_ids = set()
    if not legacy_b.empty and "Sorteo" in legacy_b.columns:
        existing_b_ids = set(legacy_b["Sorteo"].astype(str).tolist())
        
    fresh_b = scrape_baloto(n_sorteos, existing_ids=existing_b_ids)

    if not fresh_b.empty:
        # Combinar los nuevos resultados arriba de los existentes
        if not legacy_b.empty:
            combined = pd.concat([fresh_b, legacy_b], ignore_index=True)
            combined.drop_duplicates(subset=["Sorteo", "Tipo"], inplace=True)
        else:
            combined = fresh_b
        
        # Ordenamos sorteos descendente si el ID es numérico para asegurar orden
        try:
            combined["Sorteo_Int"] = combined["Sorteo"].astype(int)
            combined.sort_values(by="Sorteo_Int", ascending=False, inplace=True)
            combined.drop(columns=["Sorteo_Int"], inplace=True)
        except Exception:
            pass
            
        combined = combined.head(n_sorteos)
        safe_save(combined, config.FILES["BALOTO"])
        resultados["BALOTO"] = combined
        print(f"  [OK] Baloto actualizado: {len(fresh_b)} nuevos | Total: {len(combined)} registros")
    elif not legacy_b.empty:
        resultados["BALOTO"] = legacy_b
        print(f"  -> Baloto al dia (usando cache): {len(legacy_b)} registros")
    else:
        resultados["BALOTO"] = pd.DataFrame()
        print("  [ERROR] Sin datos Baloto")

    # --- MILOTO ---
    legacy_m = _seed_from_legacy(config.FILES["MILOTO"], config.MILOTO_LEGACY)
    
    existing_m_ids = set()
    if not legacy_m.empty and "Sorteo" in legacy_m.columns:
        existing_m_ids = set(legacy_m["Sorteo"].astype(str).tolist())
        
    fresh_m = scrape_miloto(n_sorteos, existing_ids=existing_m_ids)

    if not fresh_m.empty:
        if not legacy_m.empty:
            combined_m = pd.concat([fresh_m, legacy_m], ignore_index=True)
            combined_m.drop_duplicates(subset=["Sorteo"], inplace=True)
        else:
            combined_m = fresh_m
            
        try:
            combined_m["Sorteo_Int"] = combined_m["Sorteo"].astype(int)
            combined_m.sort_values(by="Sorteo_Int", ascending=False, inplace=True)
            combined_m.drop(columns=["Sorteo_Int"], inplace=True)
        except Exception:
            pass
            
        combined_m = combined_m.head(n_sorteos)
        safe_save(combined_m, config.FILES["MILOTO"])
        resultados["MILOTO"] = combined_m
        print(f"  [OK] Miloto actualizado: {len(fresh_m)} nuevos | Total: {len(combined_m)} registros")
    elif not legacy_m.empty:
        resultados["MILOTO"] = legacy_m
        print(f"  -> Miloto al dia (usando cache): {len(legacy_m)} registros")
    else:
        resultados["MILOTO"] = pd.DataFrame()
        print("  [ERROR] Sin datos Miloto")

    return resultados


if __name__ == "__main__":
    datos = actualizar_datos(300)
    for juego, df in datos.items():
        print(f"\n{juego}: {len(df)} registros")
        if not df.empty:
            print(df.head(3).to_string(index=False))
