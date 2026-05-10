"""
tests/test_flask_app.py
=======================
Unit tests for the StockLens Flask API.
Run with:  pytest tests/ -v
"""

import sys
import os
import json
import tempfile
import textwrap
import pytest

# Allow importing flask_app from parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

SAMPLE_CSV = textwrap.dedent("""\
    Date,Open,High,Low,Close,Adj Close,Volume,RSI,Upper Bollinger band,Lower Bollinger band,%K (5 days stochastic oscillator),"%D Average(H,3)",EMA 12,EMA 26,Volume Weighted Average Price,William % R,Commodity Channel Index,Rate of Change (10 days),Aroon Up,Aroon Down,MACD,BUY/SELL
    2010/02/09,492.209351,494.314392,486.736237,491.9617,445.888885,6595770,77.36,538.55,482.72,24.86,14.72,507.07,526.11,525.68,-82.10,-133.34,-0.046,32,88,-19.04,0
    2010/02/10,495.255463,495.255463,486.389526,487.924957,442.230225,8427562,77.45,534.37,480.36,16.03,18.96,504.12,523.28,524.85,-89.47,-126.80,-0.041,28,84,-19.15,-1
    2010/02/11,489.980469,505.11203,489.609009,502.808868,455.720215,10822218,73.80,529.70,482.28,89.62,21.56,503.92,521.76,524.11,-50.64,-81.14,-0.021,24,80,-17.84,1
""")


@pytest.fixture(scope="module")
def csv_file():
    """Create a temporary CSV file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv",
                                     delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_CSV)
        return f.name


@pytest.fixture(scope="module")
def client(csv_file):
    """Create a Flask test client pointing at the temp CSV."""
    os.environ["DATA_FILE"] = csv_file

    import importlib
    import flask_app as fa
    importlib.reload(fa)          # reload with new DATA_FILE env var
    fa._df = None                 # clear any cached dataframe

    fa.app.config["TESTING"] = True
    with fa.app.test_client() as c:
        yield c

    # cleanup
    os.unlink(csv_file)
    del os.environ["DATA_FILE"]


# ─────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────

class TestHealthEndpoint:
    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["status"] == "ok"
        assert body["rows"] == 3


class TestSearchEndpoint:
    def test_missing_date_param(self, client):
        r = client.get("/api/search")
        assert r.status_code == 400
        body = json.loads(r.data)
        assert "error" in body

    def test_date_not_found(self, client):
        r = client.get("/api/search?date=1999-01-01")
        assert r.status_code == 404
        body = json.loads(r.data)
        assert body["found"] is False

    def test_valid_date_returns_data(self, client):
        r = client.get("/api/search?date=2010-02-09")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["found"] is True
        assert "data" in body
        data = body["data"]
        assert data["Date"] == "2010-02-09"
        assert data["Open"]  is not None
        assert data["Close"] is not None
        assert data["Volume"] is not None

    def test_buy_sell_signal_present(self, client):
        r = client.get("/api/search?date=2010-02-11")
        body = json.loads(r.data)
        assert body["found"] is True
        assert body["data"]["BUY/SELL"] == 1   # '1' for BUY

    def test_slash_date_format_also_works(self, client):
        """The API accepts ISO dates; the dataset uses slashes internally."""
        r = client.get("/api/search?date=2010-02-10")
        assert r.status_code == 200


class TestDatesEndpoint:
    def test_returns_all_dates(self, client):
        r = client.get("/api/dates")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["count"] == 3
        assert "2010-02-09" in body["dates"]
        assert "2010-02-11" in body["dates"]

    def test_dates_are_sorted(self, client):
        r = client.get("/api/dates")
        body = json.loads(r.data)
        dates = body["dates"]
        assert dates == sorted(dates)


class TestStaticFrontend:
    def test_index_served(self, client):
        r = client.get("/")
        assert r.status_code == 200
