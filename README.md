# StockLens 📊

A full-stack stock market data explorer:
- **Python Flask** backend reads the dataset with **pandas** (CSV or Excel)
- **Gunicorn** production server
- **Jenkins** CI/CD pipeline auto-deploys whenever a new dataset is pushed to Git

---

## Project Structure

```
excelpipepline/
├── flask_app.py          ← Flask app & REST API
├── index.html            ← Frontend UI
├── app.js                ← Frontend logic (calls /api/search)
├── style.css             ← Premium dark UI styles
├── requirements.txt      ← Python dependencies
├── Jenkinsfile           ← Jenkins declarative pipeline
├── stocklens.service     ← systemd service unit (Linux deployment)
├── tests/
│   └── test_flask_app.py ← Pytest test suite
└── Data set sheet.csv    ← Dataset (CSV or .xlsx)
```

---

## Quick Start (Local Dev)

```bash
# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\activate           # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run Flask dev server
python flask_app.py
# → http://localhost:5000

# 4. Run tests
pytest tests/ -v
```

---

## Production (Gunicorn)

```bash
gunicorn flask_app:app \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --timeout 120 \
    --access-logfile access.log
```

### As a systemd service (Linux)

```bash
sudo cp stocklens.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable stocklens
sudo systemctl start stocklens
```

---

## REST API

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Serves the HTML frontend |
| `/api/search?date=YYYY-MM-DD` | GET | Returns all indicators for a trading date |
| `/api/dates` | GET | Returns all available trading dates |
| `/api/reload` | POST | Forces dataset reload from disk |
| `/health` | GET | Liveness check (used by Jenkins) |

### Example

```bash
curl http://localhost:5000/api/search?date=2010-02-09
```

```json
{
  "found": true,
  "date": "2010-02-09",
  "data": {
    "Date": "2010-02-09",
    "Open": 492.209351,
    "High": 494.314392,
    "Low": 486.736237,
    "Close": 491.9617,
    "RSI": 77.36,
    "MACD": -19.04,
    "BUY/SELL": 0,
    ...
  }
}
```

---

## Git + Jenkins CI/CD Setup

### 1. Push to GitHub

```bash
git init
git remote add origin https://github.com/<you>/stocklens.git
git add .
git commit -m "initial commit"
git push -u origin main
```

### 2. Jenkins Setup

1. **Install plugins**: Git, Pipeline, Workspace Cleanup
2. **Create a Pipeline job**:
   - *Definition*: `Pipeline script from SCM`
   - *SCM*: Git → your repo URL
   - *Script Path*: `Jenkinsfile`
3. **Configure webhook** (GitHub → Settings → Webhooks):
   ```
   Payload URL: http://<jenkins-host>:8080/github-webhook/
   Content type: application/json
   Events: Just the push event ✓
   ```
4. In Jenkins job → *Build Triggers* → ☑ **GitHub hook trigger for GITScm polling**

### 3. What happens on push

```
Git push (new CSV/Excel file)
    ↓
GitHub webhook → Jenkins
    ↓
[Checkout] → [Detect Changes] → [Setup Python Env]
    ↓
[Validate Dataset] → [Run Tests]
    ↓
[Deploy] → [Restart Gunicorn] → [Health Check]
    ↓
✅ New data live at http://your-server:8000
```

### 4. Switching to Excel

Just rename/replace the file and set the environment variable:

```bash
export DATA_FILE="Data set sheet.xlsx"
```

The Flask app auto-detects `.csv` vs `.xlsx` via the file extension.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATA_FILE` | `Data set sheet.csv` | Dataset filename |
| `PORT` | `5000` | Flask dev server port |
| `RELOAD_TOKEN` | *(empty)* | Secret token for `/api/reload` |

---

## Jenkins `Jenkinsfile` – Key Stages

| Stage | What it does |
|---|---|
| Checkout | Pulls latest code from Git |
| Detect Changes | Checks if the dataset file was updated |
| Setup Python Env | Creates/updates `.venv` with pip |
| Validate Dataset | Runs pandas to verify schema |
| Run Tests | `pytest tests/ -v` |
| Deploy | `rsync` files to `APP_DIR` |
| Restart Service | `systemctl restart stocklens` |
| Health Check | `curl /health` must return HTTP 200 |
