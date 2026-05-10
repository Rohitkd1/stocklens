"""
StockLens – Flask Backend
Run locally:      python flask_app.py
Run production:   gunicorn flask_app:app --bind 0.0.0.0:8000 --workers 2
"""

import os
import math
import logging
import subprocess
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.resolve()
DATA_FILE   = os.environ.get("DATA_FILE", "Data set sheet.csv")
DATA_PATH   = BASE_DIR / DATA_FILE
STATIC_DIR  = BASE_DIR
GITHUB_REPO = os.environ.get("GITHUB_REPO", "https://github.com/Rohitkd1/stocklens")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")

# ─────────────────────────────────────────────
# Dataset cache
# ─────────────────────────────────────────────
_df: pd.DataFrame | None = None


def load_dataset() -> pd.DataFrame:
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
    df.columns = df.columns.str.strip()
    df["Date"] = df["Date"].str.replace("/", "-", regex=False).str.strip()
    df.dropna(how="all", inplace=True)
    logger.info("Dataset loaded: %d rows, %d columns", len(df), len(df.columns))
    _df = df
    return _df


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def clean_value(v):
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "nan", "NaN", "NaT", "#DIV/0!"):
        return None
    try:
        f = float(s)
        if math.isnan(f) or math.isinf(f):
            return None
        return int(f) if f == int(f) else f
    except (ValueError, OverflowError):
        return s


def row_to_dict(series: pd.Series) -> dict:
    return {col: clean_value(series[col]) for col in series.index}


def run_git(args: list[str]) -> tuple[int, str, str]:
    """Run a git command in BASE_DIR; returns (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["git"] + args,
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(str(STATIC_DIR), "index.html")


@app.route("/api/search")
def api_search():
    """GET /api/search?date=YYYY-MM-DD"""
    date_param = request.args.get("date", "").strip()
    if not date_param:
        return jsonify({"error": "Missing 'date' query parameter (YYYY-MM-DD)"}), 400
    try:
        df = load_dataset()
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 503
    match = df[df["Date"] == date_param]
    if match.empty:
        return jsonify({"found": False, "date": date_param}), 404
    return jsonify({"found": True, "date": date_param, "data": row_to_dict(match.iloc[0])})


@app.route("/api/dates")
def api_dates():
    """GET /api/dates — all available trading dates."""
    try:
        df = load_dataset()
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 503
    dates = sorted(df["Date"].dropna().unique().tolist())
    return jsonify({"count": len(dates), "dates": dates})


@app.route("/api/reload", methods=["POST"])
def api_reload():
    """POST /api/reload — flush in-memory cache and re-read file."""
    expected_token = os.environ.get("RELOAD_TOKEN", "")
    if expected_token:
        if request.headers.get("Authorization", "") != f"Bearer {expected_token}":
            return jsonify({"error": "Unauthorized"}), 401
    global _df
    _df = None
    try:
        df = load_dataset()
        return jsonify({"status": "reloaded", "rows": len(df), "columns": list(df.columns)})
    except Exception as e:
        logger.exception("Reload failed")
        return jsonify({"error": str(e)}), 500


@app.route("/api/git-status")
def api_git_status():
    """GET /api/git-status — current commit info for the UI."""
    _, branch, _ = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    _, commit, _ = run_git(["log", "-1", "--format=%h|%s|%ar"])
    _, remote, _ = run_git(["remote", "get-url", "origin"])
    parts = commit.split("|") if commit else ["", "", ""]
    return jsonify({
        "repo":    remote or GITHUB_REPO,
        "branch":  branch or "main",
        "hash":    parts[0],
        "message": parts[1],
        "when":    parts[2],
    })


@app.route("/api/upload", methods=["POST"])
def api_upload():
    """
    POST /api/upload  (multipart/form-data, field: 'dataset', optional: 'commit_msg')
    Steps:
      1. Validate file type (.csv / .xlsx)
      2. Validate required columns exist
      3. Save file → overwrite DATA_FILE on disk
      4. git add → git commit → git push
      5. Reload in-memory DataFrame cache
    """
    if "dataset" not in request.files:
        return jsonify({"error": "No file field named 'dataset' in request."}), 400

    file = request.files["dataset"]
    if not file.filename:
        return jsonify({"error": "Empty filename."}), 400

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".csv", ".xlsx", ".xls"):
        return jsonify({"error": f"Unsupported file type '{suffix}'. Use .csv or .xlsx"}), 400

    # Save to temp path, validate, then atomically replace
    tmp_path = BASE_DIR / f"_upload_tmp{suffix}"
    try:
        file.save(str(tmp_path))

        if suffix == ".csv":
            df_new = pd.read_csv(tmp_path, dtype=str)
        else:
            df_new = pd.read_excel(tmp_path, dtype=str, engine="openpyxl")

        df_new.columns = df_new.columns.str.strip()
        required = ["Date", "Open", "High", "Low", "Close", "Volume"]
        missing = [c for c in required if c not in df_new.columns]
        if missing:
            tmp_path.unlink(missing_ok=True)
            return jsonify({"error": f"Missing required columns: {missing}"}), 422

        row_count = len(df_new)
        date_min  = df_new["Date"].min()
        date_max  = df_new["Date"].max()

        # Overwrite the live dataset (always uses the configured DATA_FILE name)
        tmp_path.rename(DATA_PATH)
        logger.info("Dataset replaced: %d rows (%s → %s)", row_count, date_min, date_max)

    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        logger.exception("Upload validation failed")
        return jsonify({"error": f"Validation error: {e}"}), 500

    # Git operations
    git_log = []

    code, out, err = run_git(["add", DATA_FILE])
    git_log.append(f"git add: {'OK' if code == 0 else err}")

    commit_msg = (request.form.get("commit_msg") or "").strip()
    if not commit_msg:
        commit_msg = f"data: upload {file.filename} ({row_count} rows)"

    code, out, err = run_git(["commit", "-m", commit_msg])
    commit_out = out or err
    if code != 0 and "nothing to commit" not in commit_out:
        git_log.append(f"git commit FAILED: {err}")
        return jsonify({"error": "Git commit failed", "detail": err, "git_log": git_log}), 500
    git_log.append(f"git commit: {commit_out[:120]}")

    code, out, err = run_git(["push"])
    if code == 0:
        git_log.append(f"git push: OK")
    else:
        git_log.append(f"git push: FAILED — {err}")
        logger.error("git push failed: %s", err)

    # Reload cache
    global _df
    _df = None
    try:
        df_live = load_dataset()
    except Exception as e:
        return jsonify({"error": f"Saved & pushed but cache reload failed: {e}"}), 500

    return jsonify({
        "status":     "success",
        "filename":   file.filename,
        "rows":       len(df_live),
        "date_range": f"{date_min} → {date_max}",
        "git_log":    git_log,
        "repo":       GITHUB_REPO,
        "push_ok":    code == 0,
    })


@app.route("/health")
def health():
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
