"""ReportComparator — multi-report comparison engine."""
from __future__ import annotations

import hashlib
import json
import time

# Key-points truncation limit per report (chars)
_KP_MAX_CHARS = 600


class ReportComparator:
    def __init__(self, storage, llm_client=None, llm_model: str = "qwen3.5-plus", llm_fallback_model: str = "glm-4-flash"):
        self.storage = storage
        self.llm_client = llm_client
        self.llm_model = llm_model
        self.llm_fallback_model = llm_fallback_model
        self._compare_cache: dict[str, dict] = {}  # hash -> cached result

    def validate(self, report_ids: list) -> tuple[bool, str | None]:
        """Validate report_ids for comparison. Returns (ok, error_code)."""
        if len(report_ids) < 2:
            return False, "COMPARE_MIN_REPORTS"

        parsed_reports = []
        for rid in report_ids:
            parsed = self.storage.get_parsed_report(rid)
            if parsed is None:
                return False, "REPORT_NOT_FOUND"
            parsed_reports.append(parsed)

        stock_codes = {p.get("stock_code") for p in parsed_reports}
        if len(stock_codes) > 1:
            return False, "COMPARE_DIFF_STOCK"

        return True, None

    @staticmethod
    def _cache_key(report_ids: list) -> str:
        """Deterministic hash for a set of report IDs."""
        key = "|".join(sorted(report_ids))
        return hashlib.md5(key.encode()).hexdigest()

    def compare(self, report_ids: list) -> dict:
        """Execute full comparison pipeline with caching."""
        # ── Check cache ──────────────────────────────────────
        ck = self._cache_key(report_ids)
        if ck in self._compare_cache:
            cached = self._compare_cache[ck]
            cached["compare_time_ms"] = 0  # instant
            cached["from_cache"] = True
            return cached

        start = time.time()
        parsed_reports = []
        for rid in report_ids:
            parsed = self.storage.get_parsed_report(rid)
            parsed_reports.append(parsed)

        stock_code = parsed_reports[0].get("stock_code", "")
        stock_name = parsed_reports[0].get("stock_name", "")

        reports_summary = self._build_reports_summary(parsed_reports)
        field_differences = self._compare_fields(parsed_reports)
        similarities, kp_differences = self._compare_key_points(parsed_reports)

        all_differences = field_differences + kp_differences
        elapsed_ms = int((time.time() - start) * 1000)

        result = {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "reports_summary": reports_summary,
            "similarities": similarities,
            "differences": all_differences,
            "compare_time_ms": elapsed_ms,
            "from_cache": False,
        }

        # ── Store in cache ───────────────────────────────────
        self._compare_cache[ck] = result
        return result

    def _build_reports_summary(self, parsed_reports: list) -> list:
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

    def _compare_fields(self, parsed_reports: list) -> list:
        differences = []
        # Compare rating
        ratings = {p.get("report_id", ""): p.get("rating", "") for p in parsed_reports}
        unique_ratings = set(ratings.values())
        if len(unique_ratings) > 1:
            vals_str = " vs ".join(unique_ratings)
            differences.append({
                "field": "rating",
                "values": ratings,
                "highlight": f"评级存在分歧：{vals_str}",
            })

        # Compare target_price
        prices = {p.get("report_id", ""): p.get("target_price") for p in parsed_reports}
        non_null_prices = [v for v in prices.values() if v is not None]
        if len(non_null_prices) >= 2:
            min_p, max_p = min(non_null_prices), max(non_null_prices)
            if min_p > 0 and max_p != min_p:
                diff_pct = round((max_p - min_p) / min_p * 100, 1)
                vals_str = " vs ".join(str(v) for v in non_null_prices)
                differences.append({
                    "field": "target_price",
                    "values": prices,
                    "highlight": f"目标价差异：{vals_str}，差距{diff_pct}%",
                })

        return differences

    def _compare_key_points(self, parsed_reports: list) -> tuple[list, list]:
        """Compare key_points across reports."""
        key_points_map = {
            p.get("report_id", ""): p.get("key_points", "")
            for p in parsed_reports
        }

        # Try LLM semantic comparison
        if self.llm_client:
            try:
                return self._llm_compare_key_points(parsed_reports)
            except Exception:
                pass

        # Fallback: simple text-based comparison
        return self._simple_compare_key_points(parsed_reports)

    def _llm_compare_key_points(self, parsed_reports: list) -> tuple[list, list]:
        """Use LLM for semantic comparison of key points."""
        # ── Truncate key_points to reduce tokens ─────────────
        reports_text = "\n".join([
            f"研报{i+1}（{p.get('report_id', '')}）：{p.get('key_points', '')[:_KP_MAX_CHARS]}"
            for i, p in enumerate(parsed_reports)
        ])
        report_ids = [p.get("report_id", "") for p in parsed_reports]

        system_prompt = ("比较以下研报观点，返回JSON："
            '{"similarities":[{"topic":"主题","merged_view":"描述","source_reports":["id1"]}],'
            '"differences":[{"field":"key_points","highlight":"差异要点"}]}'
            "\n只返回JSON，不要解释。")

        response = self.llm_client.chat.completions.create(
            model=self.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": reports_text},
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        content = response.choices[0].message.content
        # Strip markdown code block if present
        if content.strip().startswith("```"):
            lines = content.strip().split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            content = "\n".join(lines)
        result = json.loads(content)

        similarities = result.get("similarities", [])
        for s in similarities:
            if "source_reports" not in s:
                s["source_reports"] = report_ids

        differences = []
        for d in result.get("differences", []):
            differences.append({
                "field": "key_points",
                "values": {rid: p.get("key_points", "") for rid, p in
                           zip([pr.get("report_id", "") for pr in parsed_reports],
                               parsed_reports)},
                "highlight": d.get("highlight", d.get("description", "")),
            })

        return similarities, differences

    def _simple_compare_key_points(self, parsed_reports: list) -> tuple[list, list]:
        """Simple text-based comparison fallback."""
        report_ids = [p.get("report_id", "") for p in parsed_reports]

        # Generate a basic similarity
        similarities = [{
            "topic": "核心观点概要",
            "merged_view": "；".join([
                p.get("key_points", "")[:100] for p in parsed_reports if p.get("key_points")
            ]),
            "source_reports": report_ids,
        }]

        # Check for obvious differences in key_points length/content
        differences = []
        kps = [p.get("key_points", "") for p in parsed_reports]
        if len(set(kps)) > 1:
            differences.append({
                "field": "key_points",
                "values": {p.get("report_id", ""): p.get("key_points", "")
                           for p in parsed_reports},
                "highlight": "各研报核心观点侧重不同，建议详细阅读原文对比",
            })

        return similarities, differences
