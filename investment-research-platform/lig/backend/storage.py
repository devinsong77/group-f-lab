import json
import os
import shutil
from datetime import datetime, timezone


class Storage:
    """内存数据库 + JSON 持久化 + PDF 文件管理"""

    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.reports_dir = os.path.join(data_dir, "reports")
        self._reports = {}
        self._parsed_reports = {}
        self._knowledge_base = {}
        self._ensure_dirs()
        self._load()

    def _ensure_dirs(self):
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)

    def _load(self):
        self._reports = self._read_json("reports.json")
        self._parsed_reports = self._read_json("parsed_reports.json")
        self._knowledge_base = self._read_json("knowledge_base.json")

    def _read_json(self, filename):
        path = os.path.join(self.data_dir, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _write_json(self, filename, data):
        path = os.path.join(self.data_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _persist_all(self):
        self._write_json("reports.json", self._reports)
        self._write_json("parsed_reports.json", self._parsed_reports)
        self._write_json("knowledge_base.json", self._knowledge_base)

    # ==================== Task1: 研报上传与解析 ====================

    def save_report(self, report_id, filename, file_path):
        report = {
            "report_id": report_id,
            "filename": filename,
            "file_path": file_path,
            "parse_status": "pending",
            "upload_time": datetime.now(timezone.utc).isoformat(),
        }
        self._reports[report_id] = report
        self._write_json("reports.json", self._reports)
        return report

    def get_report(self, report_id):
        return self._reports.get(report_id)

    def update_report_status(self, report_id, status):
        report = self._reports.get(report_id)
        if report:
            report["parse_status"] = status
            self._write_json("reports.json", self._reports)
        return report

    def save_parsed_report(self, report_id, parsed_data):
        parsed_data["report_id"] = report_id
        parsed_data["parsed_at"] = datetime.now(timezone.utc).isoformat()
        self._parsed_reports[report_id] = parsed_data
        self._reports[report_id]["parse_status"] = "completed"
        stock_code = parsed_data.get("stock_code", "")
        stock_name = parsed_data.get("stock_name", "")
        industry = parsed_data.get("industry", "")
        if stock_code:
            self.add_report_to_stock(stock_code, stock_name, industry, report_id)
        self._write_json("reports.json", self._reports)
        self._write_json("parsed_reports.json", self._parsed_reports)
        self._write_json("knowledge_base.json", self._knowledge_base)
        return parsed_data

    def get_parsed_report(self, report_id):
        return self._parsed_reports.get(report_id)

    def add_report_to_stock(self, stock_code, stock_name, industry, report_id):
        if stock_code not in self._knowledge_base:
            self._knowledge_base[stock_code] = {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "industry": industry,
                "report_ids": [],
                "recent_summary": "",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        stock = self._knowledge_base[stock_code]
        if report_id not in stock["report_ids"]:
            stock["report_ids"].append(report_id)
        stock["updated_at"] = datetime.now(timezone.utc).isoformat()
        return stock

    # ==================== Task2: 研报管理 ====================

    def get_reports(self, filters=None):
        results = []
        for rid, report in self._reports.items():
            parsed = self._parsed_reports.get(rid, {})
            merged = {**report, **parsed}
            if filters:
                if filters.get("stock_code") and parsed.get("stock_code") != filters["stock_code"]:
                    continue
                if filters.get("industry") and parsed.get("industry") != filters["industry"]:
                    continue
                if filters.get("date_from"):
                    if report.get("upload_time", "") < filters["date_from"]:
                        continue
                if filters.get("date_to"):
                    if report.get("upload_time", "") > filters["date_to"]:
                        continue
            results.append(merged)
        results.sort(key=lambda x: x.get("upload_time", ""), reverse=True)
        return results

    def delete_report(self, report_id):
        if report_id not in self._reports:
            return False
        parsed = self._parsed_reports.get(report_id)
        stock_code = parsed.get("stock_code") if parsed else None
        del self._reports[report_id]
        self._parsed_reports.pop(report_id, None)
        if stock_code:
            self.remove_report_from_stock(stock_code, report_id)
        report_pdf = os.path.join(self.reports_dir, f"{report_id}.pdf")
        if os.path.exists(report_pdf):
            os.remove(report_pdf)
        self._persist_all()
        return True

    # ==================== Task2: 知识库管理 ====================

    def get_stocks(self):
        stocks = []
        for code, stock in self._knowledge_base.items():
            latest_date = None
            for rid in stock.get("report_ids", []):
                r = self._reports.get(rid)
                if r:
                    t = r.get("upload_time", "")
                    if latest_date is None or t > latest_date:
                        latest_date = t
            stocks.append({
                "stock_code": stock["stock_code"],
                "stock_name": stock["stock_name"],
                "industry": stock["industry"],
                "report_count": len(stock.get("report_ids", [])),
                "latest_report_date": latest_date,
            })
        return stocks

    def get_stock(self, stock_code):
        return self._knowledge_base.get(stock_code)

    def get_stock_detail(self, stock_code):
        stock = self._knowledge_base.get(stock_code)
        if not stock:
            return None
        reports = []
        for rid in stock.get("report_ids", []):
            parsed = self._parsed_reports.get(rid)
            report_meta = self._reports.get(rid)
            if parsed and report_meta:
                reports.append({
                    "report_id": rid,
                    "title": parsed.get("title", ""),
                    "rating": parsed.get("rating", ""),
                    "target_price": parsed.get("target_price"),
                    "key_points": parsed.get("key_points", ""),
                    "upload_time": report_meta.get("upload_time", ""),
                })
        reports.sort(key=lambda x: x.get("upload_time", ""), reverse=True)
        return {
            "stock_code": stock["stock_code"],
            "stock_name": stock["stock_name"],
            "industry": stock["industry"],
            "report_count": len(stock.get("report_ids", [])),
            "recent_summary": stock.get("recent_summary", ""),
            "reports": reports,
        }

    def update_stock_summary(self, stock_code, summary):
        stock = self._knowledge_base.get(stock_code)
        if stock:
            stock["recent_summary"] = summary
            stock["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._write_json("knowledge_base.json", self._knowledge_base)
        return stock

    def remove_report_from_stock(self, stock_code, report_id):
        stock = self._knowledge_base.get(stock_code)
        if not stock:
            return
        if report_id in stock["report_ids"]:
            stock["report_ids"].remove(report_id)
        if not stock["report_ids"]:
            del self._knowledge_base[stock_code]
        else:
            stock["updated_at"] = datetime.now(timezone.utc).isoformat()
