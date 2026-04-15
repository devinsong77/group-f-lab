"""Report Blueprint — upload, parse, list, detail, delete, download."""
from __future__ import annotations

import os
import uuid

from flask import Blueprint, request, jsonify, send_file, current_app

report_bp = Blueprint("report", __name__)


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


# ── POST /api/v1/reports/upload ──────────────────────────────

@report_bp.route("/reports/upload", methods=["POST"])
def upload_report():
    storage = current_app.config["storage"]

    if "file" not in request.files:
        return _error("INVALID_FILE_TYPE", "仅支持 PDF 格式文件", 400)

    file = request.files["file"]
    if not file.filename:
        return _error("INVALID_FILE_TYPE", "仅支持 PDF 格式文件", 400)

    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        return _error("INVALID_FILE_TYPE", "仅支持 PDF 格式文件", 400)

    # Validate file size (50MB)
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > 50 * 1024 * 1024:
        return _error("FILE_TOO_LARGE", "文件大小不能超过 50MB", 400)

    report_id = str(uuid.uuid4())
    file_path = os.path.join(storage.reports_dir, f"{report_id}.pdf")
    file.save(file_path)

    report = storage.save_report(report_id, file.filename, file_path)

    return jsonify({
        "traceId": _trace_id(),
        **report,
    }), 201


# ── POST /api/v1/reports/<id>/parse ──────────────────────────

@report_bp.route("/reports/<report_id>/parse", methods=["POST"])
def parse_report(report_id):
    storage = current_app.config["storage"]
    parser = current_app.config["parser"]

    report = storage.get_report(report_id)
    if report is None:
        return _error("REPORT_NOT_FOUND", "研报不存在或已被删除", 404)

    storage.update_report_status(report_id, "parsing")

    try:
        result = parser.process(report["file_path"])
        parsed = storage.save_parsed_report(report_id, result)

        # Generate summary for the stock
        kb_manager = current_app.config.get("kb_manager")
        if kb_manager and result.get("stock_code"):
            try:
                kb_manager.generate_summary(result["stock_code"])
            except Exception:
                pass

        return jsonify({
            "traceId": _trace_id(),
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
        }), 200
    except Exception as e:
        import traceback
        current_app.logger.error("Parse failed for %s: %s\n%s", report_id, e, traceback.format_exc())
        storage.update_report_status(report_id, "failed")
        err_type = type(e).__name__
        if "LLM" in err_type:
            return _error("LLM_ERROR", f"AI 服务暂时不可用: {e}", 500)
        return _error("PARSE_FAILED", f"研报解析失败: {e}", 500)


# ── GET /api/v1/reports ──────────────────────────────────────

@report_bp.route("/reports", methods=["GET"])
def list_reports():
    storage = current_app.config["storage"]

    filters = {}
    for key in ("stock_code", "industry", "date_from", "date_to"):
        val = request.args.get(key)
        if val:
            filters[key] = val

    reports = storage.get_reports(filters if filters else None)

    return jsonify({
        "traceId": _trace_id(),
        "reports": reports,
    }), 200


# ── GET /api/v1/reports/<id> ─────────────────────────────────

@report_bp.route("/reports/<report_id>", methods=["GET"])
def get_report(report_id):
    storage = current_app.config["storage"]

    report = storage.get_report(report_id)
    if report is None:
        return _error("REPORT_NOT_FOUND", "研报不存在或已被删除", 404)

    parsed = storage.get_parsed_report(report_id) or {}
    detail = {**report, **parsed}

    return jsonify({
        "traceId": _trace_id(),
        **detail,
    }), 200


# ── DELETE /api/v1/reports/<id> ──────────────────────────────

@report_bp.route("/reports/<report_id>", methods=["DELETE"])
def delete_report(report_id):
    storage = current_app.config["storage"]

    report = storage.get_report(report_id)
    if report is None:
        return _error("REPORT_NOT_FOUND", "研报不存在或已被删除", 404)

    # Get stock_code before deletion for summary regeneration
    parsed = storage.get_parsed_report(report_id) or {}
    stock_code = parsed.get("stock_code")

    storage.delete_report(report_id)

    # Regenerate summary if stock still exists
    if stock_code:
        kb_manager = current_app.config.get("kb_manager")
        if kb_manager:
            try:
                kb_manager.generate_summary(stock_code)
            except Exception:
                pass

    return jsonify({
        "traceId": _trace_id(),
        "message": "删除成功",
        "report_id": report_id,
    }), 200


# ── GET /api/v1/reports/<id>/file ────────────────────────────

@report_bp.route("/reports/<report_id>/file", methods=["GET"])
def download_report_file(report_id):
    storage = current_app.config["storage"]

    report = storage.get_report(report_id)
    if report is None:
        return _error("REPORT_NOT_FOUND", "研报不存在或已被删除", 404)

    file_path = report.get("file_path", "")
    if not file_path or not os.path.exists(file_path):
        return _error("REPORT_NOT_FOUND", "研报文件不存在", 404)

    return send_file(
        file_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=report.get("filename", "report.pdf"),
    )
