import json
import time
import logging

logger = logging.getLogger(__name__)


class ReportComparator:
    """研报比对引擎 - 逐字段对比 + LLM 语义比对"""

    def __init__(self, storage, llm_client=None):
        self.storage = storage
        self._llm_client = llm_client

    def validate(self, report_ids):
        if len(report_ids) < 2:
            return False, "COMPARE_MIN_REPORTS"
        stock_codes = set()
        for rid in report_ids:
            parsed = self.storage.get_parsed_report(rid)
            if not parsed:
                return False, "REPORT_NOT_FOUND"
            stock_codes.add(parsed.get("stock_code", ""))
        if len(stock_codes) > 1:
            return False, "COMPARE_DIFF_STOCK"
        return True, ""

    def compare(self, report_ids):
        start = time.time()
        parsed_reports = []
        for rid in report_ids:
            parsed = self.storage.get_parsed_report(rid)
            parsed_reports.append(parsed)
        reports_summary = self._build_reports_summary(parsed_reports)
        field_diffs = self._compare_fields(parsed_reports)
        similarities, kp_diffs = self._compare_key_points(parsed_reports)
        differences = field_diffs + kp_diffs
        first = parsed_reports[0]
        return {
            "stock_code": first.get("stock_code", ""),
            "stock_name": first.get("stock_name", ""),
            "reports_summary": reports_summary,
            "similarities": similarities,
            "differences": differences,
            "compare_time_ms": int((time.time() - start) * 1000),
        }

    def _build_reports_summary(self, parsed_reports):
        summaries = []
        for p in parsed_reports:
            summaries.append({
                "report_id": p.get("report_id", ""),
                "title": p.get("title", ""),
                "rating": p.get("rating", ""),
                "target_price": p.get("target_price"),
                "key_points": p.get("key_points", ""),
            })
        return summaries

    def _compare_fields(self, parsed_reports):
        differences = []
        ratings = {}
        for p in parsed_reports:
            ratings[p["report_id"]] = p.get("rating", "未提及")
        if len(set(ratings.values())) > 1:
            labels = [f"{ratings[rid]}" for rid in ratings]
            differences.append({
                "field": "rating",
                "values": ratings,
                "highlight": f"评级存在分歧：{'、'.join(labels)}",
            })

        prices = {}
        for p in parsed_reports:
            tp = p.get("target_price")
            if tp is not None:
                prices[p["report_id"]] = tp
        if len(prices) >= 2:
            vals = list(prices.values())
            if len(set(vals)) > 1:
                max_p, min_p = max(vals), min(vals)
                diff_pct = round((max_p - min_p) / min_p * 100, 1) if min_p else 0
                labels = [f"{v}" for v in vals]
                differences.append({
                    "field": "target_price",
                    "values": prices,
                    "highlight": f"目标价差异：{' vs '.join(labels)}，差距{diff_pct}%",
                })
        return differences

    def _compare_key_points(self, parsed_reports):
        if self._llm_client:
            return self._llm_compare_key_points(parsed_reports)
        return self._simple_compare_key_points(parsed_reports)

    def _llm_compare_key_points(self, parsed_reports):
        try:
            kp_texts = []
            for p in parsed_reports:
                title = p.get("title", "未知研报")
                kp = p.get("key_points", "")
                kp_texts.append(f"研报《{title}》(ID: {p['report_id']}):\n{kp}")
            prompt = (
                "请对比以下多份研报的核心观点，输出严格JSON格式：\n"
                '{"similarities": [{"topic": "主题", "merged_view": "合并描述", '
                '"source_reports": ["report_id1", "report_id2"]}], '
                '"differences": [{"field": "key_points", "description": "差异描述", '
                '"values": {"report_id1": "观点1", "report_id2": "观点2"}, '
                '"highlight": "差异高亮说明"}]}\n\n'
                + "\n\n".join(kp_texts)
            )
            response = self._llm_client.chat.completions.create(
                model="qwen-plus",
                messages=[
                    {"role": "system", "content": "你是金融研报分析专家。请严格输出JSON，不要输出其他内容。"},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            result = json.loads(response.choices[0].message.content)
            sims = result.get("similarities", [])
            diffs = result.get("differences", [])
            for d in diffs:
                if "field" not in d:
                    d["field"] = "key_points"
            return sims, diffs
        except Exception as e:
            logger.warning(f"LLM key_points comparison failed: {e}, using fallback")
            return self._simple_compare_key_points(parsed_reports)

    def _simple_compare_key_points(self, parsed_reports):
        similarities = []
        differences = []
        all_ids = [p["report_id"] for p in parsed_reports]
        kp_map = {p["report_id"]: p.get("key_points", "") for p in parsed_reports}
        non_empty = {rid: kp for rid, kp in kp_map.items() if kp}
        if len(non_empty) >= 2:
            similarities.append({
                "topic": "核心观点概述",
                "merged_view": "；".join(
                    f"[{p.get('title', '研报')}] {p.get('key_points', '')}"
                    for p in parsed_reports if p.get("key_points")
                ),
                "source_reports": list(non_empty.keys()),
            })
            values = {}
            for p in parsed_reports:
                values[p["report_id"]] = p.get("key_points", "（无观点）")
            differences.append({
                "field": "key_points",
                "values": values,
                "highlight": "各研报核心观点存在不同侧重点",
            })
        return similarities, differences
