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
                            # Create venv WITHOUT pip (works even without ensurepip — no root needed)
                            if [ ! -d ".venv" ]; then
                                python3 -m venv .venv --without-pip
                            fi

                            # Bootstrap pip inside the venv using get-pip.py (no sudo required)
                            if [ ! -f ".venv/bin/pip" ]; then
                                echo "Bootstrapping pip via get-pip.py..."
                                curl -s https://bootstrap.pypa.io/get-pip.py -o get-pip.py
                                .venv/bin/python3 get-pip.py --quiet
                                rm -f get-pip.py
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
                echo "Signalling Flask to reload dataset from disk..."
                script {
                    if (isUnix()) {
                        sh """
                            # POST to /api/reload — flushes the in-memory DataFrame cache
                            # Flask re-reads the CSV/Excel file immediately, no restart needed
                            RESPONSE=\$(curl -s -o /dev/null -w '%{http_code}' \
                                -X POST http://localhost:5000/api/reload 2>/dev/null || echo "000")

                            if [ "\$RESPONSE" = "200" ]; then
                                echo "Flask cache reloaded successfully (HTTP 200)"
                            elif [ "\$RESPONSE" = "000" ]; then
                                echo "Flask not reachable — skipping reload (not running on this host)"
                            else
                                echo "Reload returned HTTP \$RESPONSE — check Flask logs"
                            fi
                        """
                    } else {
                        bat """
                            powershell -Command "try { $r = Invoke-WebRequest -Uri http://localhost:5000/api/reload -Method POST -UseBasicParsing -TimeoutSec 5; Write-Host 'Flask cache reloaded (HTTP' $r.StatusCode ')' } catch { Write-Host 'Flask not reachable on this host — skipping reload' }"
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
