"""
Parser 单元测试
对齐 spec/01-后端Task1-研报上传与解析.md §6.2
"""

import os
import sys
import unittest
import tempfile
import json
from unittest.mock import Mock, patch, MagicMock

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser import ReportParser, ParseError, LLMError


class TestReportParser(unittest.TestCase):
    """ReportParser 单元测试"""

    def setUp(self):
        """测试前准备"""
        # 创建临时目录
        self.test_dir = tempfile.mkdtemp()
        
        # 创建测试 PDF 文件（模拟）
        self.test_pdf_path = os.path.join(self.test_dir, "test_report.pdf")
        # 创建一个简单的文本文件作为模拟 PDF
        with open(self.test_pdf_path, 'w', encoding='utf-8') as f:
            f.write("This is a test PDF content for testing purposes.")
    
    def tearDown(self):
        """测试后清理"""
        # 清理临时文件
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_init_without_api_key(self):
        """TC-M02-080: 无 API Key 时初始化，LLM 客户端为 None"""
        parser = ReportParser()
        self.assertIsNone(parser._llm_client)
        self.assertEqual(parser.llm_base_url, "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.assertEqual(parser.llm_model, "qwen-plus")

    def test_init_with_api_key(self):
        """TC-M02-081: 有 API Key 时初始化 LLM 客户端"""
        # Mock openai 导入
        with patch('parser.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            
            parser = ReportParser(llm_api_key="test-key", llm_model="test-model")
            
            mock_openai.assert_called_once_with(
                api_key="test-key",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
            self.assertIsNotNone(parser._llm_client)
            self.assertEqual(parser.llm_model, "test-model")

    def test_normalize_rating(self):
        """TC-M02-082: 评级字段规范化"""
        parser = ReportParser()
        
        # 标准值
        self.assertEqual(parser._normalize_rating("买入"), "买入")
        self.assertEqual(parser._normalize_rating("增持"), "增持")
        self.assertEqual(parser._normalize_rating("中性"), "中性")
        
        # 英文映射
        self.assertEqual(parser._normalize_rating("buy"), "买入")
        self.assertEqual(parser._normalize_rating("BUY"), "买入")
        self.assertEqual(parser._normalize_rating("add"), "增持")
        self.assertEqual(parser._normalize_rating("neutral"), "中性")
        
        # 空值处理
        self.assertEqual(parser._normalize_rating(None), "未提及")
        self.assertEqual(parser._normalize_rating(""), "未提及")
        
        # 未知值
        self.assertEqual(parser._normalize_rating("unknown"), "未提及")

    def test_normalize_target_price(self):
        """TC-M02-083: 目标价格式化"""
        parser = ReportParser()
        
        # 数字
        self.assertEqual(parser._normalize_target_price(150), 150.0)
        self.assertEqual(parser._normalize_target_price(150.5), 150.5)
        
        # 字符串
        self.assertEqual(parser._normalize_target_price("150"), 150.0)
        self.assertEqual(parser._normalize_target_price("150.5元"), 150.5)
        self.assertEqual(parser._normalize_target_price("¥150.5"), 150.5)
        
        # 空值
        self.assertIsNone(parser._normalize_target_price(None))
        self.assertIsNone(parser._normalize_target_price(""))
        self.assertIsNone(parser._normalize_target_price("未提及"))

    def test_normalize_stock_code(self):
        """TC-M02-084: 股票代码规范化"""
        parser = ReportParser()
        
        # 标准6位
        self.assertEqual(parser._normalize_stock_code("600519"), "600519")
        
        # 带空格
        self.assertEqual(parser._normalize_stock_code(" 600519 "), "600519")
        
        # 带其他字符
        self.assertEqual(parser._normalize_stock_code("sh600519"), "600519")
        
        # 从文本提取
        self.assertEqual(parser._normalize_stock_code("股票代码：600519"), "600519")

    def test_parse_llm_response_valid_json(self):
        """TC-M02-085: 解析有效的 LLM JSON 响应"""
        parser = ReportParser()
        
        valid_response = json.dumps({
            "title": "贵州茅台研究报告",
            "rating": "买入",
            "target_price": 2100,
            "key_points": "业绩稳健增长",
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "industry": "白酒"
        })
        
        result = parser._parse_llm_response(valid_response)
        
        self.assertEqual(result["title"], "贵州茅台研究报告")
        self.assertEqual(result["rating"], "买入")
        self.assertEqual(result["target_price"], 2100)

    def test_parse_llm_response_with_markdown(self):
        """TC-M02-086: 解析带 markdown 代码块的响应"""
        parser = ReportParser()
        
        markdown_response = '''```json
        {
            "title": "测试报告",
            "rating": "增持",
            "target_price": null,
            "key_points": "测试",
            "stock_code": "000001",
            "stock_name": "平安银行",
            "industry": "银行"
        }
        ```'''
        
        result = parser._parse_llm_response(markdown_response)
        
        self.assertEqual(result["title"], "测试报告")
        self.assertEqual(result["rating"], "增持")

    def test_parse_llm_response_invalid_json(self):
        """TC-M02-087: 解析无效的 JSON 响应应抛出 LLMError"""
        parser = ReportParser()
        
        invalid_response = "这不是有效的 JSON"
        
        with self.assertRaises(LLMError) as context:
            parser._parse_llm_response(invalid_response)
        
        self.assertIn("Failed to parse LLM response", str(context.exception))

    def test_normalize_result(self):
        """TC-M02-088: 结果规范化"""
        parser = ReportParser()
        
        raw_result = {
            "title": " 测试标题 ",
            "rating": " BUY ",
            "target_price": "150.5元",
            "key_points": " 核心观点 ",
            "stock_code": "sh600519",
            "stock_name": " 贵州茅台 ",
            "industry": " 白酒 "
        }
        
        normalized = parser._normalize_result(raw_result)
        
        self.assertEqual(normalized["title"], "测试标题")
        self.assertEqual(normalized["rating"], "买入")  # BUY -> 买入
        self.assertEqual(normalized["target_price"], 150.5)
        self.assertEqual(normalized["stock_code"], "600519")

    @patch('parser.ReportParser.extract_text')
    @patch('parser.ReportParser.parse_report')
    def test_process_success(self, mock_parse, mock_extract):
        """TC-M02-089: process 方法成功流程"""
        parser = ReportParser(llm_api_key="test-key")
        
        # Mock 返回值
        mock_extract.return_value = "提取的文本内容"
        mock_parse.return_value = {
            "title": "测试报告",
            "rating": "买入",
            "target_price": 100.0,
            "key_points": "测试观点",
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "industry": "白酒",
            "raw_text": "提取的文本内容"
        }
        
        result = parser.process(self.test_pdf_path)
        
        self.assertEqual(result["title"], "测试报告")
        self.assertIn("parse_time_ms", result)
        self.assertGreaterEqual(result["parse_time_ms"], 0)

    @patch('parser.ReportParser.extract_text')
    def test_process_parse_error(self, mock_extract):
        """TC-M02-090: process 方法 PDF 提取失败"""
        parser = ReportParser(llm_api_key="test-key")
        
        # Mock 抛出异常
        mock_extract.side_effect = ParseError("PDF 提取失败")
        
        with self.assertRaises(ParseError):
            parser.process(self.test_pdf_path)

    def test_mock_parse(self):
        """TC-M02-091: mock_parse 方法返回模拟数据"""
        parser = ReportParser()
        
        # 创建一个可读的文件用于测试
        with patch.object(parser, '_extract_with_pypdf2') as mock_extract:
            mock_extract.return_value = "测试文本内容"
            
            result = parser.mock_parse(self.test_pdf_path)
            
            self.assertEqual(result["title"], "模拟研报标题")
            self.assertEqual(result["rating"], "买入")
            self.assertEqual(result["stock_code"], "600519")
            self.assertIn("parse_time_ms", result)


class TestParseError(unittest.TestCase):
    """ParseError 异常测试"""

    def test_parse_error_is_exception(self):
        """ParseError 是 Exception 的子类"""
        self.assertTrue(issubclass(ParseError, Exception))

    def test_parse_error_message(self):
        """ParseError 可以携带错误信息"""
        error = ParseError("PDF 提取失败")
        self.assertEqual(str(error), "PDF 提取失败")


class TestLLMError(unittest.TestCase):
    """LLMError 异常测试"""

    def test_llm_error_is_exception(self):
        """LLMError 是 Exception 的子类"""
        self.assertTrue(issubclass(LLMError, Exception))

    def test_llm_error_message(self):
        """LLMError 可以携带错误信息"""
        error = LLMError("API 调用失败")
        self.assertEqual(str(error), "API 调用失败")


if __name__ == '__main__':
    unittest.main()
