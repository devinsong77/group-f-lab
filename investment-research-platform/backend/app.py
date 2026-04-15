"""
Flask 应用入口 — app.py

注册所有 Blueprint、初始化 Storage 和引擎实例
对齐规格: 08-系统架构与技术选型

Task1 注册: report_bp
Task2 注册: kb_bp + KnowledgeBaseManager
Task3 注册: compare_bp (预留)
"""

from __future__ import annotations

import os

from flask import Flask
from flask_cors import CORS

from backend.blueprints.kb_bp import kb_bp
from backend.blueprints.report_bp import report_bp
from backend.knowledge_base import KnowledgeBaseManager
from backend.storage import Storage


def create_app(config: dict | None = None) -> Flask:
    """
    Flask 应用工厂

    Args:
        config: 可选的配置覆盖（用于测试等场景）
    """
    app = Flask(__name__)

    # ── 配置项（从环境变量读取，对齐 Task1 §5）──
    data_dir = os.environ.get("DATA_DIR", "data")
    if config:
        data_dir = config.get("DATA_DIR", data_dir)

    # ── CORS 全开放（对齐 07 §4）──
    CORS(app)

    # ── 初始化 Storage 单例 ──
    storage = Storage(data_dir=data_dir)
    app.config["storage"] = storage

    # ── 初始化 KnowledgeBaseManager (Task2) ──
    # llm_client 可选，无 LLM 时使用降级方案
    llm_client = None
    # 如果 Task1 的 parser 中初始化了 LLM client，可在此处共享
    # llm_client = ... (由 app 配置或 Task1 提供)
    kb_manager = KnowledgeBaseManager(storage=storage, llm_client=llm_client)
    app.config["kb_manager"] = kb_manager

    # ── 初始化 Parser 引擎 (Task1 提供) ──
    # parser 由 Task1 实现并在此处初始化
    # app.config["parser"] = ReportParser(...)
    # 此处预留，Task1 合并时补充
    app.config["parser"] = None

    # ── 注册 Blueprint ──
    app.register_blueprint(report_bp, url_prefix="/api/v1")  # Task1 + Task2
    app.register_blueprint(kb_bp, url_prefix="/api/v1")      # Task2

    # Task3 预留:
    # from backend.blueprints.compare_bp import compare_bp
    # app.register_blueprint(compare_bp, url_prefix="/api/v1")

    return app


# ── 直接运行入口 ──
if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
