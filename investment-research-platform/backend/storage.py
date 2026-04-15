"""
Storage 层 - 内存数据库 + JSON 持久化
对齐 spec/10-数据模型与存储规格.md
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional


class Storage:
    """
    内存存储引擎，支持 JSON 文件持久化
    数据存储在内存 dict 中，每次变更后写回 JSON 文件
    """

    def __init__(self, data_dir: str = "data"):
        """
        初始化 Storage
        
        Args:
            data_dir: 数据存储目录，默认 "data"
        """
        self.data_dir = data_dir
        self.reports_dir = os.path.join(data_dir, "reports")
        
        # JSON 文件路径
        self.reports_file = os.path.join(data_dir, "reports.json")
        self.parsed_reports_file = os.path.join(data_dir, "parsed_reports.json")
        self.knowledge_base_file = os.path.join(data_dir, "knowledge_base.json")
        
        # 内存数据结构
        self._reports: dict = {}  # report_id -> Report
        self._parsed_reports: dict = {}  # report_id -> ParsedReport
        self._knowledge_base: dict = {}  # stock_code -> Stock
        
        # 初始化目录和加载数据
        self._init_directories()
        self._load_all()

    def _init_directories(self) -> None:
        """初始化目录结构"""
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)

    def _load_all(self) -> None:
        """从 JSON 文件加载数据到内存"""
        self._reports = self._load_json(self.reports_file)
        self._parsed_reports = self._load_json(self.parsed_reports_file)
        self._knowledge_base = self._load_json(self.knowledge_base_file)

    def _load_json(self, filepath: str) -> dict:
        """加载单个 JSON 文件"""
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_json(self, filepath: str, data: dict) -> None:
        """保存数据到 JSON 文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _persist_all(self) -> None:
        """将所有数据持久化到 JSON 文件"""
        self._save_json(self.reports_file, self._reports)
        self._save_json(self.parsed_reports_file, self._parsed_reports)
        self._save_json(self.knowledge_base_file, self._knowledge_base)

    def _now_iso(self) -> str:
        """返回当前时间的 ISO-8601 格式字符串（UTC）"""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ==================== 研报管理 ====================

    def save_report(self, report_id: str, filename: str, file_path: str) -> dict:
        """
        保存研报元数据
        
        Args:
            report_id: 研报唯一 ID
            filename: 原始文件名
            file_path: 服务端存储路径
            
        Returns:
            保存的研报元数据 dict
        """
        report = {
            "report_id": report_id,
            "filename": filename,
            "file_path": file_path,
            "parse_status": "pending",
            "upload_time": self._now_iso()
        }
        self._reports[report_id] = report
        self._persist_all()
        return report

    def get_report(self, report_id: str) -> Optional[dict]:
        """
        获取单个研报元数据
        
        Args:
            report_id: 研报 ID
            
        Returns:
            研报元数据 dict 或 None
        """
        return self._reports.get(report_id)

    def get_reports(self, filters: Optional[dict] = None) -> list:
        """
        获取研报列表，支持筛选
        
        Args:
            filters: 筛选条件 dict，支持 stock_code, industry, date_from, date_to
            
        Returns:
            研报列表（合并元数据和解析结果）
        """
        filters = filters or {}
        result = []
        
        for report_id, report in self._reports.items():
            # 获取解析结果（如果有）
            parsed = self._parsed_reports.get(report_id, {})
            
            # 合并数据
            merged = {
                "report_id": report_id,
                "filename": report["filename"],
                "title": parsed.get("title"),
                "stock_code": parsed.get("stock_code"),
                "stock_name": parsed.get("stock_name"),
                "industry": parsed.get("industry"),
                "rating": parsed.get("rating"),
                "parse_status": report["parse_status"],
                "upload_time": report["upload_time"]
            }
            
            # 应用筛选
            if filters.get("stock_code") and merged.get("stock_code") != filters["stock_code"]:
                continue
            if filters.get("industry") and merged.get("industry") != filters["industry"]:
                continue
            if filters.get("date_from") and report["upload_time"] < filters["date_from"]:
                continue
            if filters.get("date_to") and report["upload_time"] > filters["date_to"]:
                continue
                
            result.append(merged)
        
        # 按上传时间倒序排序
        result.sort(key=lambda x: x["upload_time"], reverse=True)
        return result

    def update_report_status(self, report_id: str, status: str) -> dict:
        """
        更新研报解析状态
        
        Args:
            report_id: 研报 ID
            status: 新状态 (pending/parsing/completed/failed)
            
        Returns:
            更新后的研报元数据
            
        Raises:
            KeyError: 研报不存在
        """
        if report_id not in self._reports:
            raise KeyError(f"Report not found: {report_id}")
        
        self._reports[report_id]["parse_status"] = status
        self._persist_all()
        return self._reports[report_id]

    def delete_report(self, report_id: str) -> None:
        """
        删除研报（级联删除）
        
        删除内容包括：
        1. 研报元数据
        2. 解析结果
        3. 知识库中的关联
        4. PDF 文件
        
        Args:
            report_id: 研报 ID
        """
        if report_id not in self._reports:
            raise KeyError(f"Report not found: {report_id}")
        
        # 获取解析结果中的股票代码
        parsed = self._parsed_reports.get(report_id, {})
        stock_code = parsed.get("stock_code")
        
        # 1. 删除研报元数据
        report = self._reports.pop(report_id)
        
        # 2. 删除解析结果
        if report_id in self._parsed_reports:
            del self._parsed_reports[report_id]
        
        # 3. 从知识库移除
        if stock_code:
            self.remove_report_from_stock(stock_code, report_id)
        
        # 4. 删除 PDF 文件
        file_path = report.get("file_path")
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass  # 忽略删除失败
        
        self._persist_all()

    # ==================== 解析结果管理 ====================

    def save_parsed_report(self, report_id: str, parsed_data: dict) -> dict:
        """
        保存解析结果
        
        自动：
        1. 更新 parse_status 为 completed
        2. 将研报添加到知识库
        
        Args:
            report_id: 研报 ID
            parsed_data: 解析结果数据
            
        Returns:
            保存的解析结果
        """
        if report_id not in self._reports:
            raise KeyError(f"Report not found: {report_id}")
        
        # 添加解析元数据
        parsed_data["report_id"] = report_id
        parsed_data["parsed_at"] = self._now_iso()
        
        # 保存解析结果
        self._parsed_reports[report_id] = parsed_data
        
        # 更新状态为 completed
        self._reports[report_id]["parse_status"] = "completed"
        
        # 添加到知识库
        stock_code = parsed_data.get("stock_code")
        stock_name = parsed_data.get("stock_name")
        industry = parsed_data.get("industry")
        
        if stock_code and stock_name:
            self.add_report_to_stock(stock_code, stock_name, industry or "", report_id)
        
        self._persist_all()
        return parsed_data

    def get_parsed_report(self, report_id: str) -> Optional[dict]:
        """
        获取解析结果
        
        Args:
            report_id: 研报 ID
            
        Returns:
            解析结果 dict 或 None
        """
        return self._parsed_reports.get(report_id)

    # ==================== 知识库管理 ====================

    def get_stocks(self) -> list:
        """
        获取知识库股票列表
        
        Returns:
            股票列表，每项包含 stock_code, stock_name, industry, report_count, latest_report_date
        """
        result = []
        for stock_code, stock in self._knowledge_base.items():
            report_ids = stock.get("report_ids", [])
            
            # 计算最新研报日期
            latest_date = None
            for rid in report_ids:
                report = self._reports.get(rid, {})
                upload_time = report.get("upload_time")
                if upload_time and (latest_date is None or upload_time > latest_date):
                    latest_date = upload_time
            
            result.append({
                "stock_code": stock_code,
                "stock_name": stock.get("stock_name", ""),
                "industry": stock.get("industry", ""),
                "report_count": len(report_ids),
                "latest_report_date": latest_date or stock.get("updated_at", "")
            })
        
        # 按最新研报日期倒序排序
        result.sort(key=lambda x: x["latest_report_date"] or "", reverse=True)
        return result

    def get_stock_detail(self, stock_code: str) -> Optional[dict]:
        """
        获取股票详情（含关联研报）
        
        Args:
            stock_code: 股票代码
            
        Returns:
            股票详情 dict 或 None
        """
        stock = self._knowledge_base.get(stock_code)
        if not stock:
            return None
        
        # 获取关联研报列表
        reports = []
        for report_id in stock.get("report_ids", []):
            parsed = self._parsed_reports.get(report_id, {})
            report = self._reports.get(report_id, {})
            if parsed:
                reports.append({
                    "report_id": report_id,
                    "title": parsed.get("title", ""),
                    "rating": parsed.get("rating", ""),
                    "target_price": parsed.get("target_price"),
                    "key_points": parsed.get("key_points", ""),
                    "upload_time": report.get("upload_time", "")
                })
        
        # 按上传时间倒序排序
        reports.sort(key=lambda x: x["upload_time"], reverse=True)
        
        return {
            "stock_code": stock_code,
            "stock_name": stock.get("stock_name", ""),
            "industry": stock.get("industry", ""),
            "report_count": len(reports),
            "recent_summary": stock.get("recent_summary", ""),
            "reports": reports
        }

    def add_report_to_stock(self, stock_code: str, stock_name: str, industry: str, report_id: str) -> dict:
        """
        将研报添加到股票知识库
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            industry: 行业分类
            report_id: 研报 ID
            
        Returns:
            股票知识库条目
        """
        if stock_code not in self._knowledge_base:
            # 创建新的股票条目
            self._knowledge_base[stock_code] = {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "industry": industry,
                "report_ids": [],
                "recent_summary": "",
                "updated_at": self._now_iso()
            }
        
        stock = self._knowledge_base[stock_code]
        
        # 更新股票名称和行业（可能变化）
        stock["stock_name"] = stock_name
        if industry:
            stock["industry"] = industry
        
        # 添加研报关联（避免重复）
        if report_id not in stock["report_ids"]:
            stock["report_ids"].append(report_id)
        
        stock["updated_at"] = self._now_iso()
        
        # 生成观点汇总（简单拼接，实际可由 LLM 生成）
        self._update_stock_summary(stock_code)
        
        self._persist_all()
        return stock

    def remove_report_from_stock(self, stock_code: str, report_id: str) -> None:
        """
        从知识库移除研报
        
        Args:
            stock_code: 股票代码
            report_id: 研报 ID
        """
        if stock_code not in self._knowledge_base:
            return
        
        stock = self._knowledge_base[stock_code]
        
        # 从 report_ids 中移除
        if report_id in stock["report_ids"]:
            stock["report_ids"].remove(report_id)
        
        # 如果没有关联研报了，删除整个股票条目
        if not stock["report_ids"]:
            del self._knowledge_base[stock_code]
        else:
            # 重新生成观点汇总
            self._update_stock_summary(stock_code)
            stock["updated_at"] = self._now_iso()
        
        self._persist_all()

    def update_stock_summary(self, stock_code: str, summary: str) -> dict:
        """
        更新股票观点汇总
        
        Args:
            stock_code: 股票代码
            summary: 新的观点汇总
            
        Returns:
            更新后的股票条目
        """
        if stock_code not in self._knowledge_base:
            raise KeyError(f"Stock not found: {stock_code}")
        
        self._knowledge_base[stock_code]["recent_summary"] = summary
        self._knowledge_base[stock_code]["updated_at"] = self._now_iso()
        self._persist_all()
        return self._knowledge_base[stock_code]

    def _update_stock_summary(self, stock_code: str) -> None:
        """
        自动生成股票观点汇总（内部方法）
        
        简单实现：按时间倒序拼接各研报的核心观点
        可由 KnowledgeBaseManager 调用 LLM 生成更智能的汇总
        """
        stock = self._knowledge_base.get(stock_code)
        if not stock:
            return
        
        key_points_list = []
        for report_id in stock.get("report_ids", []):
            parsed = self._parsed_reports.get(report_id, {})
            key_points = parsed.get("key_points")
            if key_points:
                key_points_list.append(key_points)
        
        if key_points_list:
            # 简单拼接（最多取前5条）
            stock["recent_summary"] = "；".join(key_points_list[:5])
        else:
            stock["recent_summary"] = ""

    def get_pdf_path(self, report_id: str) -> Optional[str]:
        """
        获取 PDF 文件路径
        
        Args:
            report_id: 研报 ID
            
        Returns:
            PDF 文件路径或 None
        """
        report = self._reports.get(report_id)
        if report:
            return report.get("file_path")
        return None
