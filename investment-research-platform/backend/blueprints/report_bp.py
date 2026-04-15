"""
研报 API 路由 Blueprint
对齐 spec/09-API接口规格.md §3, §4, §5, §6, §7
"""

import os
import uuid
from flask import Blueprint, request, jsonify, current_app, send_file
from werkzeug.utils import secure_filename

from ..parser import ParseError, LLMError


# 创建 Blueprint
report_bp = Blueprint('report_bp', __name__)


# ==================== 工具函数 ====================

def generate_trace_id() -> str:
    """生成 traceId"""
    # 优先复用请求头 X-Trace-Id
    trace_id = request.headers.get('X-Trace-Id')
    if trace_id:
        return trace_id
    # 本地生成
    return f"tr_{uuid.uuid4().hex}"


def success_response(data: dict, trace_id: str) -> tuple:
    """构建成功响应"""
    response = {"traceId": trace_id}
    response.update(data)
    return jsonify(response)


def error_response(code: str, message: str, http_status: int, trace_id: str, details: dict = None) -> tuple:
    """构建错误响应"""
    error = {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "traceId": trace_id
        }
    }
    return jsonify(error), http_status


def allowed_file(filename: str) -> bool:
    """检查文件类型是否为 PDF"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'


# ==================== API 路由 ====================

@report_bp.route('/reports/upload', methods=['POST'])
def upload_report():
    """
    POST /api/v1/reports/upload - 上传研报
    
    请求: multipart/form-data, file 字段
    成功: 201 + 研报元数据
    失败: 400 INVALID_FILE_TYPE / FILE_TOO_LARGE
    """
    trace_id = generate_trace_id()
    
    # 检查文件
    if 'file' not in request.files:
        return error_response("INVALID_FILE_TYPE", "请求中缺少文件", 400, trace_id)
    
    file = request.files['file']
    if file.filename == '':
        return error_response("INVALID_FILE_TYPE", "文件名为空", 400, trace_id)
    
    # 校验文件类型
    if not allowed_file(file.filename):
        return error_response(
            "INVALID_FILE_TYPE", 
            "仅支持 PDF 格式文件", 
            400, 
            trace_id,
            {"allowed": ["application/pdf"]}
        )
    
    # 校验文件大小 (50MB = 50 * 1024 * 1024 bytes)
    MAX_FILE_SIZE = 50 * 1024 * 1024
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        return error_response(
            "FILE_TOO_LARGE", 
            "文件大小不能超过 50MB", 
            400, 
            trace_id,
            {"max_size_mb": 50}
        )
    
    # 生成 report_id 和保存路径
    report_id = str(uuid.uuid4())
    filename = secure_filename(file.filename)
    
    storage = current_app.config['STORAGE']
    pdf_path = os.path.join(storage.reports_dir, f"{report_id}.pdf")
    
    # 保存文件
    file.save(pdf_path)
    
    # 保存元数据
    report = storage.save_report(report_id, filename, pdf_path)
    
    return success_response({
        "report_id": report["report_id"],
        "filename": report["filename"],
        "file_path": report["file_path"],
        "upload_time": report["upload_time"],
        "parse_status": report["parse_status"]
    }, trace_id), 201


@report_bp.route('/reports/<report_id>/parse', methods=['POST'])
def parse_report(report_id: str):
    """
    POST /api/v1/reports/{id}/parse - 触发解析
    
    成功: 200 + 解析结果
    失败: 404 REPORT_NOT_FOUND / 500 PARSE_FAILED / LLM_ERROR
    """
    trace_id = generate_trace_id()
    storage = current_app.config['STORAGE']
    parser = current_app.config['PARSER']
    
    # 检查研报是否存在
    report = storage.get_report(report_id)
    if not report:
        return error_response("REPORT_NOT_FOUND", "研报不存在或已被删除", 404, trace_id)
    
    # 更新状态为 parsing
    storage.update_report_status(report_id, "parsing")
    
    try:
        # 执行解析
        pdf_path = report["file_path"]
        parsed_data = parser.process(pdf_path)
        
        # 保存解析结果（会自动更新知识库）
        storage.save_parsed_report(report_id, parsed_data)
        
        return success_response({
            "report_id": report_id,
            "parse_status": "completed",
            "title": parsed_data["title"],
            "rating": parsed_data["rating"],
            "target_price": parsed_data["target_price"],
            "key_points": parsed_data["key_points"],
            "stock_code": parsed_data["stock_code"],
            "stock_name": parsed_data["stock_name"],
            "industry": parsed_data["industry"],
            "parse_time_ms": parsed_data["parse_time_ms"]
        }, trace_id)
        
    except ParseError as e:
        # 解析失败，更新状态
        storage.update_report_status(report_id, "failed")
        return error_response(
            "PARSE_FAILED", 
            "研报解析失败，请检查文件格式", 
            500, 
            trace_id,
            {"reason": str(e)}
        )
        
    except LLMError as e:
        # LLM 错误，更新状态
        storage.update_report_status(report_id, "failed")
        return error_response(
            "LLM_ERROR", 
            "AI 服务暂时不可用，请稍后重试", 
            500, 
            trace_id,
            {"reason": str(e)}
        )
    
    except Exception as e:
        # 其他错误
        storage.update_report_status(report_id, "failed")
        return error_response(
            "PARSE_FAILED", 
            "研报解析失败，请检查文件格式", 
            500, 
            trace_id,
            {"reason": str(e)}
        )


@report_bp.route('/reports', methods=['GET'])
def get_reports():
    """
    GET /api/v1/reports - 研报列表
    
    查询参数: stock_code, industry, date_from, date_to
    成功: 200 + reports 数组
    """
    trace_id = generate_trace_id()
    storage = current_app.config['STORAGE']
    
    # 获取筛选参数
    filters = {}
    if request.args.get('stock_code'):
        filters['stock_code'] = request.args.get('stock_code')
    if request.args.get('industry'):
        filters['industry'] = request.args.get('industry')
    if request.args.get('date_from'):
        filters['date_from'] = request.args.get('date_from')
    if request.args.get('date_to'):
        filters['date_to'] = request.args.get('date_to')
    
    reports = storage.get_reports(filters)
    
    return success_response({"reports": reports}, trace_id)


@report_bp.route('/reports/<report_id>', methods=['GET'])
def get_report(report_id: str):
    """
    GET /api/v1/reports/{id} - 研报详情
    
    成功: 200 + 完整详情
    失败: 404 REPORT_NOT_FOUND
    """
    trace_id = generate_trace_id()
    storage = current_app.config['STORAGE']
    
    report = storage.get_report(report_id)
    if not report:
        return error_response("REPORT_NOT_FOUND", "研报不存在或已被删除", 404, trace_id)
    
    parsed = storage.get_parsed_report(report_id)
    
    # 合并返回
    result = {
        "report_id": report_id,
        "filename": report["filename"],
        "title": parsed.get("title") if parsed else None,
        "rating": parsed.get("rating") if parsed else None,
        "target_price": parsed.get("target_price") if parsed else None,
        "key_points": parsed.get("key_points") if parsed else None,
        "stock_code": parsed.get("stock_code") if parsed else None,
        "stock_name": parsed.get("stock_name") if parsed else None,
        "industry": parsed.get("industry") if parsed else None,
        "parse_status": report["parse_status"],
        "upload_time": report["upload_time"],
        "parse_time_ms": parsed.get("parse_time_ms") if parsed else None
    }
    
    return success_response(result, trace_id)


@report_bp.route('/reports/<report_id>', methods=['DELETE'])
def delete_report(report_id: str):
    """
    DELETE /api/v1/reports/{id} - 删除研报
    
    成功: 200 + 删除确认
    失败: 404 REPORT_NOT_FOUND
    """
    trace_id = generate_trace_id()
    storage = current_app.config['STORAGE']
    
    # 检查是否存在
    if not storage.get_report(report_id):
        return error_response("REPORT_NOT_FOUND", "研报不存在或已被删除", 404, trace_id)
    
    # 执行级联删除
    storage.delete_report(report_id)
    
    return success_response({
        "message": "删除成功",
        "report_id": report_id
    }, trace_id)


@report_bp.route('/reports/<report_id>/file', methods=['GET'])
def download_report(report_id: str):
    """
    GET /api/v1/reports/{id}/file - 下载 PDF 文件
    
    成功: 200 + PDF 文件流
    失败: 404 REPORT_NOT_FOUND
    """
    trace_id = generate_trace_id()
    storage = current_app.config['STORAGE']
    
    pdf_path = storage.get_pdf_path(report_id)
    if not pdf_path or not os.path.exists(pdf_path):
        return error_response("REPORT_NOT_FOUND", "研报不存在或已被删除", 404, trace_id)
    
    report = storage.get_report(report_id)
    filename = report["filename"] if report else f"{report_id}.pdf"
    
    return send_file(
        pdf_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )
