"""
Flask Blueprints 包

包含所有 API 路由 Blueprint：
- report_bp: 研报上传、解析、管理路由 (Task1)
- kb_bp: 知识库路由 (Task2)
- compare_bp: 研报比对路由 (Task3)
"""

from .report_bp import report_bp

__all__ = ['report_bp']
