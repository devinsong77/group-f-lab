"""
研报管理 API 路由 — report_bp

Task1 提供: POST /reports/upload, POST /reports/{id}/parse
Task2 扩展: GET /reports, GET /reports/{id}, DELETE /reports/{id}, GET /reports/{id}/file

对齐规格: 09-API接口规格 §3~§7
"""

from __future__ import annotations

import os
import uuid

from flask import Blueprint, current_app, jsonify, request, send_file

report_bp = Blueprint("report_bp", __name__)


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


# ══════════════════════════════════════════════
# Task1 — 研报上传与解析路由
# ══════════════════════════════════════════════

@report_bp.route("/reports/upload", methods=["POST"])
def upload_report():
    """POST /api/v1/reports/upload — 上传研报 (对齐 09 §3)"""
    trace_id = _get_trace_id()
    storage = current_app.config["storage"]

    # 校验文件存在
    if "file" not in request.files:
        return _error_response(
            "INVALID_FILE_TYPE", "仅支持 PDF 格式文件", 400,
            {"allowed": ["application/pdf"]}
        )

    file = request.files["file"]

    # 校验文件类型
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return _error_response(
            "INVALID_FILE_TYPE", "仅支持 PDF 格式文件", 400,
            {"allowed": ["application/pdf"]}
        )

    # 校验文件大小（50MB）
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > 50 * 1024 * 1024:
        return _error_response(
            "FILE_TOO_LARGE", "文件大小不能超过 50MB", 400,
            {"max_size_mb": 50}
        )

    # 生成 report_id
    report_id = str(uuid.uuid4())

    # 保存 PDF 文件
    file_path = os.path.join(storage.reports_dir, f"{report_id}.pdf")
    file.save(file_path)

    # 保存元数据
    report = storage.save_report(report_id, file.filename, file_path)

    return jsonify({
        "traceId": trace_id,
        "report_id": report["report_id"],
        "filename": report["filename"],
        "file_path": report["file_path"],
        "upload_time": report["upload_time"],
        "parse_status": report["parse_status"],
    }), 201


@report_bp.route("/reports/<report_id>/parse", methods=["POST"])
def parse_report(report_id: str):
    """POST /api/v1/reports/{id}/parse — 触发解析 (对齐 09 §4)"""
    trace_id = _get_trace_id()
    storage = current_app.config["storage"]
    parser = current_app.config.get("parser")

    # 校验研报存在
    report = storage.get_report(report_id)
    if report is None:
        return _error_response("REPORT_NOT_FOUND", "研报不存在", 404)

    # 更新状态为 parsing
    storage.update_report_status(report_id, "parsing")

    try:
        # 调用 Parser 引擎（由 Task1 提供）
        if parser is None:
            return _error_response(
                "PARSE_FAILED", "解析引擎未初始化", 500,
                {"reason": "Parser not configured"}
            )

        result = parser.process(report["file_path"])

        # 保存解析结果（含自动入知识库）
        parsed = storage.save_parsed_report(report_id, result)

        # 生成/更新观点汇总
        kb_manager = current_app.config.get("kb_manager")
        if kb_manager and parsed.get("stock_code"):
            kb_manager.generate_summary(parsed["stock_code"])

        return jsonify({
            "traceId": trace_id,
            "report_id": report_id,
            "parse_status": "completed",
            "title": parsed["title"],
            "rating": parsed["rating"],
            "target_price": parsed["target_price"],
            "key_points": parsed["key_points"],
            "stock_code": parsed["stock_code"],
            "stock_name": parsed["stock_name"],
            "industry": parsed["industry"],
            "parse_time_ms": parsed["parse_time_ms"],
        }), 200

    except Exception as e:
        storage.update_report_status(report_id, "failed")
        error_code = "LLM_ERROR" if "LLM" in str(e) else "PARSE_FAILED"
        return _error_response(
            error_code, "研报解析失败", 500,
            {"reason": str(e)}
        )


# ══════════════════════════════════════════════
# Task2 — 研报管理扩展路由
# ══════════════════════════════════════════════

@report_bp.route("/reports", methods=["GET"])
def list_reports():
    """GET /api/v1/reports — 研报列表 (对齐 09 §5)"""
    trace_id = _get_trace_id()
    storage = current_app.config["storage"]

    # 获取筛选参数
    filters = {}
    stock_code = request.args.get("stock_code")
    industry = request.args.get("industry")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    if stock_code:
        filters["stock_code"] = stock_code
    if industry:
        filters["industry"] = industry
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to

    reports = storage.get_reports(filters if filters else None)

    return jsonify({
        "traceId": trace_id,
        "reports": reports,
    }), 200


@report_bp.route("/reports/<report_id>", methods=["GET"])
def get_report_detail(report_id: str):
    """GET /api/v1/reports/{id} — 研报详情 (对齐 09 §6)"""
    trace_id = _get_trace_id()
    storage = current_app.config["storage"]

    detail = storage.get_report_detail(report_id)
    if detail is None:
        return _error_response("REPORT_NOT_FOUND", "研报不存在", 404)

    return jsonify({
        "traceId": trace_id,
        **detail,
    }), 200


@report_bp.route("/reports/<report_id>", methods=["DELETE"])
def delete_report(report_id: str):
    """DELETE /api/v1/reports/{id} — 删除研报 (对齐 09 §7)"""
    trace_id = _get_trace_id()
    storage = current_app.config["storage"]

    # 校验研报存在
    report = storage.get_report(report_id)
    if report is None:
        return _error_response("REPORT_NOT_FOUND", "研报不存在", 404)

    # 获取 stock_code（级联删除后需要更新观点汇总）
    parsed = storage.get_parsed_report(report_id)
    stock_code = parsed.get("stock_code") if parsed else None

    # 执行级联删除
    storage.delete_report(report_id)

    # 重新生成受影响股票的观点汇总
    kb_manager = current_app.config.get("kb_manager")
    if kb_manager and stock_code:
        # 检查股票是否仍存在（可能已被级联删除）
        stock_detail = storage.get_stock_detail(stock_code)
        if stock_detail:
            kb_manager.generate_summary(stock_code)

    return jsonify({
        "traceId": trace_id,
        "message": "删除成功",
        "report_id": report_id,
    }), 200


@report_bp.route("/reports/<report_id>/file", methods=["GET"])
def download_report_file(report_id: str):
    """GET /api/v1/reports/{id}/file — 下载原文 (对齐 09 §6 补充)"""
    storage = current_app.config["storage"]

    report = storage.get_report(report_id)
    if report is None:
        return _error_response("REPORT_NOT_FOUND", "研报不存在", 404)

    file_path = storage.get_report_file_path(report_id)
    if file_path is None:
        return _error_response("REPORT_NOT_FOUND", "研报文件不存在", 404)

    return send_file(
        file_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=report.get("filename", f"{report_id}.pdf"),
    )
