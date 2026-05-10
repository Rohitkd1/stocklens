"""
StockLens – Flask Backend
=========================
Serves the static frontend and exposes a REST API that
reads the stock dataset (CSV or Excel) using pandas.

Run locally:
    python flask_app.py

Run in production (gunicorn):
    gunicorn flask_app:app --bind 0.0.0.0:8000 --workers 2 --timeout 120
"""

import os
import math
import logging
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory, abort

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.resolve()
DATA_FILE  = os.environ.get("DATA_FILE", "Data set sheet.csv")   # override via env var
DATA_PATH  = BASE_DIR / DATA_FILE
STATIC_DIR = BASE_DIR                                             # index.html lives here

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# App factory
# ─────────────────────────────────────────────
app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")


# ─────────────────────────────────────────────
# Dataset loader – reloads from disk every restart
# ─────────────────────────────────────────────
_df: pd.DataFrame | None = None


def load_dataset() -> pd.DataFrame:
    """
    Load the stock dataset into a pandas DataFrame.
    Supports .csv and .xlsx / .xls files.
    The dataset is cached in memory; Jenkins restarts gunicorn
    to pick up a new file, which triggers a fresh load.
    """
    global _df
    if _df is not None:
        return _df

    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

    suffix = DATA_PATH.suffix.lower()
    logger.info("Loading dataset from: %s", DATA_PATH)

    if suffix == ".csv":
        df = pd.read_csv(DATA_PATH, dtype=str)
    elif suffix in (".xlsx", ".xls"):
        df = pd.read_excel(DATA_PATH, dtype=str, engine="openpyxl")
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    # Normalise column names (strip whitespace)
    df.columns = df.columns.str.strip()

    # Normalise the Date column → ISO format YYYY-MM-DD
    df["Date"] = df["Date"].str.replace("/", "-", regex=False).str.strip()

    # Drop completely empty rows
    df.dropna(how="all", inplace=True)

    logger.info("Dataset loaded: %d rows, %d columns", len(df), len(df.columns))
    _df = df
    return _df


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def clean_value(v):
    """Convert a raw pandas value to a JSON-safe Python type."""
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "nan", "NaN", "NaT", "#DIV/0!"):
        return None
    try:
        f = float(s)
        if math.isnan(f) or math.isinf(f):
            return None
        # Return int if the float is a whole number
        return int(f) if f == int(f) else f
    except (ValueError, OverflowError):
        return s


def row_to_dict(series: pd.Series) -> dict:
    return {col: clean_value(series[col]) for col in series.index}


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the frontend."""
    return send_from_directory(str(STATIC_DIR), "index.html")


@app.route("/api/search")
def api_search():
    """
    GET /api/search?date=YYYY-MM-DD

    Returns all columns for the matching trading date as JSON.
    """
    date_param = request.args.get("date", "").strip()
    if not date_param:
        return jsonify({"error": "Missing 'date' query parameter (YYYY-MM-DD)"}), 400

    try:
        df = load_dataset()
    except FileNotFoundError as e:
        logger.error(e)
        return jsonify({"error": str(e)}), 503

    match = df[df["Date"] == date_param]

    if match.empty:
        return jsonify({"found": False, "date": date_param}), 404

    row = match.iloc[0]
    return jsonify({"found": True, "date": date_param, "data": row_to_dict(row)})


@app.route("/api/dates")
def api_dates():
    """
    GET /api/dates
    Returns a sorted list of all available trading dates (for autocomplete / validation).
    """
    try:
        df = load_dataset()
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 503

    dates = sorted(df["Date"].dropna().unique().tolist())
    return jsonify({"count": len(dates), "dates": dates})


@app.route("/api/reload", methods=["POST"])
def api_reload():
    """
    POST /api/reload
    Forces the dataset to be re-read from disk (used by Jenkins webhook).
    Protected by an optional RELOAD_TOKEN env var.
    """
    expected_token = os.environ.get("RELOAD_TOKEN", "")
    if expected_token:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {expected_token}":
            return jsonify({"error": "Unauthorized"}), 401

    global _df
    _df = None  # clear cache
    try:
        df = load_dataset()
        return jsonify({
            "status": "reloaded",
            "rows": len(df),
            "columns": list(df.columns),
        })
    except Exception as e:
        logger.exception("Reload failed")
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    """Liveness probe for Jenkins / load balancers."""
    try:
        df = load_dataset()
        return jsonify({"status": "ok", "rows": len(df)})
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 503


# ─────────────────────────────────────────────
# Dev entry point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info("Starting StockLens dev server on port %d", port)
    app.run(host="0.0.0.0", port=port, debug=True)
