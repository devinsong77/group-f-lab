"""Compare Blueprint — report comparison + market data APIs."""
from __future__ import annotations

import uuid

from flask import Blueprint, request, jsonify, current_app

compare_bp = Blueprint("compare", __name__)


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


ERROR_MESSAGES = {
    "COMPARE_MIN_REPORTS": ("至少选择 2 份研报进行比对", 400),
    "COMPARE_DIFF_STOCK": ("比对研报必须属于同一公司", 400),
    "REPORT_NOT_FOUND": ("部分研报不存在", 404),
    "LLM_ERROR": ("AI 服务暂时不可用，请稍后重试", 500),
}


# ── POST /api/v1/reports/compare ─────────────────────────────

@compare_bp.route("/reports/compare", methods=["POST"])
def compare_reports():
    comparator = current_app.config["comparator"]

    data = request.get_json(silent=True) or {}
    report_ids = data.get("report_ids", [])

    ok, err_code = comparator.validate(report_ids)
    if not ok:
        msg, status = ERROR_MESSAGES.get(err_code, ("未知错误", 400))
        return _error(err_code, msg, status)

    try:
        result = comparator.compare(report_ids)
        return jsonify({
            "traceId": _trace_id(),
            **result,
        }), 200
    except Exception as e:
        err_type = type(e).__name__
        if "LLM" in err_type:
            return _error("LLM_ERROR", "AI 服务暂时不可用，请稍后重试", 500)
        return _error("LLM_ERROR", "AI 服务暂时不可用，请稍后重试", 500)


# ── GET /api/v1/stocks/<code>/market-data ────────────────────

@compare_bp.route("/stocks/<stock_code>/market-data", methods=["GET"])
def get_market_data(stock_code):
    stock_data_svc = current_app.config["stock_data_service"]
    storage = current_app.config["storage"]

    # Try to get stock_name from knowledge base
    stock = storage.get_stock(stock_code)
    stock_name = stock.get("stock_name", "") if stock else ""

    data = stock_data_svc.get_market_data(stock_code, stock_name=stock_name)

    return jsonify({
        "traceId": _trace_id(),
        **data,
    }), 200
