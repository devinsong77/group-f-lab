"""Tests for Comparator engine + Compare/MarketData APIs."""

import io
import os
import sys
import time
import tempfile
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from parser import ReportParser
from comparator import ReportComparator
from stock_data import StockDataService
from storage import Storage


@pytest.fixture
def tmp_data_dir():
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def app(tmp_data_dir):
    app = create_app(data_dir=tmp_data_dir, test_mode=True)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _make_pdf_bytes():
    return (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R"
        b"/Contents 4 0 R>>endobj\n"
        b"4 0 obj<</Length 44>>stream\nBT /F1 12 Tf 100 700 Td "
        b"(Test Report) Tj ET\nendstream\nendobj\n"
        b"xref\n0 5\n0000000000 65535 f \n"
        b"0000000009 00000 n \n0000000058 00000 n \n"
        b"0000000115 00000 n \n0000000210 00000 n \n"
        b"trailer<</Size 5/Root 1 0 R>>\nstartxref\n306\n%%EOF"
    )


MOCK_PARSED_1 = {
    "title": "贵州茅台深度研究报告",
    "rating": "买入",
    "target_price": 2100.00,
    "key_points": "公司业绩稳健增长，高端白酒需求旺盛",
    "stock_code": "600519",
    "stock_name": "贵州茅台",
    "industry": "白酒",
    "raw_text": "text1",
    "parse_time_ms": 500,
}

MOCK_PARSED_2 = {
    "title": "贵州茅台跟踪报告",
    "rating": "增持",
    "target_price": 1980.00,
    "key_points": "短期估值偏高，长期看好",
    "stock_code": "600519",
    "stock_name": "贵州茅台",
    "industry": "白酒",
    "raw_text": "text2",
    "parse_time_ms": 300,
}

MOCK_PARSED_DIFF = {
    "title": "平安银行研究报告",
    "rating": "中性",
    "target_price": 15.00,
    "key_points": "银行业务稳定",
    "stock_code": "000001",
    "stock_name": "平安银行",
    "industry": "银行",
    "raw_text": "text3",
    "parse_time_ms": 200,
}


def _seed_reports(client, mocks=None):
    if mocks is None:
        mocks = [MOCK_PARSED_1, MOCK_PARSED_2]
    rids = []
    for m in mocks:
        data = {"file": (io.BytesIO(_make_pdf_bytes()), "r.pdf")}
        resp = client.post("/api/v1/reports/upload", data=data, content_type="multipart/form-data")
        rid = resp.get_json()["report_id"]
        with patch.object(ReportParser, "process", return_value=m):
            client.post(f"/api/v1/reports/{rid}/parse")
        rids.append(rid)
    return rids


# ── Unit Tests: Comparator ───────────────────────────────────

class TestComparatorUnit:
    """TC-COMP-001 ~ TC-COMP-004"""

    def test_validate_min_reports(self, tmp_data_dir):
        """TC-COMP-001: less than 2 report_ids → error."""
        s = Storage(data_dir=tmp_data_dir)
        c = ReportComparator(storage=s)
        ok, code = c.validate(["r1"])
        assert not ok
        assert code == "COMPARE_MIN_REPORTS"

    def test_validate_diff_stock(self, tmp_data_dir):
        """TC-COMP-002: different stock_codes → error."""
        s = Storage(data_dir=tmp_data_dir)
        s.save_report("r1", "a.pdf", "/tmp/a.pdf")
        s.save_parsed_report("r1", {
            "title": "A", "rating": "买入", "target_price": 100,
            "key_points": "kp", "stock_code": "600519",
            "stock_name": "茅台", "industry": "白酒",
            "raw_text": "t", "parse_time_ms": 1,
        })
        s.save_report("r2", "b.pdf", "/tmp/b.pdf")
        s.save_parsed_report("r2", {
            "title": "B", "rating": "中性", "target_price": 15,
            "key_points": "kp2", "stock_code": "000001",
            "stock_name": "平安银行", "industry": "银行",
            "raw_text": "t", "parse_time_ms": 1,
        })
        c = ReportComparator(storage=s)
        ok, code = c.validate(["r1", "r2"])
        assert not ok
        assert code == "COMPARE_DIFF_STOCK"

    def test_compare_fields_rating_diff(self, tmp_data_dir):
        """TC-COMP-003: detects rating and target_price differences."""
        s = Storage(data_dir=tmp_data_dir)
        c = ReportComparator(storage=s)
        parsed = [
            {"report_id": "r1", "rating": "买入", "target_price": 2100.0, "key_points": "kp1"},
            {"report_id": "r2", "rating": "增持", "target_price": 1980.0, "key_points": "kp2"},
        ]
        diffs = c._compare_fields(parsed)
        fields = [d["field"] for d in diffs]
        assert "rating" in fields
        assert "target_price" in fields

    def test_build_reports_summary(self, tmp_data_dir):
        """TC-COMP-004: builds correct summary."""
        s = Storage(data_dir=tmp_data_dir)
        c = ReportComparator(storage=s)
        parsed = [
            {"report_id": "r1", "title": "T1", "rating": "买入", "target_price": 100, "key_points": "kp1"},
        ]
        summary = c._build_reports_summary(parsed)
        assert len(summary) == 1
        assert summary[0]["title"] == "T1"


# ── Unit Tests: StockDataService ─────────────────────────────

