import json
import time
import logging

logger = logging.getLogger(__name__)


class ParseError(Exception):
    pass


class LLMError(Exception):
    pass


class ReportParser:
    """PDF 文本提取 + LLM 结构化解析引擎"""

    SYSTEM_PROMPT = (
        "你是一个专业的金融研报解析助手。请从以下研报文本中提取结构化信息，"
        "严格以 JSON 格式输出，不要输出其他内容。\n"
        "必须提取的字段：\n"
        "- title: 研报标题（字符串）\n"
        "- rating: 投资评级，只能是以下之一：买入、增持、中性、减持、卖出、未提及\n"
        "- target_price: 目标价（数字，若未提及则为 null）\n"
        "- key_points: 核心观点摘要（字符串）\n"
        "- stock_code: 6位股票代码（字符串）\n"
        "- stock_name: 股票名称（字符串）\n"
        "- industry: 行业分类（字符串）\n"
    )

    def __init__(self, llm_api_key=None, llm_base_url=None, llm_model=None):
        self.llm_api_key = llm_api_key
        self.llm_base_url = llm_base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.llm_model = llm_model or "qwen-plus"
        self._client = None
        if llm_api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=llm_api_key, base_url=self.llm_base_url)
            except ImportError:
                logger.warning("openai package not installed, LLM features unavailable")

    def extract_text(self, pdf_path):
        text = ""
        try:
            import PyPDF2
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            logger.warning(f"PyPDF2 extraction failed: {e}, trying pdfplumber")
            try:
                import pdfplumber
                with pdfplumber.open(pdf_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
            except Exception as e2:
                raise ParseError(f"PDF text extraction failed: {e2}")
        if not text.strip():
            raise ParseError("No text extracted from PDF")
        return text

    def parse_report(self, raw_text):
        if not self._client:
            raise LLMError("LLM client not configured")
        try:
            response = self._client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"请解析以下研报文本：\n\n{raw_text[:8000]}"},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            content = response.choices[0].message.content
            result = json.loads(content)
            valid_ratings = {"买入", "增持", "中性", "减持", "卖出", "未提及"}
            if result.get("rating") not in valid_ratings:
                result["rating"] = "未提及"
            if result.get("target_price") is not None:
                try:
                    result["target_price"] = float(result["target_price"])
                except (ValueError, TypeError):
                    result["target_price"] = None
            return result
        except json.JSONDecodeError as e:
            raise LLMError(f"LLM returned invalid JSON: {e}")
        except Exception as e:
            raise LLMError(f"LLM API error: {e}")

    def process(self, pdf_path):
        start = time.time()
        raw_text = self.extract_text(pdf_path)
        parsed = self.parse_report(raw_text)
        parsed["raw_text"] = raw_text
        parsed["parse_time_ms"] = int((time.time() - start) * 1000)
        return parsed
