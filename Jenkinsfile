pipeline {
    agent any

    triggers {
        pollSCM('* * * * *')
    }

    environment {
        DATA_FILE      = "Data set sheet.csv"
        VENV_DIR       = "${WORKSPACE}\\.venv"
        PYTHON         = "python"
    }

    stages {

        // ── Stage 1: Checkout ─────────────────────────────────
        stage('Checkout') {
            steps {
                echo "Checking out source from Git..."
                checkout scm
            }
        }

        // ── Stage 2: Detect changed files ────────────────────
        stage('Detect Changes') {
            steps {
                script {
                    def changedFiles = bat(
                        script: "git diff --name-only HEAD~1 HEAD 2>nul || echo all",
                        returnStdout: true
                    ).trim()
                    echo "Changed files: ${changedFiles}"
                    env.DATASET_CHANGED = (
                        changedFiles.contains("Data set sheet") ||
                        changedFiles.contains(".csv")           ||
                        changedFiles.contains(".xlsx")          ||
                        changedFiles == 'all'
                    ) ? 'true' : 'false'
                    echo "Dataset changed: ${env.DATASET_CHANGED}"
                }
            }
        }

        // ── Stage 3: Python environment setup ────────────────
        stage('Setup Python Env') {
            steps {
                echo "Setting up Python virtual environment..."
                bat """
                    if not exist .venv (
                        ${PYTHON} -m venv .venv
                    )
                    .venv\\Scripts\\pip install --upgrade pip --quiet
                    .venv\\Scripts\\pip install -r requirements.txt --quiet
                """
            }
        }

        // ── Stage 4: Validate dataset ─────────────────────────
        stage('Validate Dataset') {
            steps {
                echo "Validating dataset with pandas..."
                bat """
                    .venv\\Scripts\\python -c "
import pandas as pd, sys
from pathlib import Path
path = Path('${DATA_FILE}')
if not path.exists():
    print('ERROR: Dataset not found:', path); sys.exit(1)
df = pd.read_csv(path, dtype=str) if path.suffix.lower()=='.csv' else pd.read_excel(path, dtype=str, engine='openpyxl')
df.columns = df.columns.str.strip()
missing = [c for c in ['Date','Open','High','Low','Close','Volume'] if c not in df.columns]
if missing: print('ERROR: Missing columns:', missing); sys.exit(1)
print('Dataset OK:', len(df), 'rows,', len(df.columns), 'columns')
print('Date range:', df['Date'].min(), '->', df['Date'].max())
"
                """
            }
        }

        // ── Stage 5: Run tests ────────────────────────────────
        stage('Run Tests') {
            steps {
                echo "Running unit tests..."
                bat """
                    if exist tests (
                        .venv\\Scripts\\pytest tests\\ -v --tb=short
                    ) else (
                        echo No tests directory found, skipping.
                    )
                """
            }
        }

        // ── Stage 6: Reload Flask (Windows) ───────────────────
        stage('Reload Flask App') {
            steps {
                echo "Reloading Flask app with updated dataset..."
                bat """
                    @echo off
                    REM Kill any running Flask/Python process on port 5000
                    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5000 ^| findstr LISTENING') do (
                        taskkill /F /PID %%a 2>nul
                        echo Killed process %%a on port 5000
                    )
                    timeout /t 2 /nobreak >nul

                    REM Start Flask in background using pythonw (no console window)
                    start /B .venv\\Scripts\\python flask_app.py > flask.log 2>&1
                    echo Flask app restarted. Waiting for startup...
                    timeout /t 4 /nobreak >nul
                """
            }
        }

        // ── Stage 7: Health check ─────────────────────────────
        stage('Health Check') {
            steps {
                echo "Running health check on Flask app..."
                bat """
                    @echo off
                    powershell -Command "try { $r = Invoke-WebRequest -Uri http://localhost:5000/health -UseBasicParsing -TimeoutSec 10; if ($r.StatusCode -eq 200) { Write-Host 'Health check PASSED (HTTP 200)'; exit 0 } else { Write-Host 'Health check FAILED (HTTP ' + $r.StatusCode + ')'; exit 1 } } catch { Write-Host 'Health check FAILED: ' + $_.Exception.Message; exit 1 }"
                """
            }
        }
    }

    post {
        success {
            echo "Pipeline PASSED — StockLens is live with the updated dataset!"
        }
        failure {
            echo "Pipeline FAILED — check the stage logs above."
        }
        always {
            cleanWs()
        }
    }
}
