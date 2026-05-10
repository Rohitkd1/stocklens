pipeline {
    agent any

    triggers {
        pollSCM('* * * * *')
    }

    environment {
        DATA_FILE = "Data set sheet.csv"
        IS_UNIX   = "${isUnix()}"
    }

    stages {

        stage('Checkout') {
            steps {
                echo "Checking out source from Git..."
                checkout scm
            }
        }

        stage('Detect Changes') {
            steps {
                script {
                    def changedFiles = ''
                    try {
                        if (isUnix()) {
                            changedFiles = sh(script: "git diff --name-only HEAD~1 HEAD 2>/dev/null || echo 'all'", returnStdout: true).trim()
                        } else {
                            changedFiles = bat(script: "git diff --name-only HEAD~1 HEAD 2>nul || echo all", returnStdout: true).trim()
                        }
                    } catch (e) {
                        changedFiles = 'all'
                    }
                    echo "Changed files: ${changedFiles}"
                    env.DATASET_CHANGED = (
                        changedFiles.contains("Data set sheet") ||
                        changedFiles.contains(".csv")           ||
                        changedFiles.contains(".xlsx")          ||
                        changedFiles.contains("all")
                    ) ? 'true' : 'false'
                    echo "Dataset changed: ${env.DATASET_CHANGED}"
                }
            }
        }

        stage('Setup Python Env') {
            steps {
                echo "Setting up Python virtual environment..."
                script {
                    if (isUnix()) {
                        sh """
                            # Install python3-venv if missing (Debian/Ubuntu Jenkins containers)
                            if ! python3 -m venv --help > /dev/null 2>&1; then
                                apt-get update -qq && apt-get install -y -qq python3-venv python3-pip
                            fi

                            # Create venv only if it doesn't exist
                            if [ ! -d ".venv" ]; then
                                python3 -m venv .venv
                            fi

                            .venv/bin/pip install --upgrade pip --quiet
                            .venv/bin/pip install -r requirements.txt --quiet
                        """
                    } else {
                        bat """
                            if not exist .venv python -m venv .venv
                            .venv\\Scripts\\pip install --upgrade pip --quiet
                            .venv\\Scripts\\pip install -r requirements.txt --quiet
                        """
                    }
                }
            }
        }

        stage('Validate Dataset') {
            steps {
                echo "Validating dataset with pandas..."
                script {
                    def pyCmd = """
import pandas as pd, sys
from pathlib import Path
path = Path('Data set sheet.csv')
if not path.exists(): print('ERROR: file not found'); sys.exit(1)
df = pd.read_csv(path, dtype=str) if path.suffix.lower()=='.csv' else pd.read_excel(path, dtype=str, engine='openpyxl')
df.columns = df.columns.str.strip()
missing = [c for c in ['Date','Open','High','Low','Close','Volume'] if c not in df.columns]
if missing: print('ERROR missing cols:', missing); sys.exit(1)
print('Dataset OK:', len(df), 'rows | Date range:', df['Date'].min(), '->', df['Date'].max())
"""
                    if (isUnix()) {
                        sh ".venv/bin/python -c \"${pyCmd.replaceAll('"', '\\\\"')}\""
                    } else {
                        bat ".venv\\Scripts\\python -c \"${pyCmd.replaceAll('"', '\\"')}\""
                    }
                }
            }
        }

        stage('Run Tests') {
            steps {
                echo "Running unit tests..."
                script {
                    if (isUnix()) {
                        sh """
                            if [ -d tests ]; then
                                .venv/bin/pytest tests/ -v --tb=short
                            else
                                echo 'No tests directory, skipping.'
                            fi
                        """
                    } else {
                        bat """
                            if exist tests (
                                .venv\\Scripts\\pytest tests\\ -v --tb=short
                            ) else (
                                echo No tests directory, skipping.
                            )
                        """
                    }
                }
            }
        }

        stage('Reload Flask App') {
            steps {
                echo "Reloading Flask app with updated dataset..."
                script {
                    if (isUnix()) {
                        sh """
                            # Kill any Flask process on port 5000
                            fuser -k 5000/tcp 2>/dev/null || true
                            sleep 2
                            # Restart Flask in background
                            nohup .venv/bin/python flask_app.py > flask.log 2>&1 &
                            sleep 4
                            echo "Flask restarted. PID: \$(pgrep -f flask_app.py)"
                        """
                    } else {
                        bat """
                            @echo off
                            for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5000 ^| findstr LISTENING 2^>nul') do (
                                taskkill /F /PID %%a >nul 2>nul
                            )
                            timeout /t 2 /nobreak >nul
                            start /B .venv\\Scripts\\python flask_app.py > flask.log 2>&1
                            timeout /t 4 /nobreak >nul
                            echo Flask restarted.
                        """
                    }
                }
            }
        }

        stage('Health Check') {
            steps {
                echo "Running health check on Flask app..."
                script {
                    if (isUnix()) {
                        sh """
                            STATUS=\$(curl -s -o /dev/null -w '%{http_code}' http://localhost:5000/health || echo 000)
                            if [ "\$STATUS" = "200" ]; then
                                echo "Health check PASSED (HTTP 200)"
                            else
                                echo "Health check FAILED (HTTP \$STATUS) — Flask may not be running yet"
                                exit 1
                            fi
                        """
                    } else {
                        bat """
                            powershell -Command "try { $r = Invoke-WebRequest -Uri http://localhost:5000/health -UseBasicParsing -TimeoutSec 10; Write-Host 'Health check PASSED HTTP' $r.StatusCode } catch { Write-Host 'Health check FAILED:' $_.Exception.Message; exit 1 }"
                        """
                    }
                }
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
