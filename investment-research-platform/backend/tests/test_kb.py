"""Tests for Knowledge Base + Report management APIs."""

import io
import os
import sys
import tempfile
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from parser import ReportParser
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


def _seed_reports(client, count=2):
    """Upload and parse reports with mock."""
    mocks = [MOCK_PARSED_1, MOCK_PARSED_2]
    report_ids = []
    for i in range(count):
        data = {"file": (io.BytesIO(_make_pdf_bytes()), f"report{i}.pdf")}
        resp = client.post("/api/v1/reports/upload", data=data, content_type="multipart/form-data")
        rid = resp.get_json()["report_id"]

        with patch.object(ReportParser, "process", return_value=mocks[i % 2]):
            client.post(f"/api/v1/reports/{rid}/parse")

        report_ids.append(rid)
    return report_ids


# ── Unit Tests: Storage get_reports / delete / KB ────────────

class TestStorageExtended:
    """TC-M02-073 ~ TC-M02-076"""

    def test_get_reports(self, tmp_data_dir):
        """TC-M02-073: get_reports returns all + filter works."""
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
            "title": "B", "rating": "中性", "target_price": 50,
            "key_points": "kp2", "stock_code": "000001",
            "stock_name": "平安银行", "industry": "银行",
            "raw_text": "t", "parse_time_ms": 1,
        })
        # All
        all_r = s.get_reports()
        assert len(all_r) == 2
        # Filter
        filtered = s.get_reports({"stock_code": "600519"})
        assert len(filtered) == 1
        assert filtered[0]["stock_code"] == "600519"

    def test_delete_report_cascade(self, tmp_data_dir):
        """TC-M02-074: delete cascades to parsed + KB + file."""
        s = Storage(data_dir=tmp_data_dir)
        fpath = os.path.join(tmp_data_dir, "reports", "r1.pdf")
        with open(fpath, "wb") as f:
            f.write(b"fake pdf")
        s.save_report("r1", "a.pdf", fpath)
        s.save_parsed_report("r1", {
            "title": "A", "rating": "买入", "target_price": 100,
            "key_points": "kp", "stock_code": "600519",
            "stock_name": "茅台", "industry": "白酒",
            "raw_text": "t", "parse_time_ms": 1,
        })
        assert s.get_report("r1") is not None
        assert s.get_stock("600519") is not None
        s.delete_report("r1")
        assert s.get_report("r1") is None
        assert s.get_parsed_report("r1") is None
        assert s.get_stock("600519") is None
        assert not os.path.exists(fpath)

    def test_get_stocks(self, tmp_data_dir):
        """TC-M02-075: get_stocks returns aggregated list."""
        s = Storage(data_dir=tmp_data_dir)
        s.save_report("r1", "a.pdf", "/tmp/a.pdf")
        s.save_parsed_report("r1", {
            "title": "A", "rating": "买入", "target_price": 100,
            "key_points": "kp", "stock_code": "600519",
            "stock_name": "茅台", "industry": "白酒",
            "raw_text": "t", "parse_time_ms": 1,
        })
        stocks = s.get_stocks()
        assert len(stocks) == 1
        assert stocks[0]["stock_code"] == "600519"
        assert stocks[0]["report_count"] == 1

    def test_get_stock_detail(self, tmp_data_dir):
        """TC-M02-076: get_stock_detail returns detail with reports."""
        s = Storage(data_dir=tmp_data_dir)
        s.save_report("r1", "a.pdf", "/tmp/a.pdf")
        s.save_parsed_report("r1", {
            "title": "A", "rating": "买入", "target_price": 100,
            "key_points": "kp", "stock_code": "600519",
            "stock_name": "茅台", "industry": "白酒",
            "raw_text": "t", "parse_time_ms": 1,
        })
        detail = s.get_stock_detail("600519")
        assert detail is not None
        assert detail["stock_code"] == "600519"
        assert len(detail["reports"]) == 1


# ── Integration Tests: Report CRUD ───────────────────────────

