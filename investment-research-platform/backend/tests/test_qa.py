"""Tests for QAService engine + QA session/message APIs."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from storage import Storage
from qa_service import QAService


# ── Test data helpers ────────────────────────────────────────

def _create_test_data(data_dir):
    """在 data_dir 中创建测试用的 reports.json 和 parsed_reports.json"""
    os.makedirs(os.path.join(data_dir, "reports"), exist_ok=True)

    reports = {
        "test-report-1": {
            "report_id": "test-report-1",
            "filename": "测试研报1.pdf",
            "file_path": "data/reports/test-report-1.pdf",
            "parse_status": "completed",
            "upload_time": "2026-01-01T00:00:00+00:00",
        },
        "test-report-2": {
            "report_id": "test-report-2",
            "filename": "测试研报2.pdf",
            "file_path": "data/reports/test-report-2.pdf",
            "parse_status": "completed",
            "upload_time": "2026-01-01T00:00:00+00:00",
        },
        "test-report-unparsed": {
            "report_id": "test-report-unparsed",
            "filename": "未解析研报.pdf",
            "file_path": "data/reports/test-report-unparsed.pdf",
            "parse_status": "pending",
            "upload_time": "2026-01-01T00:00:00+00:00",
        },
    }

    parsed_reports = {
        "test-report-1": {
            "report_id": "test-report-1",
            "title": "贵州茅台投资分析",
            "rating": "买入",
            "target_price": 1900.0,
            "key_points": "茅台提价利好",
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "industry": "食品饮料",
            "raw_text": "这是测试研报1的完整原文内容，包含关于贵州茅台的详细分析...",
            "_llm_model_used": "qwen3.5-plus",
            "parse_time_ms": 5000,
            "parsed_at": "2026-01-01T00:01:00+00:00",
        },
        "test-report-2": {
            "report_id": "test-report-2",
            "title": "贵州茅台渠道分析",
            "rating": "增持",
            "target_price": 1800.0,
            "key_points": "渠道结构调整",
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "industry": "食品饮料",
            "raw_text": "这是测试研报2的完整原文内容，分析了茅台渠道变化...",
            "_llm_model_used": "qwen3.5-plus",
            "parse_time_ms": 4000,
            "parsed_at": "2026-01-01T00:01:00+00:00",
        },
    }

    with open(os.path.join(data_dir, "reports.json"), "w", encoding="utf-8") as f:
        json.dump(reports, f, ensure_ascii=False)
    with open(os.path.join(data_dir, "parsed_reports.json"), "w", encoding="utf-8") as f:
        json.dump(parsed_reports, f, ensure_ascii=False)
    with open(os.path.join(data_dir, "knowledge_base.json"), "w", encoding="utf-8") as f:
        json.dump({}, f)


def _mock_llm_response(content_json):
    """创建模拟的 LLM API 响应对象"""
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_message.content = json.dumps(content_json, ensure_ascii=False)
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    return mock_response


def _mock_llm_response_text(text: str):
    """创建返回纯文本（非JSON）的 LLM 响应"""
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_message.content = text
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    return mock_response


MOCK_LLM_ANSWER = {
    "answer": "根据研报分析，贵州茅台的目标价为1900元。",
    "source_type": "report_based",
    "sources": [
        {
            "report_id": "test-report-1",
            "report_title": "贵州茅台投资分析",
            "quote": "茅台提价利好",
        }
    ],
}


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def tmp_data_dir():
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def seeded_data_dir(tmp_data_dir):
    """带预置测试数据的临时目录"""
    _create_test_data(tmp_data_dir)
    return tmp_data_dir


@pytest.fixture
def app(seeded_data_dir):
    app = create_app(data_dir=seeded_data_dir, test_mode=True)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def storage(seeded_data_dir):
    return Storage(data_dir=seeded_data_dir)


@pytest.fixture
def qa_service(seeded_data_dir, storage):
    """创建带 mock LLM client 的 QAService"""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_llm_response(MOCK_LLM_ANSWER)
    return QAService(
        storage=storage,
        llm_client=mock_client,
        llm_model="qwen3.5-plus",
        llm_fallback_model="glm-4-flash",
        data_dir=seeded_data_dir,
    )


# ── Unit Tests: QAService session CRUD ───────────────────────

class TestQAServiceCRUD:
    """会话创建、列表、详情、删除"""

    def test_create_session(self, qa_service):
        """创建会话后能在列表中找到"""
        session = qa_service.create_session(["test-report-1"])
        assert "session_id" in session
        assert session["title"] == "新会话"
        assert session["report_ids"] == ["test-report-1"]

        sessions = qa_service.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == session["session_id"]

    def test_get_session(self, qa_service):
        """创建后能通过 get_session 获取详情"""
        created = qa_service.create_session(["test-report-1", "test-report-2"])
        detail = qa_service.get_session(created["session_id"])
        assert detail["session_id"] == created["session_id"]
        assert detail["report_ids"] == ["test-report-1", "test-report-2"]
        assert "messages" in detail

    def test_delete_session(self, qa_service):
        """删除后列表为空"""
        created = qa_service.create_session(["test-report-1"])
        qa_service.delete_session(created["session_id"])
        assert len(qa_service.list_sessions()) == 0

    def test_delete_nonexistent_session(self, qa_service):
        """删除不存在的会话抛 ValueError"""
        with pytest.raises(ValueError, match="SESSION_NOT_FOUND"):
            qa_service.delete_session("nonexistent-id")

    def test_get_nonexistent_session(self, qa_service):
        """获取不存在的会话抛 ValueError"""
        with pytest.raises(ValueError, match="SESSION_NOT_FOUND"):
            qa_service.get_session("nonexistent-id")

    def test_create_session_report_not_found(self, qa_service):
        """report_ids 中有不存在的研报 → ValueError"""
        with pytest.raises(ValueError, match="REPORTS_NOT_FOUND"):
            qa_service.create_session(["nonexistent-report"])

    def test_create_session_report_not_parsed(self, qa_service):
        """report_ids 中有未解析的研报 → ValueError"""
        with pytest.raises(ValueError, match="REPORTS_NOT_PARSED"):
            qa_service.create_session(["test-report-unparsed"])

    def test_list_sessions_empty(self, qa_service):
        """空列表返回空数组"""
        assert qa_service.list_sessions() == []

    def test_session_summary_has_message_count(self, qa_service):
        """会话摘要包含 message_count"""
        qa_service.create_session(["test-report-1"])
        sessions = qa_service.list_sessions()
        assert "message_count" in sessions[0]
        assert sessions[0]["message_count"] == 0


# ── Unit Tests: QAService ask (mock LLM) ────────────────────

class TestQAServiceAsk:
    """问答流程、多轮对话、标题更新"""

    def test_ask_returns_structured_answer(self, qa_service):
        """正常问答返回结构化回答"""
        session = qa_service.create_session(["test-report-1"])
        answer = qa_service.ask(session["session_id"], "茅台目标价是多少？")
        assert "content" in answer
        assert answer["role"] == "assistant"
        assert "source_type" in answer
        assert "sources" in answer

    def test_ask_sources_present(self, qa_service):
        """回答中包含 sources 和 source_type"""
        session = qa_service.create_session(["test-report-1"])
        answer = qa_service.ask(session["session_id"], "茅台目标价是多少？")
        assert answer["source_type"] == "report_based"
        assert len(answer["sources"]) > 0
        assert answer["sources"][0]["report_id"] == "test-report-1"

    def test_ask_appends_messages(self, qa_service):
        """消息被正确追加到会话中"""
        session = qa_service.create_session(["test-report-1"])
        qa_service.ask(session["session_id"], "茅台目标价是多少？")
        detail = qa_service.get_session(session["session_id"])
        assert len(detail["messages"]) == 2  # 1 user + 1 assistant
        assert detail["messages"][0]["role"] == "user"
        assert detail["messages"][1]["role"] == "assistant"

    def test_ask_updates_title_on_first_question(self, qa_service):
        """首次问答后会话标题被更新"""
        session = qa_service.create_session(["test-report-1"])
        question = "茅台目标价是多少？"
        qa_service.ask(session["session_id"], question)
        detail = qa_service.get_session(session["session_id"])
        assert detail["title"] == question[:30]

    def test_ask_session_not_found(self, qa_service):
        """问答时 session 不存在 → ValueError"""
        with pytest.raises(ValueError, match="SESSION_NOT_FOUND"):
            qa_service.ask("nonexistent-id", "问题")

    def test_multi_turn_conversation(self, qa_service):
        """连续问两个问题后，会话中有 4 条消息（2 user + 2 assistant）"""
        session = qa_service.create_session(["test-report-1"])
        qa_service.ask(session["session_id"], "茅台目标价是多少？")
        qa_service.ask(session["session_id"], "茅台评级是什么？")
        detail = qa_service.get_session(session["session_id"])
        assert len(detail["messages"]) == 4
        roles = [m["role"] for m in detail["messages"]]
        assert roles == ["user", "assistant", "user", "assistant"]


# ── Unit Tests: LLM fallback & tolerance ─────────────────────

class TestQAServiceLLMFallback:
    """LLM 降级与容错"""

    def test_fallback_to_backup_model(self, seeded_data_dir, storage):
        """主模型失败时自动切换到备用模型"""
        mock_client = MagicMock()
        # 第一次调用（主模型）抛异常，第二次调用（备用模型）成功
        mock_client.chat.completions.create.side_effect = [
            Exception("primary model timeout"),
            _mock_llm_response(MOCK_LLM_ANSWER),
        ]
        svc = QAService(
            storage=storage,
            llm_client=mock_client,
            llm_model="qwen3.5-plus",
            llm_fallback_model="glm-4-flash",
            data_dir=seeded_data_dir,
        )
        session = svc.create_session(["test-report-1"])
        answer = svc.ask(session["session_id"], "茅台目标价是多少？")
        assert answer["role"] == "assistant"
        # 验证调用了两次（主 + 备）
        assert mock_client.chat.completions.create.call_count == 2

    def test_both_models_fail_raises(self, seeded_data_dir, storage):
        """主备模型都失败 → RuntimeError"""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("all models down")
        svc = QAService(
            storage=storage,
            llm_client=mock_client,
            llm_model="qwen3.5-plus",
            llm_fallback_model="glm-4-flash",
            data_dir=seeded_data_dir,
        )
        session = svc.create_session(["test-report-1"])
        with pytest.raises(RuntimeError, match="QA_FAILED"):
            svc.ask(session["session_id"], "测试问题")

    def test_non_json_response_fallback(self, seeded_data_dir, storage):
        """LLM 返回非 JSON 内容时，降级为纯文本回答"""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_llm_response_text(
            "这是一个纯文本回答，没有JSON格式。"
        )
        svc = QAService(
            storage=storage,
            llm_client=mock_client,
            llm_model="qwen3.5-plus",
            llm_fallback_model="glm-4-flash",
            data_dir=seeded_data_dir,
        )
        session = svc.create_session(["test-report-1"])
        answer = svc.ask(session["session_id"], "测试问题")
        assert answer["role"] == "assistant"
        assert answer["content"] == "这是一个纯文本回答，没有JSON格式。"
        assert answer["source_type"] == "ai_generated"
        assert answer["sources"] == []


# ── Integration Tests: QA API routes ─────────────────────────

class TestQAAPICreateSession:
    """POST /api/v1/qa/sessions"""

    def test_create_session_success(self, client, app):
        """正常创建会话 → 201"""
        resp = client.post("/api/v1/qa/sessions", json={
            "report_ids": ["test-report-1", "test-report-2"],
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert "session_id" in body
        assert body["title"] == "新会话"
        assert "traceId" in body

    def test_create_session_empty_report_ids(self, client):
        """report_ids 为空 → 400"""
        resp = client.post("/api/v1/qa/sessions", json={"report_ids": []})
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "INVALID_PARAMS"

    def test_create_session_missing_report_ids(self, client):
        """缺少 report_ids 字段 → 400"""
        resp = client.post("/api/v1/qa/sessions", json={})
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "INVALID_PARAMS"

    def test_create_session_report_not_found(self, client):
        """report_ids 中有不存在的研报 → 404"""
        resp = client.post("/api/v1/qa/sessions", json={
            "report_ids": ["nonexistent-report"],
        })
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "REPORTS_NOT_FOUND"

    def test_create_session_report_not_parsed(self, client):
        """report_ids 中有未解析的研报 → 400"""
        resp = client.post("/api/v1/qa/sessions", json={
            "report_ids": ["test-report-unparsed"],
        })
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "REPORTS_NOT_PARSED"


class TestQAAPIListSessions:
    """GET /api/v1/qa/sessions"""

    def test_list_sessions_empty(self, client):
        """空列表 → 200, 空数组"""
        resp = client.get("/api/v1/qa/sessions")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["sessions"] == []

    def test_list_sessions_with_data(self, client):
        """有会话时返回摘要信息"""
        client.post("/api/v1/qa/sessions", json={
            "report_ids": ["test-report-1"],
        })
        resp = client.get("/api/v1/qa/sessions")
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["sessions"]) == 1
        assert "session_id" in body["sessions"][0]
        assert "message_count" in body["sessions"][0]


class TestQAAPIGetSession:
    """GET /api/v1/qa/sessions/<session_id>"""

    def test_get_session_success(self, client):
        """正常获取 → 200"""
        create_resp = client.post("/api/v1/qa/sessions", json={
            "report_ids": ["test-report-1"],
        })
        session_id = create_resp.get_json()["session_id"]
        resp = client.get(f"/api/v1/qa/sessions/{session_id}")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["session_id"] == session_id
        assert "messages" in body

    def test_get_session_not_found(self, client):
        """不存在的 session_id → 404"""
        resp = client.get("/api/v1/qa/sessions/nonexistent-id")
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "SESSION_NOT_FOUND"


class TestQAAPIDeleteSession:
    """DELETE /api/v1/qa/sessions/<session_id>"""

    def test_delete_session_success(self, client):
        """正常删除 → 204"""
        create_resp = client.post("/api/v1/qa/sessions", json={
            "report_ids": ["test-report-1"],
        })
        session_id = create_resp.get_json()["session_id"]
        resp = client.delete(f"/api/v1/qa/sessions/{session_id}")
        assert resp.status_code == 204

    def test_delete_session_not_found(self, client):
        """不存在的 session_id → 404"""
        resp = client.delete("/api/v1/qa/sessions/nonexistent-id")
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "SESSION_NOT_FOUND"


class TestQAAPISendMessage:
    """POST /api/v1/qa/sessions/<session_id>/messages"""

    def test_send_message_empty_question(self, client):
        """question 为空 → 400"""
        create_resp = client.post("/api/v1/qa/sessions", json={
            "report_ids": ["test-report-1"],
        })
        session_id = create_resp.get_json()["session_id"]
        resp = client.post(f"/api/v1/qa/sessions/{session_id}/messages", json={
            "question": "",
        })
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "QUESTION_EMPTY"

    def test_send_message_missing_question(self, client):
        """缺少 question 字段 → 400"""
        create_resp = client.post("/api/v1/qa/sessions", json={
            "report_ids": ["test-report-1"],
        })
        session_id = create_resp.get_json()["session_id"]
        resp = client.post(f"/api/v1/qa/sessions/{session_id}/messages", json={})
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "QUESTION_EMPTY"

    def test_send_message_session_not_found(self, client):
        """session 不存在 → 404"""
        resp = client.post("/api/v1/qa/sessions/nonexistent-id/messages", json={
            "question": "测试问题",
        })
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "SESSION_NOT_FOUND"

    def test_send_message_success(self, client, app):
        """正常发送（mock LLM）→ 200"""
        create_resp = client.post("/api/v1/qa/sessions", json={
            "report_ids": ["test-report-1"],
        })
        session_id = create_resp.get_json()["session_id"]

        # mock qa_service 的 ask 方法来避免实际 LLM 调用
        mock_answer = {
            "id": "msg-1",
            "role": "assistant",
            "content": "根据研报，目标价1900元。",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "source_type": "report_based",
            "sources": [{"report_id": "test-report-1", "report_title": "贵州茅台投资分析", "quote": "茅台提价利好"}],
        }
        with patch.object(app.config["qa_service"], "ask", return_value=mock_answer):
            resp = client.post(f"/api/v1/qa/sessions/{session_id}/messages", json={
                "question": "茅台目标价是多少？",
            })
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["role"] == "assistant"
        assert "content" in body
        assert body["source_type"] == "report_based"
        assert len(body["sources"]) > 0
        assert "traceId" in body
