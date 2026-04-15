import uuid

from flask import Blueprint, request, jsonify, current_app

kb_bp = Blueprint("kb_bp", __name__)


def _trace_id():
    tid = request.headers.get("X-Trace-Id")
    if not tid:
        tid = f"tr_{uuid.uuid4().hex}"
    return tid


def _error(code, message, http_status, trace_id):
    return jsonify({"error": {"code": code, "message": message, "traceId": trace_id}}), http_status


@kb_bp.route("/kb/stocks", methods=["GET"])
def list_stocks():
    trace_id = _trace_id()
    kb_manager = current_app.config["kb_manager"]
    stocks = kb_manager.get_stocks()
    return jsonify({"traceId": trace_id, "stocks": stocks}), 200


@kb_bp.route("/kb/stocks/<code>", methods=["GET"])
def get_stock_detail(code):
    trace_id = _trace_id()
    kb_manager = current_app.config["kb_manager"]
    detail = kb_manager.get_stock_detail(code)
    if not detail:
        return _error("STOCK_NOT_FOUND", "未找到该股票的知识库数据", 404, trace_id)
    detail["traceId"] = trace_id
    return jsonify(detail), 200


@kb_bp.route("/kb/stocks/<code>/reports", methods=["GET"])
def get_stock_reports(code):
    trace_id = _trace_id()
    kb_manager = current_app.config["kb_manager"]

    sort_by = request.args.get("sort_by", "upload_time")
    order = request.args.get("order", "desc")
    reports = kb_manager.get_stock_reports(code, sort_by=sort_by, order=order)
    return jsonify({"traceId": trace_id, "reports": reports}), 200
