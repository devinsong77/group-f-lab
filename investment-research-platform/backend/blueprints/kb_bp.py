"""Knowledge Base Blueprint — stock aggregation APIs."""
from __future__ import annotations

import uuid

from flask import Blueprint, request, jsonify, current_app

kb_bp = Blueprint("kb", __name__)


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


# ── GET /api/v1/kb/stocks ────────────────────────────────────

@kb_bp.route("/kb/stocks", methods=["GET"])
def list_stocks():
    kb_manager = current_app.config["kb_manager"]
    stocks = kb_manager.get_stocks()
    return jsonify({
        "traceId": _trace_id(),
        "stocks": stocks,
    }), 200


# ── GET /api/v1/kb/stocks/<code> ─────────────────────────────

@kb_bp.route("/kb/stocks/<stock_code>", methods=["GET"])
def get_stock_detail(stock_code):
    kb_manager = current_app.config["kb_manager"]
    detail = kb_manager.get_stock_detail(stock_code)
    if detail is None:
        return _error("STOCK_NOT_FOUND", "未找到该股票的知识库数据", 404)
    return jsonify({
        "traceId": _trace_id(),
        **detail,
    }), 200


# ── GET /api/v1/kb/stocks/<code>/reports ─────────────────────

@kb_bp.route("/kb/stocks/<stock_code>/reports", methods=["GET"])
def get_stock_reports(stock_code):
    kb_manager = current_app.config["kb_manager"]
    sort_by = request.args.get("sort_by", "upload_time")
    order = request.args.get("order", "desc")
    reports = kb_manager.get_stock_reports(stock_code, sort_by=sort_by, order=order)
    return jsonify({
        "traceId": _trace_id(),
        "reports": reports,
    }), 200
