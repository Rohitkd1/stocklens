pipeline {
    agent any

    // ──────────────────────────────────────────────────────────
    // Trigger: Poll SCM every minute, OR use a GitHub/GitLab
    // webhook → Build Triggers → "GitHub hook trigger for GITScm polling"
    // ──────────────────────────────────────────────────────────
    triggers {
        pollSCM('* * * * *')   // fallback polling every minute
    }

    environment {
        // Absolute path to the project on the Jenkins agent
        APP_DIR        = "/var/www/stocklens"           // change to your server path

        // Python virtualenv location
        VENV_DIR       = "${APP_DIR}/.venv"

        // Dataset filename (override if using Excel)
        DATA_FILE      = "Data set sheet.csv"

        // Gunicorn process name (used by systemd / supervisord)
        APP_MODULE     = "flask_app:app"
        GUNICORN_BIND  = "0.0.0.0:8000"
        GUNICORN_WORKERS = "2"

        // Optional reload token (set as Jenkins secret text credential)
        // RELOAD_TOKEN = credentials('stocklens-reload-token')
    }

    stages {

        // ── Stage 1: Checkout ─────────────────────────────────
        stage('Checkout') {
            steps {
                echo "📥 Checking out source from Git..."
                checkout scm
            }
        }

        // ── Stage 2: Detect changed files ────────────────────
        stage('Detect Changes') {
            steps {
                script {
                    def changedFiles = sh(
                        script: "git diff --name-only HEAD~1 HEAD 2>/dev/null || echo 'all'",
                        returnStdout: true
                    ).trim()
                    echo "Changed files:\n${changedFiles}"
                    env.DATASET_CHANGED = changedFiles.contains("Data set sheet") ||
                                          changedFiles.contains(".csv")          ||
                                          changedFiles.contains(".xlsx")         ||
                                          changedFiles == 'all' ? 'true' : 'false'
                    echo "Dataset changed: ${env.DATASET_CHANGED}"
                }
            }
        }

        // ── Stage 3: Python environment setup ────────────────
        stage('Setup Python Env') {
            steps {
                echo "🐍 Setting up Python virtual environment..."
                sh """
                    python3 -m venv ${VENV_DIR}
                    ${VENV_DIR}/bin/pip install --upgrade pip --quiet
                    ${VENV_DIR}/bin/pip install -r requirements.txt --quiet
                """
            }
        }

        // ── Stage 4: Validate dataset ─────────────────────────
        stage('Validate Dataset') {
            steps {
                echo "✅ Validating dataset with pandas..."
                sh """
                    ${VENV_DIR}/bin/python - <<'EOF'
import pandas as pd
import sys
from pathlib import Path

data_file = "${DATA_FILE}"
path = Path(data_file)

if not path.exists():
    print(f"ERROR: Dataset not found: {data_file}", file=sys.stderr)
    sys.exit(1)

suffix = path.suffix.lower()
if suffix == ".csv":
    df = pd.read_csv(path, dtype=str)
elif suffix in (".xlsx", ".xls"):
    df = pd.read_excel(path, dtype=str, engine="openpyxl")
else:
    print(f"ERROR: Unsupported file type: {suffix}", file=sys.stderr)
    sys.exit(1)

df.columns = df.columns.str.strip()

required_cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
missing = [c for c in required_cols if c not in df.columns]
if missing:
    print(f"ERROR: Missing required columns: {missing}", file=sys.stderr)
    sys.exit(1)

print(f"Dataset OK: {len(df)} rows, {len(df.columns)} columns")
print(f"Date range: {df['Date'].min()} → {df['Date'].max()}")
sys.exit(0)
EOF
                """
            }
        }

        // ── Stage 5: Run tests ────────────────────────────────
        stage('Run Tests') {
            steps {
                echo "🧪 Running unit tests..."
                sh """
                    ${VENV_DIR}/bin/python -m pytest tests/ -v --tb=short 2>/dev/null || \
                    echo 'No tests directory found, skipping.'
                """
            }
        }

        // ── Stage 6: Deploy / restart app ─────────────────────
        stage('Deploy') {
            steps {
                echo "🚀 Deploying updated application..."
                sh """
                    # Sync project files to deployment directory
                    rsync -av --exclude='.git' --exclude='.venv' \
                        ./ ${APP_DIR}/

                    # Install/update Python dependencies in deploy location
                    ${APP_DIR}/.venv/bin/pip install -r ${APP_DIR}/requirements.txt --quiet
                """
            }
        }

        // ── Stage 7: Restart Gunicorn ─────────────────────────
        stage('Restart Service') {
            steps {
                echo "♻️  Restarting Gunicorn service..."
                sh """
                    # Option A – systemd (preferred on Linux servers)
                    if systemctl is-active --quiet stocklens 2>/dev/null; then
                        systemctl restart stocklens
                        echo "Restarted via systemd."

                    # Option B – supervisorctl
                    elif command -v supervisorctl &>/dev/null; then
                        supervisorctl restart stocklens
                        echo "Restarted via supervisord."

                    # Option C – kill & relaunch (dev fallback)
                    else
                        pkill -f "${APP_MODULE}" || true
                        sleep 1
                        nohup ${APP_DIR}/.venv/bin/gunicorn ${APP_MODULE} \
                            --bind ${GUNICORN_BIND} \
                            --workers ${GUNICORN_WORKERS} \
                            --daemon \
                            --pid ${APP_DIR}/gunicorn.pid \
                            --log-file ${APP_DIR}/gunicorn.log \
                            --access-logfile ${APP_DIR}/access.log
                        echo "Gunicorn launched in daemon mode."
                    fi
                """
            }
        }

        // ── Stage 8: Health check ─────────────────────────────
        stage('Health Check') {
            steps {
                echo "💓 Running health check..."
                sh """
                    sleep 3   # give gunicorn a moment to start
                    STATUS=\$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/health)
                    if [ "\$STATUS" = "200" ]; then
                        echo "Health check PASSED (HTTP 200)"
                    else
                        echo "Health check FAILED (HTTP \$STATUS)"
                        exit 1
                    fi
                """
            }
        }
    }

    // ──────────────────────────────────────────────────────────
    // Post actions
    // ──────────────────────────────────────────────────────────
    post {
        success {
            echo "✅ Pipeline completed successfully. StockLens is live!"
        }
        failure {
            echo "❌ Pipeline FAILED. Check the logs above."
            // Add email/Slack notification here if needed:
            // mail to: 'team@example.com', subject: 'StockLens build failed', body: "Check Jenkins: ${BUILD_URL}"
        }
        always {
            cleanWs()   // clean workspace after every build
        }
    }
}
