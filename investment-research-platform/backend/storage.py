"""Storage layer — in-memory dict + JSON persistence + PDF file management."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone


class Storage:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.reports_dir = os.path.join(data_dir, "reports")
        os.makedirs(self.reports_dir, exist_ok=True)

        self._reports: dict[str, dict] = {}
        self._parsed_reports: dict[str, dict] = {}
        self._knowledge_base: dict[str, dict] = {}

        self._reports_file = os.path.join(data_dir, "reports.json")
        self._parsed_file = os.path.join(data_dir, "parsed_reports.json")
        self._kb_file = os.path.join(data_dir, "knowledge_base.json")

        self._load()

    # ── persistence ──────────────────────────────────────────

    def _load(self):
        for attr, path in [
            ("_reports", self._reports_file),
            ("_parsed_reports", self._parsed_file),
            ("_knowledge_base", self._kb_file),
        ]:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    setattr(self, attr, json.load(f))

    def _save_reports(self):
        with open(self._reports_file, "w", encoding="utf-8") as f:
            json.dump(self._reports, f, ensure_ascii=False, indent=2)

    def _save_parsed(self):
        with open(self._parsed_file, "w", encoding="utf-8") as f:
            json.dump(self._parsed_reports, f, ensure_ascii=False, indent=2)

    def _save_kb(self):
        with open(self._kb_file, "w", encoding="utf-8") as f:
            json.dump(self._knowledge_base, f, ensure_ascii=False, indent=2)

    def _save_all(self):
        self._save_reports()
        self._save_parsed()
        self._save_kb()

    # ── Report CRUD ──────────────────────────────────────────

    def save_report(self, report_id: str, filename: str, file_path: str) -> dict:
        report = {
            "report_id": report_id,
            "filename": filename,
            "file_path": file_path,
            "parse_status": "pending",
            "upload_time": datetime.now(timezone.utc).isoformat(),
        }
        self._reports[report_id] = report
        self._save_reports()
        return report

    def get_report(self, report_id: str) -> dict | None:
        return self._reports.get(report_id)

    def update_report_status(self, report_id: str, status: str) -> dict:
        report = self._reports.get(report_id)
        if report is None:
            raise KeyError(f"Report {report_id} not found")
        report["parse_status"] = status
        self._save_reports()
        return report

    def save_parsed_report(self, report_id: str, parsed_data: dict) -> dict:
        parsed = {
            "report_id": report_id,
            **parsed_data,
            "parsed_at": datetime.now(timezone.utc).isoformat(),
        }
        self._parsed_reports[report_id] = parsed
        self.update_report_status(report_id, "completed")
        # auto-add to knowledge base
        stock_code = parsed_data.get("stock_code", "")
        stock_name = parsed_data.get("stock_name", "")
        industry = parsed_data.get("industry", "")
        if stock_code:
            self.add_report_to_stock(stock_code, stock_name, industry, report_id)
        self._save_parsed()
        return parsed

    def get_parsed_report(self, report_id: str) -> dict | None:
        return self._parsed_reports.get(report_id)

    # ── Reports list / filter / delete ───────────────────────

    def get_reports(self, filters: dict | None = None) -> list:
        results = []
        for rid, report in self._reports.items():
            parsed = self._parsed_reports.get(rid, {})
            merged = {**report, **parsed}
            results.append(merged)

        if filters:
            stock_code = filters.get("stock_code")
            industry = filters.get("industry")
            date_from = filters.get("date_from")
            date_to = filters.get("date_to")

            if stock_code:
                results = [r for r in results if r.get("stock_code") == stock_code]
            if industry:
                results = [r for r in results if r.get("industry") == industry]
            if date_from:
                results = [r for r in results if r.get("upload_time", "") >= date_from]
            if date_to:
                results = [r for r in results if r.get("upload_time", "") <= date_to]

        results.sort(key=lambda r: r.get("upload_time", ""), reverse=True)
        return results

    def delete_report(self, report_id: str) -> None:
        report = self._reports.get(report_id)
        if report is None:
            raise KeyError(f"Report {report_id} not found")

        parsed = self._parsed_reports.get(report_id, {})
        stock_code = parsed.get("stock_code")

        # 1. delete report metadata
        del self._reports[report_id]
        # 2. delete parsed result
        self._parsed_reports.pop(report_id, None)
        # 3. remove from knowledge base
        if stock_code:
            self.remove_report_from_stock(stock_code, report_id)
        # 4. delete PDF file
        file_path = report.get("file_path", "")
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        # 5. persist
        self._save_all()

    # ── Knowledge Base ───────────────────────────────────────

    def add_report_to_stock(self, stock_code: str, stock_name: str, industry: str, report_id: str) -> dict:
        stock = self._knowledge_base.get(stock_code)
        if stock is None:
            stock = {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "industry": industry,
                "report_ids": [],
                "recent_summary": "",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self._knowledge_base[stock_code] = stock
        if report_id not in stock["report_ids"]:
            stock["report_ids"].append(report_id)
        stock["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_kb()
        return stock

    def remove_report_from_stock(self, stock_code: str, report_id: str) -> None:
        stock = self._knowledge_base.get(stock_code)
        if stock is None:
            return
        if report_id in stock["report_ids"]:
            stock["report_ids"].remove(report_id)
        if not stock["report_ids"]:
            del self._knowledge_base[stock_code]
        else:
            stock["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_kb()

    def get_stocks(self) -> list:
        results = []
        for code, stock in self._knowledge_base.items():
            latest_date = ""
            for rid in stock.get("report_ids", []):
                r = self._reports.get(rid)
                if r and r.get("upload_time", "") > latest_date:
                    latest_date = r["upload_time"]
            results.append({
                "stock_code": stock["stock_code"],
                "stock_name": stock["stock_name"],
                "industry": stock["industry"],
                "report_count": len(stock.get("report_ids", [])),
                "latest_report_date": latest_date,
            })
        return results

    def get_stock(self, stock_code: str) -> dict | None:
        return self._knowledge_base.get(stock_code)

    def get_stock_detail(self, stock_code: str) -> dict | None:
        stock = self._knowledge_base.get(stock_code)
        if stock is None:
            return None

        reports = []
        for rid in stock.get("report_ids", []):
            report = self._reports.get(rid, {})
            parsed = self._parsed_reports.get(rid, {})
            reports.append({
                "report_id": rid,
                "title": parsed.get("title", ""),
                "rating": parsed.get("rating", ""),
                "target_price": parsed.get("target_price"),
                "key_points": parsed.get("key_points", ""),
                "upload_time": report.get("upload_time", ""),
            })
        reports.sort(key=lambda r: r.get("upload_time", ""), reverse=True)

        return {
            "stock_code": stock["stock_code"],
            "stock_name": stock["stock_name"],
            "industry": stock["industry"],
            "report_count": len(stock.get("report_ids", [])),
            "recent_summary": stock.get("recent_summary", ""),
            "reports": reports,
        }

    def update_stock_summary(self, stock_code: str, summary: str) -> dict | None:
        stock = self._knowledge_base.get(stock_code)
        if stock is None:
            return None
        stock["recent_summary"] = summary
        stock["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_kb()
        return stock
