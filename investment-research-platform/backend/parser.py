"""ReportParser — PDF text extraction + LLM structured parsing."""
from __future__ import annotations

import json
import time
import os


class ParseError(Exception):
    """Raised when PDF text extraction fails."""
    pass


class LLMError(Exception):
    """Raised when LLM service is unavailable."""
    pass


class ReportParser:
    def __init__(
        self,
        llm_api_key: str | None = None,
        llm_base_url: str | None = None,
        llm_model: str | None = None,
        llm_fallback_model: str | None = None,
    ):
        self.llm_api_key = llm_api_key
        self.llm_base_url = llm_base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.llm_model = llm_model or "qwen3.5-plus"
        self.llm_fallback_model = llm_fallback_model or "glm-4-flash"
        self._client = None
        if llm_api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=llm_api_key, base_url=self.llm_base_url)
            except ImportError:
                pass

    def extract_text(self, pdf_path: str) -> str:
        """Extract text from PDF. Try PyPDF2 first, fallback to pdfplumber."""
        if not os.path.exists(pdf_path):
            raise ParseError(f"PDF file not found: {pdf_path}")

        text = ""
        # Try PyPDF2 first
        try:
            import PyPDF2
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            if text.strip():
                return text.strip()
        except Exception:
            pass

        # Fallback to pdfplumber
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            if text.strip():
                return text.strip()
        except Exception:
            pass

        if not text.strip():
            raise ParseError("Failed to extract text from PDF")
        return text.strip()

    def _call_llm(self, model: str, system_prompt: str, user_content: str) -> dict:
        """Call LLM with given model and return parsed JSON dict."""
        response = self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
        )
        content = response.choices[0].message.content
        # Strip markdown code block if present
        if content.strip().startswith("```"):
            lines = content.strip().split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            content = "\n".join(lines)
        return json.loads(content)

    def parse_report(self, raw_text: str) -> dict:
        """Use LLM to parse report text into structured data.

        Strategy: try primary model (Qwen3.5) first, fallback to GLM on failure.
        """
        if not self._client:
            raise LLMError("LLM client not configured (missing API key)")

        system_prompt = """你是一个专业的金融研报分析助手。请从用户提供的研报文本中提取以下字段，以严格JSON格式返回：
{
  "title": "研报标题（字符串）",
  "rating": "投资评级，必须是以下之一：买入、增持、中性、减持、卖出、未提及",
  "target_price": 目标价格（数字，如未提及返回null），
  "key_points": "核心观点摘要（字符串，200字以内）",
  "stock_code": "6位股票代码（字符串）",
  "stock_name": "股票名称（字符串）",
  "industry": "行业分类（字符串）"
}
请只返回JSON，不要添加任何其他文字。"""

        user_content = f"请分析以下研报文本：\n\n{raw_text[:8000]}"
        models = [self.llm_model, self.llm_fallback_model]
        last_error = None

        for model in models:
            try:
                result = self._call_llm(model, system_prompt, user_content)
                # Validate rating enum
                valid_ratings = {"买入", "增持", "中性", "减持", "卖出", "未提及"}
                if result.get("rating") not in valid_ratings:
                    result["rating"] = "未提及"
                result["_llm_model_used"] = model
                return result
            except json.JSONDecodeError as e:
                last_error = LLMError(f"LLM ({model}) returned invalid JSON: {e}")
            except Exception as e:
                last_error = LLMError(f"LLM ({model}) service error: {e}")

        raise last_error or LLMError("All LLM models failed")

    def process(self, pdf_path: str) -> dict:
        """Full pipeline: extract text → LLM parse → return result."""
        start = time.time()
        raw_text = self.extract_text(pdf_path)
        parsed = self.parse_report(raw_text)
        elapsed_ms = int((time.time() - start) * 1000)
        parsed["raw_text"] = raw_text
        parsed["parse_time_ms"] = elapsed_ms
        return parsed
