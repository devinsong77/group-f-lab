"""
Parser 引擎 - PDF 文本提取 + LLM 结构化解析
对齐 spec/08-系统架构与技术选型.md §4.1
"""

import json
import re
import time
from typing import Optional


class ParseError(Exception):
    """PDF 提取或解析错误"""
    pass


class LLMError(Exception):
    """LLM API 调用错误"""
    pass


class ReportParser:
    """
    研报解析引擎
    
    功能：
    1. PDF 文本提取（PyPDF2 / pdfplumber）
    2. LLM 结构化解析（提取核心字段）
    """

    # 评级枚举值
    RATING_ENUM = ["买入", "增持", "中性", "减持", "卖出", "未提及"]

    # LLM Prompt 模板
    SYSTEM_PROMPT = """你是一位专业的金融研报分析助手。请从用户提供的研报文本中提取关键信息，并以严格的 JSON 格式返回。

你需要提取以下字段：
- title: 研报标题（字符串，必填）
- rating: 投资评级（字符串，必须是以下之一：买入、增持、中性、减持、卖出、未提及）
- target_price: 目标价（数字，单位：元；如果未提及则返回 null）
- key_points: 核心观点摘要（字符串，100-300字，概括研报的主要投资逻辑和结论）
- stock_code: 股票代码（字符串，6位数字）
- stock_name: 股票名称（字符串）
- industry: 行业分类（字符串，如：白酒、新能源、医药等）

输出要求：
1. 必须返回合法的 JSON 格式，不要包含任何其他文字说明
2. 不要包含 markdown 代码块标记
3. 确保所有字段都存在，即使值为 null 或空字符串
4. rating 字段必须是规定的枚举值之一
5. target_price 如果是数字，不要带单位"""

    USER_PROMPT_TEMPLATE = """请分析以下研报内容并提取关键信息：

---
{raw_text}
---

请严格按照系统指令返回 JSON 格式结果。"""

    def __init__(self, llm_api_key: Optional[str] = None, llm_base_url: Optional[str] = None, llm_model: Optional[str] = None):
        """
        初始化 Parser
        
        Args:
            llm_api_key: LLM API 密钥
            llm_base_url: LLM API 地址
            llm_model: LLM 模型名称
        """
        self.llm_api_key = llm_api_key
        self.llm_base_url = llm_base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.llm_model = llm_model or "qwen-plus"
        self._llm_client = None
        
        # 延迟初始化 LLM 客户端
        if llm_api_key:
            self._init_llm_client()

    def _init_llm_client(self):
        """初始化 LLM 客户端"""
        try:
            from openai import OpenAI
            self._llm_client = OpenAI(
                api_key=self.llm_api_key,
                base_url=self.llm_base_url
            )
        except ImportError:
            raise LLMError("OpenAI client not installed. Run: pip install openai")
        except Exception as e:
            raise LLMError(f"Failed to initialize LLM client: {str(e)}")

    def extract_text(self, pdf_path: str) -> str:
        """
        从 PDF 提取文本
        
        优先使用 PyPDF2，失败时 fallback 到 pdfplumber
        
        Args:
            pdf_path: PDF 文件路径
            
        Returns:
            提取的文本内容
            
        Raises:
            ParseError: 提取失败
        """
        text = None
        errors = []
        
        # 尝试 PyPDF2
        try:
            text = self._extract_with_pypdf2(pdf_path)
            if text and len(text.strip()) > 100:
                return text
        except Exception as e:
            errors.append(f"PyPDF2: {str(e)}")
        
        # Fallback 到 pdfplumber
        try:
            text = self._extract_with_pdfplumber(pdf_path)
            if text and len(text.strip()) > 100:
                return text
        except Exception as e:
            errors.append(f"pdfplumber: {str(e)}")
        
        # 都失败了
        raise ParseError(f"Failed to extract text from PDF: {'; '.join(errors)}")

    def _extract_with_pypdf2(self, pdf_path: str) -> str:
        """使用 PyPDF2 提取文本"""
        try:
            import PyPDF2
        except ImportError:
            raise ImportError("PyPDF2 not installed. Run: pip install PyPDF2")
        
        text_parts = []
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        
        return "\n".join(text_parts)

    def _extract_with_pdfplumber(self, pdf_path: str) -> str:
        """使用 pdfplumber 提取文本"""
        try:
            import pdfplumber
        except ImportError:
            raise ImportError("pdfplumber not installed. Run: pip install pdfplumber")
        
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        
        return "\n".join(text_parts)

    def parse_report(self, raw_text: str) -> dict:
        """
        使用 LLM 解析研报文本
        
        Args:
            raw_text: PDF 提取的原始文本
            
        Returns:
            解析结果 dict，包含：
            - title: 研报标题
            - rating: 投资评级
            - target_price: 目标价
            - key_points: 核心观点
            - stock_code: 股票代码
            - stock_name: 股票名称
            - industry: 行业分类
            - raw_text: 原始文本（用于比对分析）
            
        Raises:
            LLMError: LLM API 调用失败
        """
        if not self._llm_client:
            raise LLMError("LLM client not initialized. Please provide llm_api_key.")
        
        # 截断文本（避免超出 token 限制）
        max_chars = 15000
        truncated_text = raw_text[:max_chars] if len(raw_text) > max_chars else raw_text
        
        user_prompt = self.USER_PROMPT_TEMPLATE.format(raw_text=truncated_text)
        
        try:
            response = self._llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # 低温度，更确定性的输出
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            parsed = self._parse_llm_response(content)
            
            # 添加原始文本（用于比对分析）
            parsed["raw_text"] = raw_text
            
            return parsed
            
        except Exception as e:
            raise LLMError(f"LLM API call failed: {str(e)}")

    def _parse_llm_response(self, content: str) -> dict:
        """
        解析 LLM 返回的 JSON
        
        Args:
            content: LLM 返回的文本内容
            
        Returns:
            解析后的 dict
        """
        # 清理可能的 markdown 代码块
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        try:
            result = json.loads(content)
        except json.JSONDecodeError as e:
            # 尝试提取 JSON 部分
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                except json.JSONDecodeError:
                    raise LLMError(f"Failed to parse LLM response as JSON: {str(e)}")
            else:
                raise LLMError(f"Failed to parse LLM response as JSON: {str(e)}")
        
        # 验证和规范化字段
        return self._normalize_result(result)

    def _normalize_result(self, result: dict) -> dict:
        """
        规范化解析结果
        
        Args:
            result: 原始解析结果
            
        Returns:
            规范化后的结果
        """
        normalized = {
            "title": str(result.get("title", "")).strip(),
            "rating": self._normalize_rating(result.get("rating", "")),
            "target_price": self._normalize_target_price(result.get("target_price")),
            "key_points": str(result.get("key_points", "")).strip(),
            "stock_code": self._normalize_stock_code(result.get("stock_code", "")),
            "stock_name": str(result.get("stock_name", "")).strip(),
            "industry": str(result.get("industry", "")).strip()
        }
        
        return normalized

    def _normalize_rating(self, rating: any) -> str:
        """规范化评级字段"""
        if not rating:
            return "未提及"
        
        rating_str = str(rating).strip()
        
        # 映射常见变体
        rating_map = {
            "buy": "买入",
            "add": "增持",
            "accumulate": "增持",
            "neutral": "中性",
            "hold": "中性",
            "reduce": "减持",
            "sell": "卖出",
            "strong buy": "买入",
            "outperform": "增持",
            "underperform": "减持"
        }
        
        # 尝试直接匹配
        if rating_str in self.RATING_ENUM:
            return rating_str
        
        # 尝试映射
        lower_rating = rating_str.lower()
        if lower_rating in rating_map:
            return rating_map[lower_rating]
        
        # 包含匹配
        for enum_val in self.RATING_ENUM:
            if enum_val in rating_str:
                return enum_val
        
        return "未提及"

    def _normalize_target_price(self, price: any) -> Optional[float]:
        """规范化目标价字段"""
        if price is None:
            return None
        
        if isinstance(price, (int, float)):
            return float(price) if price > 0 else None
        
        # 尝试从字符串解析
        price_str = str(price).strip()
        
        # 移除常见单位
        price_str = price_str.replace("元", "").replace("¥", "").replace(",", "").replace("，", "")
        
        # 提取数字
        match = re.search(r'(\d+\.?\d*)', price_str)
        if match:
            try:
                val = float(match.group(1))
                return val if val > 0 else None
            except ValueError:
                pass
        
        return None

    def _normalize_stock_code(self, code: any) -> str:
        """规范化股票代码"""
        if not code:
            return ""
        
        code_str = str(code).strip()
        
        # 移除可能的空格和符号
        code_str = re.sub(r'[^\d]', '', code_str)
        
        # 确保是6位
        if len(code_str) == 6:
            return code_str
        
        # 尝试从文本中提取6位数字
        match = re.search(r'\b(\d{6})\b', str(code))
        if match:
            return match.group(1)
        
        return code_str

    def process(self, pdf_path: str) -> dict:
        """
        完整解析流程：提取文本 + LLM 解析
        
        Args:
            pdf_path: PDF 文件路径
            
        Returns:
            完整解析结果，包含 parse_time_ms
            
        Raises:
            ParseError: PDF 提取失败
            LLMError: LLM 解析失败
        """
        start_time = time.time()
        
        # 1. 提取文本
        raw_text = self.extract_text(pdf_path)
        
        # 2. LLM 解析
        parsed = self.parse_report(raw_text)
        
        # 3. 计算耗时
        parse_time_ms = int((time.time() - start_time) * 1000)
        parsed["parse_time_ms"] = parse_time_ms
        
        return parsed

    def mock_parse(self, pdf_path: str) -> dict:
        """
        Mock 解析（用于测试，不调用 LLM）
        
        Args:
            pdf_path: PDF 文件路径
            
        Returns:
            模拟的解析结果
        """
        start_time = time.time()
        
        # 提取文本
        raw_text = self.extract_text(pdf_path)
        
        # 模拟解析结果
        result = {
            "title": "模拟研报标题",
            "rating": "买入",
            "target_price": 150.00,
            "key_points": "这是模拟的核心观点摘要，用于测试目的。",
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "industry": "白酒",
            "raw_text": raw_text,
            "parse_time_ms": int((time.time() - start_time) * 1000)
        }
        
        return result
