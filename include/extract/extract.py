"""Extractor de REE y Open-Meteo -> JSON crudo en data/raw (capa bronze)."""
import argparse
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

REE_URL = "https://apidatos.ree.es/es/datos/{category}/{widget}"
REE_ENDPOINTS = {
    "ree_demanda": ("demanda", "evolucion"),
    "ree_generacion": ("generacion", "estructura-generacion"),
}

METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
METEO_DAILY = "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum"
CIUDADES = {
    "madrid": (40.4168, -3.7038),
    "barcelona": (41.3874, 2.1686),
    "valencia": (39.4699, -0.3763),
    "sevilla": (37.3891, -5.9845),
    "bilbao": (43.2630, -2.9350),
}


def month_chunks(start: date, end: date):
    """Divide el rango en meses: un fichero por mes y fuente."""
    cur = start
    while cur <= end:
        next_month = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
        yield cur, min(next_month - timedelta(days=1), end)
        cur = next_month


def get_json(url: str, params: dict) -> dict:
    """GET con reintentos y backoff exponencial."""
    for intento in range(3):
        r = requests.get(url, params=params, timeout=30)
        if r.status_code == 200:
            return r.json()
        print(f"  ! HTTP {r.status_code}, reintento {intento + 1}/3")
        time.sleep(2 ** intento)
    r.raise_for_status()


def save(source: str, name: str, payload) -> None:
    path = RAW_DIR / source / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    wrapped = {
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "payload": payload,
    }
    path.write_text(json.dumps(wrapped, ensure_ascii=False))
    print(f"  ✓ {path.relative_to(RAW_DIR.parent.parent)}")


def extract_ree(start: date, end: date) -> None:
    for source, (category, widget) in REE_ENDPOINTS.items():
        for s, e in month_chunks(start, end):
            data = get_json(
                REE_URL.format(category=category, widget=widget),
                {"start_date": f"{s}T00:00", "end_date": f"{e}T23:59", "time_trunc": "day"},
            )
            save(source, f"{s:%Y-%m}", data)


def extract_meteo(start: date, end: date) -> None:
    for s, e in month_chunks(start, end):
        resultados = []
        for ciudad, (lat, lon) in CIUDADES.items():
            data = get_json(METEO_URL, {
                "latitude": lat, "longitude": lon,
                "start_date": str(s), "end_date": str(e),
                "daily": METEO_DAILY, "timezone": "Europe/Madrid",
            })
            data["ciudad"] = ciudad
            resultados.append(data)
        save("meteo_diario", f"{s:%Y-%m}", resultados)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--start", type=date.fromisoformat, required=True)
    p.add_argument("--end", type=date.fromisoformat, required=True)
    p.add_argument("--fuente", choices=["all", "ree", "meteo"], default="all")
    a = p.parse_args()

    if a.fuente in ("all", "ree"):
        print("REE:"); extract_ree(a.start, a.end)
    if a.fuente in ("all", "meteo"):
        print("Open-Meteo:"); extract_meteo(a.start, a.end)