"""Task3 测试用例：研报比对引擎 + 行情数据服务 + 集成测试"""
import json
import os
import sys
import shutil
import tempfile
import time
from unittest.mock import patch, MagicMock

import pytest

# 将 backend 目录加入 sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from storage import Storage
from comparator import ReportComparator
from stock_data import StockDataService
from app import create_app


# ==================== Fixtures ====================

@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def storage(tmp_dir):
    return Storage(data_dir=tmp_dir)


@pytest.fixture
def seeded_storage(storage):
    """预置 2 份同一公司 + 1 份不同公司的研报解析数据"""
    storage.save_report("r1", "report1.pdf", os.path.join(storage.reports_dir, "r1.pdf"))
    storage.save_report("r2", "report2.pdf", os.path.join(storage.reports_dir, "r2.pdf"))
    storage.save_report("r3", "report3.pdf", os.path.join(storage.reports_dir, "r3.pdf"))
    # 创建空 PDF 文件占位
    for rid in ("r1", "r2", "r3"):
        fpath = os.path.join(storage.reports_dir, f"{rid}.pdf")
        with open(fpath, "wb") as f:
            f.write(b"%PDF-1.4 fake")

    storage.save_parsed_report("r1", {
        "title": "券商A - 贵州茅台深度研究",
        "rating": "买入",
        "target_price": 2100.00,
        "key_points": "2026年营收增速将达15%以上，品牌护城河稳固，白酒行业龙头地位不变",
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "industry": "白酒",
        "raw_text": "fake text 1",
        "parse_time_ms": 3000,
    })
    storage.save_parsed_report("r2", {
        "title": "券商B - 贵州茅台跟踪报告",
        "rating": "增持",
        "target_price": 1980.00,
        "key_points": "短期估值偏高但长期增长逻辑不变，建议逢低布局",
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "industry": "白酒",
        "raw_text": "fake text 2",
        "parse_time_ms": 2500,
    })
    storage.save_parsed_report("r3", {
        "title": "券商C - 比亚迪新能源展望",
        "rating": "买入",
        "target_price": 350.00,
        "key_points": "新能源汽车销量持续增长，海外市场拓展顺利",
        "stock_code": "002594",
        "stock_name": "比亚迪",
        "industry": "新能源汽车",
        "raw_text": "fake text 3",
        "parse_time_ms": 2000,
    })
    return storage


@pytest.fixture
def comparator(seeded_storage):
    return ReportComparator(seeded_storage, llm_client=None)


@pytest.fixture
def stock_data_service():
    return StockDataService(cache_ttl=300)


@pytest.fixture
def app(tmp_dir, seeded_storage):
    """创建已预置数据的 Flask 测试应用"""
    test_app = create_app(data_dir=tmp_dir)
    # 替换为已预置数据的 storage
    test_app.config["storage"] = seeded_storage
    test_app.config["comparator"] = ReportComparator(seeded_storage, llm_client=None)
    test_app.config["stock_data_service"] = StockDataService(cache_ttl=300)
    test_app.config["TESTING"] = True
    return test_app


@pytest.fixture
def client(app):
    return app.test_client()


# ==================== 单元测试: ReportComparator ====================

class TestComparatorValidate:
    """TC-COMP-001 ~ TC-COMP-002"""

    def test_validate_min_reports(self, comparator):
        """TC-COMP-001: report_ids < 2 返回错误"""
        ok, code = comparator.validate(["r1"])
        assert not ok
        assert code == "COMPARE_MIN_REPORTS"

    def test_validate_empty_list(self, comparator):
        ok, code = comparator.validate([])
        assert not ok
        assert code == "COMPARE_MIN_REPORTS"

    def test_validate_report_not_found(self, comparator):
        ok, code = comparator.validate(["r1", "nonexistent"])
        assert not ok
        assert code == "REPORT_NOT_FOUND"

    def test_validate_diff_stock(self, comparator):
        """TC-COMP-002: 不同 stock_code 返回错误"""
        ok, code = comparator.validate(["r1", "r3"])
        assert not ok
        assert code == "COMPARE_DIFF_STOCK"

    def test_validate_success(self, comparator):
        ok, code = comparator.validate(["r1", "r2"])
        assert ok
        assert code == ""


class TestComparatorCompareFields:
    """TC-COMP-003: 正确检测 rating/target_price 差异"""

    def test_compare_fields_rating_diff(self, comparator, seeded_storage):
        parsed = [seeded_storage.get_parsed_report("r1"), seeded_storage.get_parsed_report("r2")]
        diffs = comparator._compare_fields(parsed)
        rating_diffs = [d for d in diffs if d["field"] == "rating"]
        assert len(rating_diffs) == 1
        assert "买入" in str(rating_diffs[0]["values"])
        assert "增持" in str(rating_diffs[0]["values"])

    def test_compare_fields_target_price_diff(self, comparator, seeded_storage):
        parsed = [seeded_storage.get_parsed_report("r1"), seeded_storage.get_parsed_report("r2")]
        diffs = comparator._compare_fields(parsed)
        price_diffs = [d for d in diffs if d["field"] == "target_price"]
        assert len(price_diffs) == 1
        assert 2100.0 in price_diffs[0]["values"].values()
        assert 1980.0 in price_diffs[0]["values"].values()
        assert "%" in price_diffs[0]["highlight"]


