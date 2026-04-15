import os
import uuid

from flask import Blueprint, request, jsonify, send_file, current_app

report_bp = Blueprint("report_bp", __name__)


def _trace_id():
    tid = request.headers.get("X-Trace-Id")
    if not tid:
        tid = f"tr_{uuid.uuid4().hex}"
    return tid


def _error(code, message, http_status, trace_id, details=None):
    body = {"error": {"code": code, "message": message, "traceId": trace_id}}
    if details:
        body["error"]["details"] = details
    return jsonify(body), http_status


# ==================== Task1: 上传与解析 ====================

@report_bp.route("/reports/upload", methods=["POST"])
def upload_report():
    trace_id = _trace_id()
    storage = current_app.config["storage"]

    if "file" not in request.files:
        return _error("INVALID_FILE_TYPE", "仅支持 PDF 格式文件", 400, trace_id)

    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return _error("INVALID_FILE_TYPE", "仅支持 PDF 格式文件", 400, trace_id)

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > 50 * 1024 * 1024:
        return _error("FILE_TOO_LARGE", "文件大小不能超过 50MB", 400, trace_id)

    report_id = str(uuid.uuid4())
    file_path = os.path.join(storage.reports_dir, f"{report_id}.pdf")
    file.save(file_path)

    report = storage.save_report(report_id, file.filename, file_path)
    report["traceId"] = trace_id
    return jsonify(report), 201


@report_bp.route("/reports/<report_id>/parse", methods=["POST"])
def parse_report(report_id):
    trace_id = _trace_id()
    storage = current_app.config["storage"]
    parser = current_app.config["parser"]

    report = storage.get_report(report_id)
    if not report:
        return _error("REPORT_NOT_FOUND", "研报不存在或已被删除", 404, trace_id)

    storage.update_report_status(report_id, "parsing")

    try:
        result = parser.process(report["file_path"])
        parsed = storage.save_parsed_report(report_id, result)
        resp = {
            "traceId": trace_id,
            "report_id": report_id,
            "parse_status": "completed",
            "title": parsed.get("title", ""),
            "rating": parsed.get("rating", ""),
            "target_price": parsed.get("target_price"),
            "key_points": parsed.get("key_points", ""),
            "stock_code": parsed.get("stock_code", ""),
            "stock_name": parsed.get("stock_name", ""),
            "industry": parsed.get("industry", ""),
            "parse_time_ms": parsed.get("parse_time_ms", 0),
        }
        return jsonify(resp), 200
    except Exception as e:
        storage.update_report_status(report_id, "failed")
        err_type = type(e).__name__
        if "LLM" in err_type:
            return _error("LLM_ERROR", "AI 服务暂时不可用，请稍后重试", 500, trace_id)
        return _error("PARSE_FAILED", "研报解析失败，请检查文件格式", 500, trace_id)


# ==================== Task2: 研报管理 ====================

@report_bp.route("/reports", methods=["GET"])
def list_reports():
    trace_id = _trace_id()
    storage = current_app.config["storage"]

    filters = {}
    for key in ("stock_code", "industry", "date_from", "date_to"):
        val = request.args.get(key)
        if val:
            filters[key] = val

    reports = storage.get_reports(filters if filters else None)
    return jsonify({"traceId": trace_id, "reports": reports}), 200


@report_bp.route("/reports/<report_id>", methods=["GET"])
def get_report(report_id):
    trace_id = _trace_id()
    storage = current_app.config["storage"]

    report = storage.get_report(report_id)
    if not report:
        return _error("REPORT_NOT_FOUND", "研报不存在或已被删除", 404, trace_id)

    parsed = storage.get_parsed_report(report_id) or {}
    result = {**report, **parsed, "traceId": trace_id}
    return jsonify(result), 200


@report_bp.route("/reports/<report_id>", methods=["DELETE"])
def delete_report(report_id):
    trace_id = _trace_id()
    storage = current_app.config["storage"]

    report = storage.get_report(report_id)
    if not report:
        return _error("REPORT_NOT_FOUND", "研报不存在或已被删除", 404, trace_id)

    storage.delete_report(report_id)
    return jsonify({"traceId": trace_id, "message": "删除成功", "report_id": report_id}), 200


@report_bp.route("/reports/<report_id>/file", methods=["GET"])
def download_report_file(report_id):
    trace_id = _trace_id()
    storage = current_app.config["storage"]

    report = storage.get_report(report_id)
    if not report:
        return _error("REPORT_NOT_FOUND", "研报不存在或已被删除", 404, trace_id)

    file_path = report.get("file_path", "")
    if not os.path.exists(file_path):
        return _error("REPORT_NOT_FOUND", "研报文件不存在", 404, trace_id)

    return send_file(file_path, mimetype="application/pdf", as_attachment=True,
                     download_name=report.get("filename", "report.pdf"))
