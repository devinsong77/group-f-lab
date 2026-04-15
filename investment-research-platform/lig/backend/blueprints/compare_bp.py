import uuid

from flask import Blueprint, request, jsonify, current_app

compare_bp = Blueprint("compare_bp", __name__)


def _trace_id():
    tid = request.headers.get("X-Trace-Id")
    if not tid:
        tid = f"tr_{uuid.uuid4().hex}"
    return tid


def _error(code, message, http_status, trace_id):
    return jsonify({"error": {"code": code, "message": message, "traceId": trace_id}}), http_status


ERROR_MESSAGES = {
    "COMPARE_MIN_REPORTS": ("至少选择 2 份研报进行比对", 400),
    "COMPARE_DIFF_STOCK": ("比对研报必须属于同一公司", 400),
    "REPORT_NOT_FOUND": ("部分研报不存在", 404),
    "LLM_ERROR": ("AI 服务暂时不可用，请稍后重试", 500),
}


@compare_bp.route("/reports/compare", methods=["POST"])
def compare_reports():
    trace_id = _trace_id()
    comparator = current_app.config["comparator"]

    data = request.get_json(silent=True)
    if not data or "report_ids" not in data:
        return _error("COMPARE_MIN_REPORTS", "至少选择 2 份研报进行比对", 400, trace_id)

    report_ids = data["report_ids"]
    valid, err_code = comparator.validate(report_ids)
    if not valid:
        msg, status = ERROR_MESSAGES.get(err_code, ("未知错误", 400))
        return _error(err_code, msg, status, trace_id)

    try:
        result = comparator.compare(report_ids)
        result["traceId"] = trace_id
        return jsonify(result), 200
    except Exception as e:
        return _error("LLM_ERROR", "AI 服务暂时不可用，请稍后重试", 500, trace_id)


@compare_bp.route("/stocks/<code>/market-data", methods=["GET"])
def get_market_data(code):
    trace_id = _trace_id()
    stock_data_service = current_app.config["stock_data_service"]
    storage = current_app.config["storage"]

    stock = storage.get_stock(code)
    stock_name = stock.get("stock_name", "") if stock else ""

    data = stock_data_service.get_market_data(code)
    data["stock_name"] = stock_name
    data["traceId"] = trace_id
    return jsonify(data), 200