class TestStockDataUnit:
    """TC-STOCK-001 ~ TC-STOCK-002"""

    def test_cache_hit(self):
        """TC-STOCK-001: cache hit returns source=cache."""
        svc = StockDataService(cache_ttl=300)
        svc._cache["600519"] = {
            "data": {
                "stock_code": "600519", "stock_name": "贵州茅台",
                "pe": 35.2, "pb": 12.8, "market_cap": 26000.0,
                "latest_price": 1850.0, "data_time": "2026-04-15T15:00:00Z",
                "source": "akshare",
            },
            "timestamp": time.time(),
        }
        result = svc.get_market_data("600519")
        assert result["source"] == "cache"
        assert result["pe"] == 35.2

    @patch.object(StockDataService, "_fetch_from_eastmoney", return_value=None)
    @patch.object(StockDataService, "_fetch_from_tencent", return_value=None)
    def test_unavailable_degradation(self, mock_tencent, mock_em):
        """TC-STOCK-002: all sources fail → source=unavailable."""
        svc = StockDataService(cache_ttl=300)
        result = svc.get_market_data("600519")
        assert result["source"] == "unavailable"
        assert result["pe"] is None


# ── Integration Tests: Compare API ───────────────────────────

class TestCompareAPI:
    """TC-M02-030 ~ TC-M02-035"""

    def test_compare_success(self, client):
        """TC-M02-030: POST /reports/compare 2 same-stock → 200."""
        rids = _seed_reports(client)
        resp = client.post("/api/v1/reports/compare", json={"report_ids": rids})
        assert resp.status_code == 200

    def test_compare_has_similarities(self, client):
        """TC-M02-031: response contains similarities array."""
        rids = _seed_reports(client)
        resp = client.post("/api/v1/reports/compare", json={"report_ids": rids})
        body = resp.get_json()
        assert "similarities" in body
        assert isinstance(body["similarities"], list)

    def test_compare_has_differences(self, client):
        """TC-M02-032: response contains differences array."""
        rids = _seed_reports(client)
        resp = client.post("/api/v1/reports/compare", json={"report_ids": rids})
        body = resp.get_json()
        assert "differences" in body
        assert isinstance(body["differences"], list)

    def test_compare_reports_summary(self, client):
        """TC-M02-033: reports_summary has core fields."""
        rids = _seed_reports(client)
        resp = client.post("/api/v1/reports/compare", json={"report_ids": rids})
        body = resp.get_json()
        assert "reports_summary" in body
        for s in body["reports_summary"]:
            assert "report_id" in s
            assert "title" in s

    def test_compare_min_reports(self, client):
        """TC-M02-034: < 2 report_ids → 400 COMPARE_MIN_REPORTS."""
        resp = client.post("/api/v1/reports/compare", json={"report_ids": ["r1"]})
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "COMPARE_MIN_REPORTS"

    def test_compare_diff_stock(self, client):
        """TC-M02-035: different stock reports → 400 COMPARE_DIFF_STOCK."""
        rids = _seed_reports(client, mocks=[MOCK_PARSED_1, MOCK_PARSED_DIFF])
        resp = client.post("/api/v1/reports/compare", json={"report_ids": rids})
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "COMPARE_DIFF_STOCK"


# ── Integration Tests: Market Data ───────────────────────────

class TestMarketDataAPI:
    """TC-M02-060 ~ TC-M02-063"""

    @patch.object(StockDataService, "_fetch_from_tencent", return_value={
        "stock_code": "600519", "stock_name": "", "pe": 35.2,
        "pb": 12.8, "market_cap": 26000.0, "latest_price": 1850.0,
        "data_time": "2026-04-15T15:00:00Z",
    })
    def test_market_data_success(self, mock_fetch, client):
        """TC-M02-060: GET /stocks/{code}/market-data → 200."""
        resp = client.get("/api/v1/stocks/600519/market-data")
        assert resp.status_code == 200
        body = resp.get_json()
        assert "pe" in body
        assert "pb" in body
        assert "market_cap" in body

    @patch.object(StockDataService, "_fetch_from_tencent", return_value={
        "stock_code": "600519", "stock_name": "", "pe": 35.2,
        "pb": 12.8, "market_cap": 26000.0, "latest_price": 1850.0,
        "data_time": "2026-04-15T15:00:00Z",
    })
    def test_market_data_source(self, mock_fetch, client):
        """TC-M02-061: source is tencent or cache."""
        resp = client.get("/api/v1/stocks/600519/market-data")
        body = resp.get_json()
        assert body["source"] in ("tencent", "eastmoney", "cache")

    @patch.object(StockDataService, "_fetch_from_eastmoney", return_value=None)
    @patch.object(StockDataService, "_fetch_from_tencent", return_value=None)
    def test_market_data_unavailable(self, mock_tencent, mock_em, client):
        """TC-M02-062: all sources down → source=unavailable, nulls."""
        resp = client.get("/api/v1/stocks/600519/market-data")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["source"] == "unavailable"
        assert body["pe"] is None

    @patch.object(StockDataService, "_fetch_from_eastmoney", return_value=None)
    @patch.object(StockDataService, "_fetch_from_tencent", return_value=None)
    def test_market_data_unknown_stock(self, mock_tencent, mock_em, client):
        """TC-M02-063: unknown stock degrades gracefully."""
        resp = client.get("/api/v1/stocks/999999/market-data")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["source"] == "unavailable"
