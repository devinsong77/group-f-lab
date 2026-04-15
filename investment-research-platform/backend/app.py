"""Flask application entry point."""

import os

from flask import Flask
from flask_cors import CORS

from storage import Storage
from parser import ReportParser
from knowledge_base import KnowledgeBaseManager
from comparator import ReportComparator
from stock_data import StockDataService
from blueprints.report_bp import report_bp
from blueprints.kb_bp import kb_bp
from blueprints.compare_bp import compare_bp


def create_app(data_dir=None, test_mode=False):
    app = Flask(__name__)
    CORS(app)

    # Configuration
    if data_dir is None:
        data_dir = os.environ.get("DATA_DIR", "data")

    llm_api_key = os.environ.get("LLM_API_KEY", "sk-f47c2e9de62c4375800379e938e2c25b")
    llm_base_url = os.environ.get("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    llm_model = os.environ.get("LLM_MODEL", "qwen3.5-plus")
    llm_fallback_model = os.environ.get("LLM_FALLBACK_MODEL", "glm-4-flash")

    # Create shared LLM client for components that need it
    llm_client = None
    if llm_api_key and not test_mode:
        try:
            from openai import OpenAI
            llm_client = OpenAI(api_key=llm_api_key, base_url=llm_base_url)
        except ImportError:
            pass

    # Initialize components
    storage = Storage(data_dir=data_dir)
    parser = ReportParser(
        llm_api_key=llm_api_key if not test_mode else None,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        llm_fallback_model=llm_fallback_model,
    )
    kb_manager = KnowledgeBaseManager(
        storage=storage,
        llm_client=llm_client,
        llm_model=llm_model,
    )
    # Comparator uses lighter qwen-plus (much faster for structured JSON tasks)
    llm_compare_model = os.environ.get("LLM_COMPARE_MODEL", "qwen-plus")
    comparator = ReportComparator(
        storage=storage,
        llm_client=llm_client,
        llm_model=llm_compare_model,
        llm_fallback_model=llm_fallback_model,
    )
    stock_data_service = StockDataService()

    # Inject into app config
    app.config["storage"] = storage
    app.config["parser"] = parser
    app.config["kb_manager"] = kb_manager
    app.config["comparator"] = comparator
    app.config["stock_data_service"] = stock_data_service

    # Register blueprints
    app.register_blueprint(report_bp, url_prefix="/api/v1")
    app.register_blueprint(kb_bp, url_prefix="/api/v1")
    app.register_blueprint(compare_bp, url_prefix="/api/v1")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5002, debug=True)
