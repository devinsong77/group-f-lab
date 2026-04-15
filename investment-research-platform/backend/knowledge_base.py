"""
知识库管理引擎 — KnowledgeBaseManager

对齐规格: 08 §2 (Knowledge Base 引擎层)、10 §5 (Stock 实体)
职责: 按股票聚合数据、观点汇总生成
禁止: 调用外部 API（分层架构约束）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.storage import Storage


class KnowledgeBaseManager:
    """知识库管理 — 按股票聚合、观点汇总生成"""

    def __init__(self, storage: Storage, llm_client=None):
        """
        Args:
            storage: Storage 实例引用
            llm_client: 可选 LLM 客户端（用于生成智能观点汇总）
                        需提供 chat_completion(prompt: str) -> str 接口
        """
        self.storage = storage
        self.llm_client = llm_client

    def get_stocks(self) -> list:
        """
        返回知识库股票列表
        每项包含: stock_code, stock_name, industry, report_count, latest_report_date
        """
        return self.storage.get_stocks()

    def get_stock_detail(self, stock_code: str) -> dict | None:
        """
        返回股票详情
        含: stock_code, stock_name, industry, report_count, recent_summary, reports[]
        """
        return self.storage.get_stock_detail(stock_code)

    def get_stock_reports(
        self, stock_code: str, sort_by: str = "upload_time", order: str = "desc"
    ) -> list:
        """返回某只股票的关联研报列表，支持时间排序"""
        return self.storage.get_stock_reports(stock_code, sort_by, order)

    def generate_summary(self, stock_code: str) -> str:
        """
        聚合该股票所有研报的核心观点，生成观点汇总 (对齐 Task2 §5.2)

        - 有 LLM 时：调用 LLM 生成智能汇总
        - 无 LLM 时：简单拼接各研报核心观点（降级方案）
        - 更新 Stock.recent_summary
        """
        detail = self.storage.get_stock_detail(stock_code)
        if detail is None:
            return ""

        reports = detail.get("reports", [])
        if not reports:
            summary = ""
            self.storage.update_stock_summary(stock_code, summary)
            return summary

        # 收集所有研报的核心观点
        key_points_list = []
        for report in reports:
            kp = report.get("key_points", "")
            title = report.get("title", "")
            if kp:
                key_points_list.append({"title": title, "key_points": kp})

        if not key_points_list:
            summary = ""
            self.storage.update_stock_summary(stock_code, summary)
            return summary

        if self.llm_client is not None:
            # 有 LLM 时：调用 LLM 生成智能汇总
            summary = self._generate_llm_summary(detail, key_points_list)
        else:
            # 无 LLM 时：简单拼接各研报核心观点（降级方案）
            summary = self._generate_fallback_summary(detail, key_points_list)

        self.storage.update_stock_summary(stock_code, summary)
        return summary

    def _generate_llm_summary(
        self, stock_detail: dict, key_points_list: list[dict]
    ) -> str:
        """调用 LLM 生成智能观点汇总"""
        stock_name = stock_detail.get("stock_name", "")
        stock_code = stock_detail.get("stock_code", "")

        # 构建 Prompt
        points_text = "\n".join(
            f"- 《{kp['title']}》: {kp['key_points']}"
            for kp in key_points_list
        )
        prompt = (
            f"你是一名专业的投研分析师。请根据以下多份关于 {stock_name}({stock_code}) "
            f"的研报核心观点，生成一段简洁的综合观点汇总（不超过 300 字）：\n\n"
            f"{points_text}\n\n"
            f"请直接输出汇总文本，不要添加标题或额外格式。"
        )

        try:
            summary = self.llm_client.chat_completion(prompt)
            return summary.strip()
        except Exception:
            # LLM 降级 → 使用 fallback
            return self._generate_fallback_summary(stock_detail, key_points_list)

    def _generate_fallback_summary(
        self, stock_detail: dict, key_points_list: list[dict]
    ) -> str:
        """简单拼接各研报核心观点（降级方案）"""
        stock_name = stock_detail.get("stock_name", "")
        parts = [f"{stock_name} 观点汇总："]
        for kp in key_points_list:
            title = kp.get("title", "未知研报")
            points = kp.get("key_points", "")
            parts.append(f"【{title}】{points}")
        return "\n".join(parts)
