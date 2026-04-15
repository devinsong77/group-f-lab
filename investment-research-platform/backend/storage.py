"""
Storage 层 — 内存数据库 + JSON 持久化 + PDF 文件管理

对齐规格: 10-数据模型与存储规格
Task1 提供基础方法 (save_report, get_report, update_report_status, save_parsed_report, get_parsed_report, add_report_to_stock)
Task2 扩展方法 (get_reports, delete_report, get_stocks, get_stock_detail, update_stock_summary, remove_report_from_stock)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone


class Storage:
    """内存数据库 + JSON 持久化存储引擎"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.reports_dir = os.path.join(data_dir, "reports")

        # JSON 持久化文件路径
        self.reports_json = os.path.join(data_dir, "reports.json")
        self.parsed_reports_json = os.path.join(data_dir, "parsed_reports.json")
        self.knowledge_base_json = os.path.join(data_dir, "knowledge_base.json")

        # 确保目录存在
        os.makedirs(self.reports_dir, exist_ok=True)

        # 内存数据库 —— 启动时从 JSON 加载
        self._reports: dict[str, dict] = {}
        self._parsed_reports: dict[str, dict] = {}
        self._stocks: dict[str, dict] = {}

        self._load_from_json()

    # ──────────────────────────────────────────────
    # 内部工具方法
    # ──────────────────────────────────────────────

    def _load_from_json(self) -> None:
        """启动时从 JSON 文件加载数据到内存"""
        self._reports = self._read_json(self.reports_json)
        self._parsed_reports = self._read_json(self.parsed_reports_json)
        self._stocks = self._read_json(self.knowledge_base_json)

    def _read_json(self, path: str) -> dict:
        """读取 JSON 文件，文件不存在或损坏时返回空 dict"""
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _write_json(self, path: str, data: dict) -> None:
        """将数据写回 JSON 文件（UTF-8, 2空格缩进）"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _persist_reports(self) -> None:
        self._write_json(self.reports_json, self._reports)

    def _persist_parsed_reports(self) -> None:
        self._write_json(self.parsed_reports_json, self._parsed_reports)

    def _persist_knowledge_base(self) -> None:
        self._write_json(self.knowledge_base_json, self._stocks)

    # ══════════════════════════════════════════════
    # Task1 — 研报管理基础方法
    # ══════════════════════════════════════════════

    def save_report(self, report_id: str, filename: str, file_path: str) -> dict:
        """保存研报元数据，parse_status 初始为 pending (对齐 10 §6.1)"""
        report = {
            "report_id": report_id,
            "filename": filename,
            "file_path": file_path,
            "parse_status": "pending",
            "upload_time": datetime.now(timezone.utc).isoformat(),
        }
        self._reports[report_id] = report
        self._persist_reports()
        return report

    def get_report(self, report_id: str) -> dict | None:
        """返回单个研报元数据"""
        return self._reports.get(report_id)

    def update_report_status(self, report_id: str, status: str) -> dict:
        """更新 parse_status (pending/parsing/completed/failed)"""
        report = self._reports.get(report_id)
        if report is None:
            raise KeyError(f"Report {report_id} not found")
        report["parse_status"] = status
        self._persist_reports()
        return report

    # ══════════════════════════════════════════════
    # Task1 — 解析结果管理
    # ══════════════════════════════════════════════

    def save_parsed_report(self, report_id: str, parsed_data: dict) -> dict:
        """
        保存解析结果 + 更新 parse_status 为 completed + 自动入知识库
        (对齐 10 §6.2 + §7)
        """
        parsed_report = {
            "report_id": report_id,
            "title": parsed_data.get("title", ""),
            "rating": parsed_data.get("rating", "未提及"),
            "target_price": parsed_data.get("target_price"),
            "key_points": parsed_data.get("key_points", ""),
            "stock_code": parsed_data.get("stock_code", ""),
            "stock_name": parsed_data.get("stock_name", ""),
            "industry": parsed_data.get("industry", ""),
            "raw_text": parsed_data.get("raw_text", ""),
            "parse_time_ms": parsed_data.get("parse_time_ms", 0),
            "parsed_at": datetime.now(timezone.utc).isoformat(),
        }
        self._parsed_reports[report_id] = parsed_report
        self._persist_parsed_reports()

        # 更新 parse_status
        self.update_report_status(report_id, "completed")

        # 自动入知识库
        stock_code = parsed_report["stock_code"]
        if stock_code:
            self.add_report_to_stock(
                stock_code=stock_code,
                stock_name=parsed_report["stock_name"],
                industry=parsed_report["industry"],
                report_id=report_id,
            )

        return parsed_report

    def get_parsed_report(self, report_id: str) -> dict | None:
        """返回解析结果"""
        return self._parsed_reports.get(report_id)

    # ══════════════════════════════════════════════
    # Task1 — 知识库入库基础方法
    # ══════════════════════════════════════════════

    def add_report_to_stock(
        self, stock_code: str, stock_name: str, industry: str, report_id: str
    ) -> dict:
        """
        将研报添加到对应股票的知识库
        若股票不存在则新建条目 (对齐 10 §6.3)
        """
        now = datetime.now(timezone.utc).isoformat()
        if stock_code not in self._stocks:
            self._stocks[stock_code] = {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "industry": industry,
                "report_ids": [],
                "recent_summary": "",
                "updated_at": now,
            }

        stock = self._stocks[stock_code]
        if report_id not in stock["report_ids"]:
            stock["report_ids"].append(report_id)
        stock["updated_at"] = now
        # 更新股票名称和行业（以最新研报为准）
        stock["stock_name"] = stock_name
        stock["industry"] = industry

        self._persist_knowledge_base()
        return stock

    # ══════════════════════════════════════════════
    # Task2 — 研报管理扩展方法
    # ══════════════════════════════════════════════

    def get_reports(self, filters: dict | None = None) -> list:
        """
        返回全部研报列表，支持筛选参数 (对齐 10 §6.1)
        filters 可选键: stock_code, industry, date_from, date_to
        每条记录合并 Report 元数据 + ParsedReport 解析结果
        """
        result = []
        for report_id, report in self._reports.items():
            parsed = self._parsed_reports.get(report_id, {})
            merged = {
                "report_id": report["report_id"],
                "filename": report["filename"],
                "title": parsed.get("title"),
                "stock_code": parsed.get("stock_code"),
                "stock_name": parsed.get("stock_name"),
                "industry": parsed.get("industry"),
                "rating": parsed.get("rating"),
                "parse_status": report["parse_status"],
                "upload_time": report["upload_time"],
            }
            result.append(merged)

        if not filters:
            return result

        # 筛选
        filtered = result
        if filters.get("stock_code"):
            filtered = [
                r for r in filtered
                if r.get("stock_code") == filters["stock_code"]
            ]
        if filters.get("industry"):
            filtered = [
                r for r in filtered
                if r.get("industry") == filters["industry"]
            ]
        if filters.get("date_from"):
            date_from = filters["date_from"]
            filtered = [
                r for r in filtered
                if r.get("upload_time", "") >= date_from
            ]
        if filters.get("date_to"):
            date_to = filters["date_to"]
            filtered = [
                r for r in filtered
                if r.get("upload_time", "") <= date_to
            ]

        return filtered

    def get_report_detail(self, report_id: str) -> dict | None:
        """
        返回完整研报详情（元数据 + 解析结果合并）(对齐 09 §6)
        """
        report = self._reports.get(report_id)
        if report is None:
            return None

        parsed = self._parsed_reports.get(report_id, {})
        return {
            "report_id": report["report_id"],
            "filename": report["filename"],
            "title": parsed.get("title"),
            "rating": parsed.get("rating"),
            "target_price": parsed.get("target_price"),
            "key_points": parsed.get("key_points"),
            "stock_code": parsed.get("stock_code"),
            "stock_name": parsed.get("stock_name"),
            "industry": parsed.get("industry"),
            "parse_status": report["parse_status"],
            "upload_time": report["upload_time"],
            "parse_time_ms": parsed.get("parse_time_ms"),
        }

    def delete_report(self, report_id: str) -> None:
        """
        级联删除研报 (对齐 10 §6.1 + §7)
        1. 获取 ParsedReport → 得到 stock_code
        2. 删除 Report 元数据
        3. 删除 ParsedReport 解析结果
        4. remove_report_from_stock(stock_code, report_id)
        5. 删除 PDF 文件
        6. 写回所有 JSON 文件
        """
        report = self._reports.get(report_id)
        if report is None:
            raise KeyError(f"Report {report_id} not found")

        # 获取关联的 stock_code
        parsed = self._parsed_reports.get(report_id)
        stock_code = parsed.get("stock_code") if parsed else None

        # 删除 Report 元数据
        del self._reports[report_id]

        # 删除 ParsedReport 解析结果
        if report_id in self._parsed_reports:
            del self._parsed_reports[report_id]

        # 从知识库移除引用
        if stock_code:
            self.remove_report_from_stock(stock_code, report_id)

        # 删除 PDF 文件
        file_path = report.get("file_path", "")
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        # 写回所有 JSON 文件
        self._persist_reports()
        self._persist_parsed_reports()
        self._persist_knowledge_base()

    # ══════════════════════════════════════════════
    # Task2 — 知识库管理扩展方法
    # ══════════════════════════════════════════════

    def get_stocks(self) -> list:
        """
        返回知识库中的股票列表 (对齐 10 §6.3)
        每项含: stock_code, stock_name, industry, report_count, latest_report_date
        """
        result = []
        for stock_code, stock in self._stocks.items():
            report_ids = stock.get("report_ids", [])
            # 计算最新研报日期
            latest_date = self._get_latest_report_date(report_ids)
            result.append({
                "stock_code": stock["stock_code"],
                "stock_name": stock["stock_name"],
                "industry": stock["industry"],
                "report_count": len(report_ids),
                "latest_report_date": latest_date,
            })
        return result

    def get_stock_detail(self, stock_code: str) -> dict | None:
        """
        返回股票详情 + 关联研报信息 + 观点汇总 (对齐 10 §6.3)
        """
        stock = self._stocks.get(stock_code)
        if stock is None:
            return None

        report_ids = stock.get("report_ids", [])
        reports = []
        for rid in report_ids:
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

        # 按 upload_time 降序排列
        reports.sort(key=lambda r: r.get("upload_time", ""), reverse=True)

        return {
            "stock_code": stock["stock_code"],
            "stock_name": stock["stock_name"],
            "industry": stock["industry"],
            "report_count": len(report_ids),
            "recent_summary": stock.get("recent_summary", ""),
            "reports": reports,
        }

    def get_stock_reports(
        self, stock_code: str, sort_by: str = "upload_time", order: str = "desc"
    ) -> list:
        """
        返回某只股票的关联研报列表，支持时间排序
        """
        stock = self._stocks.get(stock_code)
        if stock is None:
            return []

        report_ids = stock.get("report_ids", [])
        reports = []
        for rid in report_ids:
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

        reverse = order == "desc"
        reports.sort(key=lambda r: r.get(sort_by, ""), reverse=reverse)
        return reports

    def update_stock_summary(self, stock_code: str, summary: str) -> dict:
        """更新 recent_summary 字段 (对齐 10 §6.3)"""
        stock = self._stocks.get(stock_code)
        if stock is None:
            raise KeyError(f"Stock {stock_code} not found")

        stock["recent_summary"] = summary
        stock["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._persist_knowledge_base()
        return stock

    def remove_report_from_stock(self, stock_code: str, report_id: str) -> None:
        """
        从知识库移除研报引用 (对齐 10 §6.3)
        若无关联研报则删除整个 Stock 条目
        """
        stock = self._stocks.get(stock_code)
        if stock is None:
            return

        if report_id in stock["report_ids"]:
            stock["report_ids"].remove(report_id)

        if not stock["report_ids"]:
            # 无关联研报 → 删除整个 Stock 条目
            del self._stocks[stock_code]
        else:
            stock["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._persist_knowledge_base()

    # ──────────────────────────────────────────────
    # 内部辅助
    # ──────────────────────────────────────────────

    def _get_latest_report_date(self, report_ids: list[str]) -> str:
        """获取研报列表中最新的上传时间"""
        latest = ""
        for rid in report_ids:
            report = self._reports.get(rid)
            if report:
                upload_time = report.get("upload_time", "")
                if upload_time > latest:
                    latest = upload_time
        return latest

    def get_report_file_path(self, report_id: str) -> str | None:
        """获取研报 PDF 文件路径"""
        report = self._reports.get(report_id)
        if report is None:
            return None
        file_path = report.get("file_path", "")
        if file_path and os.path.exists(file_path):
            return file_path
        return None