class TestComparatorBuildSummary:
    """TC-COMP-004: 正确构建摘要"""

    def test_build_reports_summary(self, comparator, seeded_storage):
        parsed = [seeded_storage.get_parsed_report("r1"), seeded_storage.get_parsed_report("r2")]
        summaries = comparator._build_reports_summary(parsed)
        assert len(summaries) == 2
        assert summaries[0]["report_id"] == "r1"
        assert summaries[0]["title"] == "券商A - 贵州茅台深度研究"
        assert summaries[0]["rating"] == "买入"
        assert summaries[0]["target_price"] == 2100.0
        assert summaries[1]["report_id"] == "r2"


class TestComparatorCompare:
    """比对完整流程测试"""

    def test_compare_full(self, comparator):
        result = comparator.compare(["r1", "r2"])
        assert result["stock_code"] == "600519"
        assert result["stock_name"] == "贵州茅台"
        assert len(result["reports_summary"]) == 2
        assert isinstance(result["similarities"], list)
        assert isinstance(result["differences"], list)
        assert "compare_time_ms" in result
        # 应有 rating 和 target_price 差异
        diff_fields = [d["field"] for d in result["differences"]]
        assert "rating" in diff_fields
        assert "target_price" in diff_fields


# ==================== 单元测试: StockDataService ====================

class TestStockDataService:
    """TC-STOCK-001 ~ TC-STOCK-002"""

    def test_cache_hit(self, stock_data_service):
        """TC-STOCK-001: 缓存命中返回 cache"""
        stock_data_service._cache["600519"] = {
            "data": {
                "stock_code": "600519",
                "pe": 35.2,
                "pb": 12.8,
                "market_cap": 26000.0,
                "latest_price": 1850.0,
                "data_time": "2026-04-15T15:00:00Z",
            },
            "timestamp": time.time(),
        }
        result = stock_data_service.get_market_data("600519")
        assert result["source"] == "cache"
        assert result["pe"] == 35.2
        assert result["stock_code"] == "600519"

    def test_cache_expired(self, stock_data_service):
        """缓存过期后不返回缓存"""
        stock_data_service._cache["600519"] = {
            "data": {"stock_code": "600519", "pe": 35.2},
            "timestamp": time.time() - 600,  # 已过期
        }
        with patch.object(stock_data_service, "_fetch_from_akshare", return_value=None):
            result = stock_data_service.get_market_data("600519")
        assert result["source"] == "unavailable"

    def test_akshare_unavailable(self, stock_data_service):
        """TC-STOCK-002: AKShare 异常返回 unavailable"""
        with patch.object(stock_data_service, "_fetch_from_akshare", return_value=None):
            result = stock_data_service.get_market_data("999999")
        assert result["source"] == "unavailable"
        assert result["pe"] is None
        assert result["pb"] is None
        assert result["market_cap"] is None
        assert result["latest_price"] is None

    def test_fetch_success_updates_cache(self, stock_data_service):
        """AKShare 成功时更新缓存"""
        fake_data = {
            "stock_code": "600519",
            "pe": 35.0,
            "pb": 12.0,
            "market_cap": 25000.0,
            "latest_price": 1800.0,
            "data_time": "2026-04-15T15:00:00Z",
        }
        with patch.object(stock_data_service, "_fetch_from_akshare", return_value=fake_data):
            result = stock_data_service.get_market_data("600519")
        assert result["source"] == "akshare"
        assert result["pe"] == 35.0
        assert "600519" in stock_data_service._cache


# ==================== 集成测试: POST /reports/compare ====================

