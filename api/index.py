from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent.parent
FORMULA_FILE = BASE_DIR / "data_formulas.csv"

app = FastAPI(title="EN-supporter API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/formulas")
def formulas() -> list[dict]:
    df = pd.read_csv(FORMULA_FILE)
    numeric_cols = ["kcal_per_ml", "protein_g_per_100ml", "fiber_g_per_100ml", "osmolality_mOsmL"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.fillna("").to_dict(orient="records")
