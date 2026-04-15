"""KnowledgeBaseManager — stock aggregation and summary generation."""
from __future__ import annotations


class KnowledgeBaseManager:
    def __init__(self, storage, llm_client=None, llm_model: str = "qwen3.5-plus"):
        self.storage = storage
        self.llm_client = llm_client
        self.llm_model = llm_model

    def get_stocks(self) -> list:
        return self.storage.get_stocks()

    def get_stock_detail(self, stock_code: str) -> dict | None:
        return self.storage.get_stock_detail(stock_code)

    def get_stock_reports(self, stock_code: str, sort_by: str = "upload_time", order: str = "desc") -> list:
        detail = self.storage.get_stock_detail(stock_code)
        if detail is None:
            return []
        reports = detail.get("reports", [])
        reverse = order == "desc"
        reports.sort(key=lambda r: r.get(sort_by, ""), reverse=reverse)
        return reports

    def generate_summary(self, stock_code: str) -> str:
        """Generate summary for a stock from all its reports' key_points."""
        detail = self.storage.get_stock_detail(stock_code)
        if detail is None:
            return ""

        reports = detail.get("reports", [])
        if not reports:
            return ""

        key_points_list = [
            r.get("key_points", "") for r in reports if r.get("key_points")
        ]

        if not key_points_list:
            return ""

        # Try LLM summary
        if self.llm_client:
            try:
                combined = "\n\n".join(
                    [f"研报{i+1}观点：{kp}" for i, kp in enumerate(key_points_list)]
                )
                system_prompt = "你是一个金融分析助手。请将以下多份研报的核心观点汇总为一段简洁的综合摘要（200字以内）。"
                response = self.llm_client.chat.completions.create(
                    model=self.llm_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": combined},
                    ],
                    temperature=0.3,
                )
                summary = response.choices[0].message.content.strip()
                self.storage.update_stock_summary(stock_code, summary)
                return summary
            except Exception:
                pass

        # Fallback: simple concatenation
        summary = "；".join(key_points_list)
        if len(summary) > 500:
            summary = summary[:500] + "..."
        self.storage.update_stock_summary(stock_code, summary)
        return summary
