"""
知识库测试 — test_kb.py

覆盖 Task2 的单元测试和集成测试用例:
- TC-M02-020 ~ TC-M02-025 (知识库集成测试)
- TC-M02-050 ~ TC-M02-055 (研报管理集成测试)
- TC-M02-073 ~ TC-M02-076 (单元测试)

对齐规格: 13-测试策略与质量门禁
"""

import io
import os
import shutil
import tempfile

import pytest

from backend.app import create_app
from backend.knowledge_base import KnowledgeBaseManager
from backend.storage import Storage


# ══════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════

@pytest.fixture
def tmp_data_dir():
    """创建临时数据目录，测试后清理"""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


@pytest.fixture
def storage(tmp_data_dir):
    """创建 Storage 实例"""
    return Storage(data_dir=tmp_data_dir)


@pytest.fixture
def kb_manager(storage):
    """创建 KnowledgeBaseManager 实例（无 LLM）"""
    return KnowledgeBaseManager(storage=storage, llm_client=None)


@pytest.fixture
def app(tmp_data_dir):
    """创建 Flask 测试应用"""
    app = create_app(config={"DATA_DIR": tmp_data_dir})
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Flask 测试客户端"""
    return app.test_client()


def _seed_report(storage, report_id="rpt-001", filename="test.pdf",
                 stock_code="600519", stock_name="贵州茅台", industry="白酒",
                 rating="买入", target_price=2100.0, key_points="核心观点内容"):
    """辅助函数：向 storage 插入一份完整的研报+解析结果"""
    file_path = os.path.join(storage.reports_dir, f"{report_id}.pdf")
    # 创建假 PDF 文件
    with open(file_path, "wb") as f:
        f.write(b"%PDF-1.4 fake content")

    storage.save_report(report_id, filename, file_path)
    storage.save_parsed_report(report_id, {
        "title": f"{stock_name}深度研究",
        "rating": rating,
        "target_price": target_price,
        "key_points": key_points,
        "stock_code": stock_code,
        "stock_name": stock_name,
        "industry": industry,
        "raw_text": "测试原始文本",
        "parse_time_ms": 500,
    })
    return report_id


# ══════════════════════════════════════════════
# TC-M02-073 ~ 076: 单元测试 — Storage 层
# ══════════════════════════════════════════════

class TestStorageUnit:
    """Storage 层 Task2 方法单元测试"""

    def test_get_reports_all(self, storage):
        """TC-M02-073: get_reports 返回全部研报"""
        _seed_report(storage, "rpt-001")
        _seed_report(storage, "rpt-002", stock_code="000858",
                     stock_name="五粮液", key_points="五粮液观点")

        reports = storage.get_reports()
        assert len(reports) == 2
        ids = {r["report_id"] for r in reports}
        assert "rpt-001" in ids
        assert "rpt-002" in ids

    def test_get_reports_filter_stock_code(self, storage):
        """TC-M02-073: get_reports 按 stock_code 筛选"""
        _seed_report(storage, "rpt-001", stock_code="600519")
        _seed_report(storage, "rpt-002", stock_code="000858",
                     stock_name="五粮液", key_points="五粮液观点")

        reports = storage.get_reports({"stock_code": "600519"})
        assert len(reports) == 1
        assert reports[0]["report_id"] == "rpt-001"

    def test_get_reports_filter_industry(self, storage):
        """TC-M02-073: get_reports 按行业筛选"""
        _seed_report(storage, "rpt-001", industry="白酒")
        _seed_report(storage, "rpt-002", stock_code="601318",
                     stock_name="中国平安", industry="保险",
                     key_points="保险观点")

        reports = storage.get_reports({"industry": "保险"})
        assert len(reports) == 1
        assert reports[0]["stock_name"] == "中国平安"

    def test_delete_report_cascade(self, storage):
        """TC-M02-074: delete_report 级联删除"""
        _seed_report(storage, "rpt-001")
        _seed_report(storage, "rpt-002")

        # 删除前确认知识库有数据
        stocks = storage.get_stocks()
        assert len(stocks) == 1
        assert stocks[0]["report_count"] == 2

        # 删除一份
        storage.delete_report("rpt-001")

        # 研报已删除
        assert storage.get_report("rpt-001") is None
        assert storage.get_parsed_report("rpt-001") is None

        # 知识库仍有一份研报
        stocks = storage.get_stocks()
        assert len(stocks) == 1
        assert stocks[0]["report_count"] == 1

    def test_delete_report_removes_stock_when_empty(self, storage):
        """TC-M02-074: 删除最后一份研报时级联删除 Stock 条目"""
        _seed_report(storage, "rpt-001")

        storage.delete_report("rpt-001")

        stocks = storage.get_stocks()
        assert len(stocks) == 0

    def test_delete_report_removes_pdf(self, storage):
        """TC-M02-074: 删除研报同时删除 PDF 文件"""
        _seed_report(storage, "rpt-001")
        file_path = os.path.join(storage.reports_dir, "rpt-001.pdf")
        assert os.path.exists(file_path)

        storage.delete_report("rpt-001")
        assert not os.path.exists(file_path)

    def test_get_stocks(self, storage):
        """TC-M02-075: get_stocks 返回按股票聚合的列表"""
        _seed_report(storage, "rpt-001", stock_code="600519")
        _seed_report(storage, "rpt-002", stock_code="600519")
        _seed_report(storage, "rpt-003", stock_code="000858",
                     stock_name="五粮液", key_points="五粮液观点")

        stocks = storage.get_stocks()
        assert len(stocks) == 2

        maotai = next(s for s in stocks if s["stock_code"] == "600519")
        wuliangye = next(s for s in stocks if s["stock_code"] == "000858")
        assert maotai["report_count"] == 2
        assert wuliangye["report_count"] == 1

    def test_get_stock_detail(self, storage):
        """TC-M02-076: get_stock_detail 返回股票详情"""
        _seed_report(storage, "rpt-001", stock_code="600519")
        _seed_report(storage, "rpt-002", stock_code="600519",
                     key_points="另一份观点")

        detail = storage.get_stock_detail("600519")
        assert detail is not None
        assert detail["stock_code"] == "600519"
        assert detail["stock_name"] == "贵州茅台"
        assert detail["report_count"] == 2
        assert len(detail["reports"]) == 2

    def test_get_stock_detail_not_found(self, storage):
        """TC-M02-076: 不存在的 stock_code 返回 None"""
        detail = storage.get_stock_detail("999999")
        assert detail is None


# ══════════════════════════════════════════════
# KnowledgeBaseManager 单元测试
# ══════════════════════════════════════════════

class TestKnowledgeBaseManager:
    """KnowledgeBaseManager 单元测试"""

    def test_generate_summary_no_llm(self, storage, kb_manager):
        """TC-M02-076 补充: 无 LLM 时生成降级汇总"""
        _seed_report(storage, "rpt-001", key_points="茅台业绩增长强劲")
        _seed_report(storage, "rpt-002", key_points="茅台产能扩张顺利")

        summary = kb_manager.generate_summary("600519")
        assert summary != ""
        assert "贵州茅台" in summary
        assert "茅台业绩增长强劲" in summary
        assert "茅台产能扩张顺利" in summary

    def test_generate_summary_empty_stock(self, storage, kb_manager):
        """无研报时汇总为空"""
        # 手动创建空股票条目
        storage._stocks["999999"] = {
            "stock_code": "999999",
            "stock_name": "测试股",
            "industry": "测试",
            "report_ids": [],
            "recent_summary": "",
            "updated_at": "",
        }
        summary = kb_manager.generate_summary("999999")
        assert summary == ""

    def test_get_stock_reports_sorted(self, storage, kb_manager):
        """TC-M02-025: get_stock_reports 支持时间排序"""
        _seed_report(storage, "rpt-001", stock_code="600519")
        _seed_report(storage, "rpt-002", stock_code="600519",
                     key_points="后上传的观点")

        reports = kb_manager.get_stock_reports("600519", order="desc")
        assert len(reports) == 2
        # desc 排序：upload_time 更晚的在前
        assert reports[0]["upload_time"] >= reports[1]["upload_time"]


# ══════════════════════════════════════════════
# TC-M02-020 ~ 025: 集成测试 — 知识库 API
# ══════════════════════════════════════════════

class TestKnowledgeBaseAPI:
    """知识库 API 集成测试"""

    def _seed_via_storage(self, app):
        """通过 storage 直接插入测试数据"""
        with app.app_context():
            storage = app.config["storage"]
            _seed_report(storage, "rpt-001", stock_code="600519")
            _seed_report(storage, "rpt-002", stock_code="600519",
                         key_points="第二份研报观点")
            _seed_report(storage, "rpt-003", stock_code="000858",
                         stock_name="五粮液", key_points="五粮液观点")

    def test_get_kb_stocks_200(self, app, client):
        """TC-M02-020: GET /kb/stocks → 200, 返回 stocks 数组"""
        self._seed_via_storage(app)

        resp = client.get("/api/v1/kb/stocks")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "traceId" in data
        assert "stocks" in data
        assert isinstance(data["stocks"], list)
        assert len(data["stocks"]) == 2

    def test_get_kb_stock_detail_200(self, app, client):
        """TC-M02-021: GET /kb/stocks/{code} → 200"""
        self._seed_via_storage(app)

        resp = client.get("/api/v1/kb/stocks/600519")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["stock_code"] == "600519"
        assert "recent_summary" in data
        assert "reports" in data
        assert isinstance(data["reports"], list)

    def test_kb_stock_aggregation(self, app, client):
        """TC-M02-022: 知识库按 stock_code 正确聚合多份研报"""
        self._seed_via_storage(app)

        resp = client.get("/api/v1/kb/stocks/600519")
        data = resp.get_json()
        assert data["report_count"] == 2
        assert len(data["reports"]) == 2

    def test_kb_recent_summary_not_empty(self, app, client):
        """TC-M02-023: recent_summary 非空"""
        self._seed_via_storage(app)
        # 先生成汇总
        with app.app_context():
            kb_manager = app.config["kb_manager"]
            kb_manager.generate_summary("600519")

        resp = client.get("/api/v1/kb/stocks/600519")
        data = resp.get_json()
        assert data["recent_summary"] != ""

    def test_kb_stock_not_found_404(self, client):
        """TC-M02-024: 不存在的 stock_code → 404, STOCK_NOT_FOUND"""
        resp = client.get("/api/v1/kb/stocks/999999")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"]["code"] == "STOCK_NOT_FOUND"

    def test_kb_stock_reports_sorted(self, app, client):
        """TC-M02-025: GET /kb/stocks/{code}/reports 支持时间排序"""
        self._seed_via_storage(app)

        resp = client.get("/api/v1/kb/stocks/600519/reports?order=desc")
        assert resp.status_code == 200
        data = resp.get_json()
        reports = data["reports"]
        assert len(reports) == 2
        assert reports[0]["upload_time"] >= reports[1]["upload_time"]


# ══════════════════════════════════════════════
# TC-M02-050 ~ 055: 集成测试 — 研报管理 API
# ══════════════════════════════════════════════

class TestReportManagementAPI:
    """研报管理 API 集成测试"""

    def _seed_via_storage(self, app):
        with app.app_context():
            storage = app.config["storage"]
            _seed_report(storage, "rpt-001", stock_code="600519")
            _seed_report(storage, "rpt-002", stock_code="600519",
                         key_points="第二份观点")
            _seed_report(storage, "rpt-003", stock_code="000858",
                         stock_name="五粮液", industry="白酒",
                         key_points="五粮液观点")

    def test_get_reports_200(self, app, client):
        """TC-M02-050: GET /reports → 200, 返回 reports 数组"""
        self._seed_via_storage(app)

        resp = client.get("/api/v1/reports")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "traceId" in data
        assert "reports" in data
        assert isinstance(data["reports"], list)
        assert len(data["reports"]) == 3

    def test_get_report_detail_200(self, app, client):
        """TC-M02-051: GET /reports/{id} → 200, 含完整研报详情"""
        self._seed_via_storage(app)

        resp = client.get("/api/v1/reports/rpt-001")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["report_id"] == "rpt-001"
        assert "title" in data
        assert "rating" in data
        assert "stock_code" in data
        assert "parse_status" in data
        assert "upload_time" in data

    def test_get_reports_filter_stock_code(self, app, client):
        """TC-M02-052: GET /reports?stock_code=xxx 筛选正确"""
        self._seed_via_storage(app)

        resp = client.get("/api/v1/reports?stock_code=600519")
        data = resp.get_json()
        assert len(data["reports"]) == 2
        for r in data["reports"]:
            assert r["stock_code"] == "600519"

    def test_delete_report_200_cascade(self, app, client):
        """TC-M02-053: DELETE /reports/{id} → 200, 级联删除"""
        self._seed_via_storage(app)

        resp = client.delete("/api/v1/reports/rpt-001")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["message"] == "删除成功"
        assert data["report_id"] == "rpt-001"

        # 确认已删除
        resp = client.get("/api/v1/reports/rpt-001")
        assert resp.status_code == 404

    def test_delete_report_not_found_404(self, client):
        """TC-M02-054: 删除不存在的研报 → 404, REPORT_NOT_FOUND"""
        resp = client.delete("/api/v1/reports/nonexistent")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"]["code"] == "REPORT_NOT_FOUND"

    def test_download_report_file_200(self, app, client):
        """TC-M02-055: GET /reports/{id}/file → 200, 返回 PDF 文件"""
        self._seed_via_storage(app)

        resp = client.get("/api/v1/reports/rpt-001/file")
        assert resp.status_code == 200
        assert resp.content_type == "application/pdf"

    def test_download_report_file_not_found(self, client):
        """TC-M02-055 补充: 不存在的研报文件 → 404"""
        resp = client.get("/api/v1/reports/nonexistent/file")
        assert resp.status_code == 404

    def test_get_report_not_found_404(self, client):
        """TC-M02-054 补充: GET 不存在的研报 → 404"""
        resp = client.get("/api/v1/reports/nonexistent")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"]["code"] == "REPORT_NOT_FOUND"
