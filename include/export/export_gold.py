"""Exporta todas las tablas del esquema gold a Parquet (capa de consumo)."""
import os
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DB = os.environ.get("DBT_DUCKDB_PATH", str(ROOT / "data" / "warehouse.duckdb"))
OUT = ROOT / "app" / "data"

OUT.mkdir(parents=True, exist_ok=True)
con = duckdb.connect(DB, read_only=True)
tablas = [r[0] for r in con.sql(
    "select table_name from information_schema.tables where table_schema = 'gold'"
).fetchall()]

for t in tablas:
    destino = OUT / f"{t}.parquet"
    con.sql(f"copy gold.{t} to '{destino}' (format parquet)")
    print(f"✓ {t} → {destino.relative_to(ROOT)}")
con.close()
