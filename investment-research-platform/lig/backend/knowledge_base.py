import json
import logging

logger = logging.getLogger(__name__)


class KnowledgeBaseManager:
    """知识库管理 - 按股票聚合、观点汇总生成"""

    def __init__(self, storage, llm_client=None):
        self.storage = storage
        self._llm_client = llm_client

    def get_stocks(self):
        return self.storage.get_stocks()

    def get_stock_detail(self, stock_code):
        return self.storage.get_stock_detail(stock_code)

    def get_stock_reports(self, stock_code, sort_by="upload_time", order="desc"):
        detail = self.storage.get_stock_detail(stock_code)
        if not detail:
            return []
        reports = detail.get("reports", [])
        reverse = order == "desc"
        reports.sort(key=lambda x: x.get(sort_by, ""), reverse=reverse)
        return reports

    def generate_summary(self, stock_code):
        detail = self.storage.get_stock_detail(stock_code)
        if not detail or not detail.get("reports"):
            return ""
        key_points_list = []
        for r in detail["reports"]:
            if r.get("key_points"):
                title = r.get("title", "未知研报")
                key_points_list.append(f"[{title}] {r['key_points']}")
        if not key_points_list:
            return ""
        if self._llm_client:
            try:
                prompt = (
                    "请根据以下多份研报的核心观点，生成一段综合汇总（200字以内）：\n\n"
                    + "\n\n".join(key_points_list)
                )
                response = self._llm_client.chat.completions.create(
                    model="qwen-plus",
                    messages=[
                        {"role": "system", "content": "你是一个专业的金融分析助手，请简洁地汇总多份研报的核心观点。"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                )
                summary = response.choices[0].message.content
                self.storage.update_stock_summary(stock_code, summary)
                return summary
            except Exception as e:
                logger.warning(f"LLM summary generation failed: {e}, using fallback")
        summary = "综合观点汇总：" + " | ".join(key_points_list)
        self.storage.update_stock_summary(stock_code, summary)
        return summary