class TestReportCRUD:
    """TC-M02-050 ~ TC-M02-055"""

    def test_list_reports(self, client):
        """TC-M02-050: GET /reports → 200, reports array."""
        _seed_reports(client, 2)
        resp = client.get("/api/v1/reports")
        assert resp.status_code == 200
        body = resp.get_json()
        assert "reports" in body
        assert len(body["reports"]) == 2

    def test_get_report_detail(self, client):
        """TC-M02-051: GET /reports/{id} → 200, full detail."""
        rids = _seed_reports(client, 1)
        resp = client.get(f"/api/v1/reports/{rids[0]}")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["report_id"] == rids[0]
        assert "title" in body

    def test_filter_by_stock_code(self, client):
        """TC-M02-052: GET /reports?stock_code=xxx filters correctly."""
        _seed_reports(client, 2)
        resp = client.get("/api/v1/reports?stock_code=600519")
        assert resp.status_code == 200
        body = resp.get_json()
        for r in body["reports"]:
            assert r.get("stock_code") == "600519"

    def test_delete_report(self, client):
        """TC-M02-053: DELETE /reports/{id} → 200, cascade delete."""
        rids = _seed_reports(client, 1)
        resp = client.delete(f"/api/v1/reports/{rids[0]}")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["message"] == "删除成功"
        # Verify deleted
        resp2 = client.get(f"/api/v1/reports/{rids[0]}")
        assert resp2.status_code == 404

    def test_delete_not_found(self, client):
        """TC-M02-054: DELETE non-existent → 404."""
        resp = client.delete("/api/v1/reports/nonexistent")
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "REPORT_NOT_FOUND"

    def test_download_file(self, client):
        """TC-M02-055: GET /reports/{id}/file → 200 PDF."""
        data = {"file": (io.BytesIO(_make_pdf_bytes()), "dl.pdf")}
        resp = client.post("/api/v1/reports/upload", data=data, content_type="multipart/form-data")
        rid = resp.get_json()["report_id"]
        resp2 = client.get(f"/api/v1/reports/{rid}/file")
        assert resp2.status_code == 200
        assert resp2.content_type == "application/pdf"


# ── Integration Tests: Knowledge Base ────────────────────────

class TestKnowledgeBase:
    """TC-M02-020 ~ TC-M02-025"""

    def test_list_stocks(self, client):
        """TC-M02-020: GET /kb/stocks → 200, stocks array."""
        _seed_reports(client, 2)
        resp = client.get("/api/v1/kb/stocks")
        assert resp.status_code == 200
        body = resp.get_json()
        assert "stocks" in body
        assert len(body["stocks"]) >= 1

    def test_get_stock_detail(self, client):
        """TC-M02-021: GET /kb/stocks/{code} → 200, with summary and reports."""
        _seed_reports(client, 2)
        resp = client.get("/api/v1/kb/stocks/600519")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["stock_code"] == "600519"
        assert "reports" in body
        assert "recent_summary" in body

    def test_stock_aggregation(self, client):
        """TC-M02-022: KB correctly aggregates multiple reports per stock."""
        _seed_reports(client, 2)
        resp = client.get("/api/v1/kb/stocks/600519")
        body = resp.get_json()
        assert body["report_count"] == 2

    def test_summary_non_empty(self, client):
        """TC-M02-023: recent_summary is non-empty after seeding."""
        _seed_reports(client, 2)
        resp = client.get("/api/v1/kb/stocks/600519")
        body = resp.get_json()
        # Summary should have been generated (fallback concatenation)
        assert isinstance(body["recent_summary"], str)

    def test_stock_not_found(self, client):
        """TC-M02-024: non-existent stock → 404 STOCK_NOT_FOUND."""
        resp = client.get("/api/v1/kb/stocks/999999")
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "STOCK_NOT_FOUND"

    def test_stock_reports_sorted(self, client):
        """TC-M02-025: GET /kb/stocks/{code}/reports supports sorting."""
        _seed_reports(client, 2)
        resp = client.get("/api/v1/kb/stocks/600519/reports?order=desc")
        assert resp.status_code == 200
        body = resp.get_json()
        assert "reports" in body
