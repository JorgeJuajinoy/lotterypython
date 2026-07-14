import os
from pathlib import Path

# Cargar .env automaticamente
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# --- RUTAS BASE ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

# Crear carpetas si no existen
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# --- FUENTE DE DATOS HISTORICOS (proyecto existente) ---
# Si los .xlsx del proyecto machinelearning están disponibles, se usan como semilla inicial
BALOTO_LEGACY   = r"D:\Proyectos_Programacion\machineLearning\baloto\baloto.xlsx"
MILOTO_LEGACY   = r"D:\Proyectos_Programacion\machineLearning\baloto\miloto.xlsx"

# --- ARCHIVOS DE DATOS PROPIOS ---
FILES = {
    "BALOTO":  os.path.join(DATA_DIR, "baloto_300.xlsx"),
    "MILOTO":  os.path.join(DATA_DIR, "miloto_300.xlsx"),
}

SUGERENCIAS_FILE    = os.path.join(DATA_DIR, "sugerencias_historico.xlsx")
PESOS_FILE          = os.path.join(DATA_DIR, "pesos_metodos.json")

# --- REPORTES ---
REPORT_HTML         = os.path.join(REPORTS_DIR, "sugerencias_hoy.html")
INFORME_HTML        = os.path.join(REPORTS_DIR, "informe_loop.html")
INFORME_XLSX        = os.path.join(REPORTS_DIR, "informe_loop.xlsx")

# --- API KEY GEMINI ---
# Edita el archivo .env en esta misma carpeta para cambiar la key:
#   GOOGLE_API_KEY=tu_nueva_key_aqui
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

# --- REGLAS DE JUEGO ---
JUEGOS = {
    "BALOTO": {
        "n_nums": 5,
        "rango":  43,
        "extra":  {"nombre": "SuperBalota", "rango": 16},
        "tipo": "Baloto",
    },
    "REVANCHA": {
        "n_nums": 5,
        "rango":  43,
        "extra":  {"nombre": "SuperBalota", "rango": 16},
        "tipo": "Revancha",
        "data_key": "BALOTO",   # Comparte datos con Baloto
    },
    "MILOTO": {
        "n_nums": 5,
        "rango":  39,
        "extra":  None,
        "tipo": "Miloto",
    },
}

# --- LOOP CONFIG ---
OBJETIVO_ACIERTO   = 0.90   # 90%
MAX_ITERACIONES    = 10
N_SUGERENCIAS      = 2      # Máximo jugadas por juego

# Definición de acierto mínimo para contar como "hit":
# Se considera acierto si la jugada tiene >= ACIERTO_MIN_NUMS coincidencias con el resultado real
ACIERTO_MIN_NUMS   = 2
