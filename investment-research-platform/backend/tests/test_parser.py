"""Tests for Parser engine + Report upload/parse APIs."""

import io
import os
import sys
import json
import tempfile
import pytest
from unittest.mock import patch, MagicMock

# Ensure backend is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from storage import Storage
from parser import ReportParser, ParseError, LLMError


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def tmp_data_dir():
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def storage(tmp_data_dir):
    return Storage(data_dir=tmp_data_dir)


@pytest.fixture
def app(tmp_data_dir):
    app = create_app(data_dir=tmp_data_dir, test_mode=True)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _make_pdf_bytes():
    """Create a minimal valid PDF."""
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


MOCK_PARSED = {
    "title": "贵州茅台深度研究报告",
    "rating": "买入",
    "target_price": 2100.00,
    "key_points": "公司业绩稳健增长，高端白酒需求旺盛",
    "stock_code": "600519",
    "stock_name": "贵州茅台",
    "industry": "白酒",
    "raw_text": "这是一份测试研报文本",
    "parse_time_ms": 500,
}


# ── Unit Tests: Storage ──────────────────────────────────────

class TestStorage:
    """TC-M02-070 ~ TC-M02-072"""

    def test_init_creates_dirs(self, tmp_data_dir):
        """TC-M02-070: directories auto-created, JSON files initialized."""
        s = Storage(data_dir=tmp_data_dir)
        assert os.path.isdir(os.path.join(tmp_data_dir, "reports"))

    def test_save_report(self, storage):
        """TC-M02-071: save report metadata, parse_status=pending."""
        report = storage.save_report("r1", "test.pdf", "/tmp/test.pdf")
        assert report["report_id"] == "r1"
        assert report["parse_status"] == "pending"
        assert report["filename"] == "test.pdf"

    def test_save_parsed_report(self, storage):
        """TC-M02-072: save parsed result + update status + update KB."""
        storage.save_report("r1", "test.pdf", "/tmp/test.pdf")
        parsed = storage.save_parsed_report("r1", {
            "title": "测试研报",
            "rating": "买入",
            "target_price": 100.0,
            "key_points": "核心观点",
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "industry": "白酒",
            "raw_text": "text",
            "parse_time_ms": 100,
        })
        assert parsed["report_id"] == "r1"
        # Status should be completed
        report = storage.get_report("r1")
        assert report["parse_status"] == "completed"
        # Should be in KB
        stock = storage.get_stock("600519")
        assert stock is not None
        assert "r1" in stock["report_ids"]


# ── Integration Tests: Upload ────────────────────────────────

class TestUploadAPI:
    """TC-M02-001 ~ TC-M02-003"""

    def test_upload_pdf_success(self, client):
        """TC-M02-001: POST /reports/upload PDF → 201."""
        data = {"file": (io.BytesIO(_make_pdf_bytes()), "test.pdf")}
        resp = client.post("/api/v1/reports/upload", data=data, content_type="multipart/form-data")
        assert resp.status_code == 201
        body = resp.get_json()
        assert "report_id" in body
        assert body["parse_status"] == "pending"
        assert "traceId" in body

    def test_upload_non_pdf_rejected(self, client):
        """TC-M02-002: upload non-PDF → 400 INVALID_FILE_TYPE."""
        data = {"file": (io.BytesIO(b"not a pdf"), "test.txt")}
        resp = client.post("/api/v1/reports/upload", data=data, content_type="multipart/form-data")
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["error"]["code"] == "INVALID_FILE_TYPE"

    def test_upload_too_large(self, client):
        """TC-M02-003: upload > 50MB → 400 FILE_TOO_LARGE."""
        large = b"x" * (50 * 1024 * 1024 + 1)
        data = {"file": (io.BytesIO(large), "big.pdf")}
        resp = client.post("/api/v1/reports/upload", data=data, content_type="multipart/form-data")
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["error"]["code"] == "FILE_TOO_LARGE"


# ── Integration Tests: Parse ─────────────────────────────────

class TestParseAPI:
    """TC-M02-010 ~ TC-M02-015"""

    def _upload(self, client):
        data = {"file": (io.BytesIO(_make_pdf_bytes()), "report.pdf")}
        resp = client.post("/api/v1/reports/upload", data=data, content_type="multipart/form-data")
        return resp.get_json()["report_id"]

    @patch.object(ReportParser, "process", return_value=MOCK_PARSED)
    def test_parse_success(self, mock_proc, client):
        """TC-M02-010: POST /reports/{id}/parse → 200 completed."""
        rid = self._upload(client)
        resp = client.post(f"/api/v1/reports/{rid}/parse")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["parse_status"] == "completed"
        assert "traceId" in body

    @patch.object(ReportParser, "process", return_value=MOCK_PARSED)
    def test_parse_title_present(self, mock_proc, client):
        """TC-M02-011: title is non-empty string."""
        rid = self._upload(client)
        resp = client.post(f"/api/v1/reports/{rid}/parse")
        body = resp.get_json()
        assert isinstance(body["title"], str) and len(body["title"]) > 0

    @patch.object(ReportParser, "process", return_value=MOCK_PARSED)
    def test_parse_rating_valid(self, mock_proc, client):
        """TC-M02-012: rating is a valid enum value."""
        rid = self._upload(client)
        resp = client.post(f"/api/v1/reports/{rid}/parse")
        body = resp.get_json()
        assert body["rating"] in {"买入", "增持", "中性", "减持", "卖出", "未提及"}

    @patch.object(ReportParser, "process", return_value=MOCK_PARSED)
    def test_parse_target_price(self, mock_proc, client):
        """TC-M02-013: target_price is number or null."""
        rid = self._upload(client)
        resp = client.post(f"/api/v1/reports/{rid}/parse")
        body = resp.get_json()
        assert isinstance(body["target_price"], (int, float)) or body["target_price"] is None

    @patch.object(ReportParser, "process", return_value=MOCK_PARSED)
    def test_parse_key_points(self, mock_proc, client):
        """TC-M02-014: key_points is non-empty string."""
        rid = self._upload(client)
        resp = client.post(f"/api/v1/reports/{rid}/parse")
        body = resp.get_json()
        assert isinstance(body["key_points"], str) and len(body["key_points"]) > 0

    @patch.object(ReportParser, "process", return_value=MOCK_PARSED)
    def test_parse_stock_info(self, mock_proc, client):
        """TC-M02-015: stock_code and stock_name present."""
        rid = self._upload(client)
        resp = client.post(f"/api/v1/reports/{rid}/parse")
        body = resp.get_json()
        assert body["stock_code"] == "600519"
        assert body["stock_name"] == "贵州茅台"

    def test_parse_not_found(self, client):
        """Parse non-existent report → 404."""
        resp = client.post("/api/v1/reports/nonexistent/parse")
        assert resp.status_code == 404
        body = resp.get_json()
        assert body["error"]["code"] == "REPORT_NOT_FOUND"