class TestCompareAPI:
    """TC-M02-030 ~ TC-M02-035"""

    def test_compare_success(self, client):
        """TC-M02-030: 2 份同公司研报比对 → 200"""
        resp = client.post("/api/v1/reports/compare",
                           data=json.dumps({"report_ids": ["r1", "r2"]}),
                           content_type="application/json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "traceId" in data
        assert data["stock_code"] == "600519"

    def test_compare_has_similarities(self, client):
        """TC-M02-031: 响应包含 similarities 数组"""
        resp = client.post("/api/v1/reports/compare",
                           data=json.dumps({"report_ids": ["r1", "r2"]}),
                           content_type="application/json")
        data = resp.get_json()
        assert "similarities" in data
        assert isinstance(data["similarities"], list)

    def test_compare_has_differences(self, client):
        """TC-M02-032: 响应包含 differences 数组"""
        resp = client.post("/api/v1/reports/compare",
                           data=json.dumps({"report_ids": ["r1", "r2"]}),
                           content_type="application/json")
        data = resp.get_json()
        assert "differences" in data
        assert isinstance(data["differences"], list)
        assert len(data["differences"]) > 0

    def test_compare_has_reports_summary(self, client):
        """TC-M02-033: reports_summary 包含每份研报的核心字段"""
        resp = client.post("/api/v1/reports/compare",
                           data=json.dumps({"report_ids": ["r1", "r2"]}),
                           content_type="application/json")
        data = resp.get_json()
        assert "reports_summary" in data
        assert len(data["reports_summary"]) == 2
        for s in data["reports_summary"]:
            assert "report_id" in s
            assert "title" in s
            assert "rating" in s
            assert "target_price" in s
            assert "key_points" in s

    def test_compare_min_reports(self, client):
        """TC-M02-034: report_ids < 2 → 400 COMPARE_MIN_REPORTS"""
        resp = client.post("/api/v1/reports/compare",
                           data=json.dumps({"report_ids": ["r1"]}),
                           content_type="application/json")
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"]["code"] == "COMPARE_MIN_REPORTS"

    def test_compare_diff_stock(self, client):
        """TC-M02-035: 不同公司研报 → 400 COMPARE_DIFF_STOCK"""
        resp = client.post("/api/v1/reports/compare",
                           data=json.dumps({"report_ids": ["r1", "r3"]}),
                           content_type="application/json")
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"]["code"] == "COMPARE_DIFF_STOCK"

    def test_compare_report_not_found(self, client):
        """比对时某研报不存在 → 404 REPORT_NOT_FOUND"""
        resp = client.post("/api/v1/reports/compare",
                           data=json.dumps({"report_ids": ["r1", "nonexistent"]}),
                           content_type="application/json")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"]["code"] == "REPORT_NOT_FOUND"

    def test_compare_no_body(self, client):
        """空请求体 → 400"""
        resp = client.post("/api/v1/reports/compare", content_type="application/json")
        assert resp.status_code == 400


# ==================== 集成测试: GET /stocks/{code}/market-data ====================

class TestMarketDataAPI:
    """TC-M02-060 ~ TC-M02-063"""

    def test_market_data_with_mock(self, app, client):
        """TC-M02-060: 行情数据返回 200 + pe/pb/market_cap"""
        svc = app.config["stock_data_service"]
        svc._cache["600519"] = {
            "data": {
                "stock_code": "600519",
                "pe": 35.2,
                "pb": 12.8,
                "market_cap": 26000.0,
                "latest_price": 1850.0,
                "data_time": "2026-04-15T15:00:00Z",
            },
            "timestamp": time.time(),
        }
        resp = client.get("/api/v1/stocks/600519/market-data")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "traceId" in data
        assert data["pe"] == 35.2
        assert data["pb"] == 12.8
        assert data["market_cap"] == 26000.0

    def test_market_data_source_cache(self, app, client):
        """TC-M02-061: source 为 cache"""
        svc = app.config["stock_data_service"]
        svc._cache["600519"] = {
            "data": {
                "stock_code": "600519",
                "pe": 35.2,
                "pb": 12.8,
                "market_cap": 26000.0,
                "latest_price": 1850.0,
                "data_time": "2026-04-15T15:00:00Z",
            },
            "timestamp": time.time(),
        }
        resp = client.get("/api/v1/stocks/600519/market-data")
        data = resp.get_json()
        assert data["source"] == "cache"

    def test_market_data_unavailable(self, app, client):
        """TC-M02-062: AKShare 不可用时 source=unavailable"""
        svc = app.config["stock_data_service"]
        with patch.object(svc, "_fetch_from_akshare", return_value=None):
            resp = client.get("/api/v1/stocks/999999/market-data")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["source"] == "unavailable"
        assert data["pe"] is None
        assert data["pb"] is None

    def test_market_data_unknown_stock(self, app, client):
        """TC-M02-063: 不存在的 stock_code 降级处理"""
        svc = app.config["stock_data_service"]
        with patch.object(svc, "_fetch_from_akshare", return_value=None):
            resp = client.get("/api/v1/stocks/000000/market-data")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["source"] == "unavailable"
        assert data["stock_name"] == ""

    def test_market_data_has_stock_name(self, app, client):
        """行情数据中包含 stock_name"""
        svc = app.config["stock_data_service"]
        svc._cache["600519"] = {
            "data": {
                "stock_code": "600519",
                "pe": 35.2, "pb": 12.8,
                "market_cap": 26000.0, "latest_price": 1850.0,
                "data_time": "2026-04-15T15:00:00Z",
            },
            "timestamp": time.time(),
        }
        resp = client.get("/api/v1/stocks/600519/market-data")
        data = resp.get_json()
        assert data["stock_name"] == "贵州茅台"
