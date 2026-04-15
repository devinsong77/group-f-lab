"""
知识库 API 路由 — kb_bp

Task2 提供: GET /kb/stocks, GET /kb/stocks/{code}, GET /kb/stocks/{code}/reports

对齐规格: 09-API接口规格 §9~§10
"""

from __future__ import annotations

import uuid

from flask import Blueprint, current_app, jsonify, request

kb_bp = Blueprint("kb_bp", __name__)


def _get_trace_id() -> str:
    """生成或复用 traceId (对齐 07 §3.1)"""
    trace_id = request.headers.get("X-Trace-Id")
    if not trace_id:
        trace_id = f"tr_{uuid.uuid4().hex}"
    return trace_id


def _error_response(code: str, message: str, status: int, details: dict | None = None):
    """统一错误响应格式 (对齐 09 §2)"""
    return jsonify({
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "traceId": _get_trace_id(),
        }
    }), status


@kb_bp.route("/kb/stocks", methods=["GET"])
def list_stocks():
    """GET /api/v1/kb/stocks — 知识库股票列表 (对齐 09 §9)"""
    trace_id = _get_trace_id()
    kb_manager = current_app.config["kb_manager"]

    stocks = kb_manager.get_stocks()

    return jsonify({
        "traceId": trace_id,
        "stocks": stocks,
    }), 200


@kb_bp.route("/kb/stocks/<stock_code>", methods=["GET"])
def get_stock_detail(stock_code: str):
    """GET /api/v1/kb/stocks/{code} — 股票知识库详情 (对齐 09 §10)"""
    trace_id = _get_trace_id()
    kb_manager = current_app.config["kb_manager"]

    detail = kb_manager.get_stock_detail(stock_code)
    if detail is None:
        return _error_response("STOCK_NOT_FOUND", "未找到该股票的知识库数据", 404)

    return jsonify({
        "traceId": trace_id,
        **detail,
    }), 200


@kb_bp.route("/kb/stocks/<stock_code>/reports", methods=["GET"])
def get_stock_reports(stock_code: str):
    """GET /api/v1/kb/stocks/{code}/reports — 股票关联研报 (对齐 09 §10 补充)"""
    trace_id = _get_trace_id()
    kb_manager = current_app.config["kb_manager"]
    storage = current_app.config["storage"]

    # 校验股票存在
    stock_detail = storage.get_stock_detail(stock_code)
    if stock_detail is None:
        return _error_response("STOCK_NOT_FOUND", "未找到该股票的知识库数据", 404)

    # 获取排序参数
    sort_by = request.args.get("sort_by", "upload_time")
    order = request.args.get("order", "desc")

    reports = kb_manager.get_stock_reports(stock_code, sort_by, order)

    return jsonify({
        "traceId": trace_id,
        "stock_code": stock_code,
        "reports": reports,
    }), 200
