"""
Flask 应用入口
对齐 spec/08-系统架构与技术选型.md §1.1
"""

import os
from flask import Flask
from flask_cors import CORS

from storage import Storage
from parser import ReportParser
from blueprints.report_bp import report_bp


def create_app(test_config=None):
    """
    创建 Flask 应用
    
    Args:
        test_config: 测试配置（可选）
        
    Returns:
        Flask 应用实例
    """
    app = Flask(__name__)
    
    # ==================== 配置 ====================
    
    # 从环境变量读取配置
    app.config['LLM_API_KEY'] = os.environ.get('LLM_API_KEY')
    app.config['LLM_BASE_URL'] = os.environ.get(
        'LLM_BASE_URL', 
        'https://dashscope.aliyuncs.com/compatible-mode/v1'
    )
    app.config['LLM_MODEL'] = os.environ.get('LLM_MODEL', 'qwen-plus')
    app.config['DATA_DIR'] = os.environ.get('DATA_DIR', 'data')
    
    # 测试配置覆盖
    if test_config:
        app.config.update(test_config)
    
    # ==================== CORS ====================
    
    # 全开放 CORS（对齐 spec/07-非功能需求与约束.md §4）
    CORS(app, resources={
        r"/api/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-Trace-Id"]
        }
    })
    
    # ==================== 初始化 Storage ====================
    
    storage = Storage(data_dir=app.config['DATA_DIR'])
    app.config['STORAGE'] = storage
    
    # ==================== 初始化 Parser ====================
    
    parser = ReportParser(
        llm_api_key=app.config['LLM_API_KEY'],
        llm_base_url=app.config['LLM_BASE_URL'],
        llm_model=app.config['LLM_MODEL']
    )
    app.config['PARSER'] = parser
    
    # ==================== 注册 Blueprints ====================
    
    # 研报相关路由
    app.register_blueprint(report_bp, url_prefix='/api/v1')
    
    # 注意：以下 Blueprints 由其他 Task 实现
    # - kb_bp: 知识库路由 (Task2)
    # - compare_bp: 研报比对路由 (Task3)
    
    # ==================== 健康检查 ====================
    
    @app.route('/health', methods=['GET'])
    def health_check():
        """健康检查端点"""
        return {
            "status": "healthy",
            "storage_initialized": True,
            "parser_initialized": parser._llm_client is not None
        }
    
    @app.route('/', methods=['GET'])
    def index():
        """根路径 - API 信息"""
        return {
            "name": "投研分析平台 API",
            "version": "v1",
            "base_url": "/api/v1",
            "endpoints": [
                "POST /api/v1/reports/upload",
                "GET  /api/v1/reports",
                "GET  /api/v1/reports/{id}",
                "DELETE /api/v1/reports/{id}",
                "POST /api/v1/reports/{id}/parse",
                "GET  /api/v1/reports/{id}/file",
                # 以下端点由其他 Task 实现：
                # "GET  /api/v1/kb/stocks",
                # "GET  /api/v1/kb/stocks/{code}",
                # "POST /api/v1/reports/compare",
                # "GET  /api/v1/stocks/{code}/market-data"
            ]
        }
    
    return app


# 创建应用实例（用于生产部署）
app = create_app()


if __name__ == '__main__':
    # 开发服务器启动
    # 生产环境应使用: flask --app app run
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
