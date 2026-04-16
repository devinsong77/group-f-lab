"""QA Blueprint — multi-report Q&A session management."""
from __future__ import annotations

import logging
import uuid

import json

from flask import Blueprint, Response, request, jsonify, current_app

logger = logging.getLogger(__name__)

qa_bp = Blueprint("qa", __name__)


def _trace_id():
    tid = request.headers.get("X-Trace-Id")
    if not tid:
        tid = f"tr_{uuid.uuid4().hex}"
    return tid


def _error(code: str, message: str, status: int, details: dict | None = None):
    return jsonify({
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "traceId": _trace_id(),
        }
    }), status


ERROR_MAP: dict[str, tuple[str, int]] = {
    "REPORTS_NOT_FOUND":  ("研报不存在", 404),
    "REPORTS_NOT_PARSED": ("研报未解析完成", 400),
    "SESSION_NOT_FOUND":  ("会话不存在", 404),
}


# ── POST /api/v1/qa/sessions ────────────────────────────────

@qa_bp.route("/qa/sessions", methods=["POST"])
def create_session():
    qa_service = current_app.config["qa_service"]

    data = request.get_json(silent=True) or {}
    report_ids = data.get("report_ids")

    if not isinstance(report_ids, list) or len(report_ids) == 0:
        return _error("INVALID_PARAMS", "report_ids 必须是非空数组", 400)

    try:
        session = qa_service.create_session(report_ids)
        return jsonify({
            "traceId": _trace_id(),
            **session,
        }), 201
    except ValueError as e:
        err_code = str(e)
        msg, status = ERROR_MAP.get(err_code, ("未知错误", 400))
        return _error(err_code, msg, status)


# ── GET /api/v1/qa/sessions ─────────────────────────────────

@qa_bp.route("/qa/sessions", methods=["GET"])
def list_sessions():
    qa_service = current_app.config["qa_service"]

    sessions = qa_service.list_sessions()
    return jsonify({
        "traceId": _trace_id(),
        "sessions": sessions,
    }), 200


# ── GET /api/v1/qa/sessions/<session_id> ────────────────────

@qa_bp.route("/qa/sessions/<session_id>", methods=["GET"])
def get_session(session_id):
    qa_service = current_app.config["qa_service"]

    try:
        session = qa_service.get_session(session_id)
        return jsonify({
            "traceId": _trace_id(),
            **session,
        }), 200
    except ValueError as e:
        err_code = str(e)
        msg, status = ERROR_MAP.get(err_code, ("未知错误", 400))
        return _error(err_code, msg, status)


# ── DELETE /api/v1/qa/sessions/<session_id> ─────────────────

@qa_bp.route("/qa/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    qa_service = current_app.config["qa_service"]

    try:
        qa_service.delete_session(session_id)
        return "", 204
    except ValueError as e:
        err_code = str(e)
        msg, status = ERROR_MAP.get(err_code, ("未知错误", 400))
        return _error(err_code, msg, status)


# ── POST /api/v1/qa/sessions/<session_id>/messages ──────────

@qa_bp.route("/qa/sessions/<session_id>/messages", methods=["POST"])
def send_message(session_id):
    qa_service = current_app.config["qa_service"]

    data = request.get_json(silent=True) or {}
    question = data.get("question", "")

    if not isinstance(question, str) or len(question.strip()) == 0:
        return _error("QUESTION_EMPTY", "问题不能为空", 400)

    question = question.strip()
    if len(question) > 2000:
        return _error("QUESTION_TOO_LONG", "问题长度不能超过 2000 字符", 400)

    # 判断是否请求流式响应
    want_stream = (
        request.args.get("stream", "").lower() == "true"
        or "text/event-stream" in request.headers.get("Accept", "")
    )

    if want_stream:
        def generate():
            try:
                for chunk in qa_service.ask_stream(session_id, question):
                    yield chunk
            except ValueError as e:
                error_msg = str(e)
                yield f"data: {json.dumps({'type': 'error', 'message': error_msg}, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.exception("QA stream error for session %s", session_id)
                yield f"data: {json.dumps({'type': 'error', 'message': 'QA_FAILED'}, ensure_ascii=False)}\n\n"

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    # 非流式逻辑保持不变
    try:
        answer = qa_service.ask(session_id, question)
        return jsonify({
            "traceId": _trace_id(),
            **answer,
        }), 200
    except ValueError as e:
        err_code = str(e)
        msg, status = ERROR_MAP.get(err_code, ("未知错误", 400))
        return _error(err_code, msg, status)
    except RuntimeError as e:
        logger.error("QA failed for session %s: %s", session_id, e)
        return _error("QA_FAILED", "问答服务暂时不可用，请稍后重试", 500)
