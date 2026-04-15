import os
import logging
import tkinter as tk
from tkinter import messagebox

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

logging.basicConfig(level=logging.INFO)


def create_app(data_dir=None):
    app = Flask(__name__)

    if data_dir is None:
        data_dir = os.environ.get("DATA_DIR", "data")

    storage = Storage(data_dir=data_dir)

    llm_api_key = os.environ.get("LLM_API_KEY")
    llm_base_url = os.environ.get("LLM_BASE_URL")
    llm_model = os.environ.get("LLM_MODEL")
    parser = ReportParser(llm_api_key=llm_api_key, llm_base_url=llm_base_url, llm_model=llm_model)

    llm_client = parser._client
    kb_manager = KnowledgeBaseManager(storage, llm_client=llm_client)
    comparator = ReportComparator(storage, llm_client=llm_client)
    stock_data_service = StockDataService(cache_ttl=300)

    app.config["storage"] = storage
    app.config["parser"] = parser
    app.config["kb_manager"] = kb_manager
    app.config["comparator"] = comparator
    app.config["stock_data_service"] = stock_data_service

    CORS(app)

    app.register_blueprint(report_bp, url_prefix="/api/v1")
    app.register_blueprint(kb_bp, url_prefix="/api/v1")
    app.register_blueprint(compare_bp, url_prefix="/api/v1")

    return app


def show_hello():
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo("hello", "hello")
    root.destroy()


if __name__ == "__main__":
    show_hello()
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
