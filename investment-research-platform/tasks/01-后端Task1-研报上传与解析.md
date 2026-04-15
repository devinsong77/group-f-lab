# 01 — 后端 Task1：研报上传与解析

---

| 项 | 值 |
|---|---|
| 模块编号 | M2-IRA |
| 任务编号 | Backend-Task1 |
| 交付阶段 | **S1** |
| 涉及 WBS | W1(upload/parse 路由), W2(Storage 基础), W3(Parser 引擎) |
| 覆盖需求 | REQ-M2IRA-001（研报上传）、REQ-M2IRA-002（研报解析） |
| 关联前端 | ReportManager 页面上传区 + 解析结果展示 |

---

## 1. 任务目标

实现研报上传与 LLM 自动解析的完整后端链路：用户上传 PDF → 服务端存储 → PDF 文本提取 → LLM 结构化解析 → 6 个核心字段入库 → 自动入知识库。

## 2. 涉及文件

| 文件 | 职责 | 新建/修改 |
|------|------|-----------|
| `backend/app.py` | Flask 应用入口，注册 Blueprint，CORS 配置 | 新建 |
| `backend/blueprints/report_bp.py` | 研报上传 + 解析 API 路由 | 新建 |
| `backend/parser.py` | PDF 文本提取 + LLM 结构化解析引擎 | 新建 |
| `backend/storage.py` | 内存数据库 + JSON 持久化 + PDF 文件管理 | 新建 |
| `backend/tests/test_parser.py` | Parser 单元测试 | 新建 |

## 3. 详细实现步骤

### 3.1 Storage 层基础（storage.py）

**实现 `Storage` 类**，对齐 `10` 数据模型：

```python
class Storage:
    def __init__(self, data_dir="data"):
        # 初始化目录结构
        # 启动时从 JSON 加载数据到内存 dict
        # JSON 文件: reports.json, parsed_reports.json, knowledge_base.json

    def save_report(self, report_id, filename, file_path) -> dict:
        # 保存研报元数据，parse_status 初始为 "pending"
        # 写回 reports.json

    def get_report(self, report_id) -> dict | None:
        # 从内存返回单个研报

    def update_report_status(self, report_id, status) -> dict:
        # 更新 parse_status（pending/parsing/completed/failed）
        # 写回 JSON

    def save_parsed_report(self, report_id, parsed_data) -> dict:
        # 保存解析结果
        # 更新 parse_status 为 completed
        # 调用知识库入库逻辑（add_report_to_stock）
        # 写回 parsed_reports.json + knowledge_base.json

    def get_parsed_report(self, report_id) -> dict | None:
        # 返回解析结果

    def add_report_to_stock(self, stock_code, stock_name, industry, report_id) -> dict:
        # 将研报添加到对应股票的知识库
        # 如果股票不存在则新建条目
```

**数据实体**（对齐 `10`）：

Report:
| 字段 | 类型 | 说明 |
|------|------|------|
| `report_id` | string (UUID) | PK |
| `filename` | string | 原始文件名 |
| `file_path` | string | 服务端存储路径 |
| `parse_status` | string | pending/parsing/completed/failed |
| `upload_time` | string (ISO-8601) | 上传时间 |

ParsedReport:
| 字段 | 类型 | 说明 |
|------|------|------|
| `report_id` | string | PK/FK → Report |
| `title` | string | 研报标题 |
| `rating` | string | 买入/增持/中性/减持/卖出/未提及 |
| `target_price` | number\|null | 目标价（元） |
| `key_points` | string | 核心观点摘要 |
| `stock_code` | string | 6 位股票代码 |
| `stock_name` | string | 股票名称 |
| `industry` | string | 行业分类 |
| `raw_text` | string | PDF 原始文本 |
| `parse_time_ms` | integer | 解析耗时 |
| `parsed_at` | string (ISO-8601) | 解析完成时间 |

### 3.2 Parser 引擎（parser.py）

**实现 `ReportParser` 类**，对齐 `08` §4.1：

```python
class ReportParser:
    def __init__(self, llm_api_key, llm_base_url):
        # 初始化 LLM 客户端

    def extract_text(self, pdf_path: str) -> str:
        # PDF 文本提取
        # 优先 PyPDF2，失败时 fallback 到 pdfplumber
        # 提取失败抛出 ParseError

    def parse_report(self, raw_text: str) -> dict:
        # LLM 结构化解析
        # Prompt 模板 → 返回 JSON
        # 提取字段: title, rating, target_price, key_points, stock_code, stock_name, industry
        # LLM 不可用时抛出 LLMError

    def process(self, pdf_path: str) -> dict:
        # 完整流程: extract_text → parse_report
        # 返回解析结果 dict
```

**LLM Prompt 设计要点**：
- 系统 Prompt 与用户输入隔离（对齐 `11` §5 LLM 安全）
- 输出格式为严格 JSON
- 提取 6 个核心字段 + industry
- rating 限制为枚举值
- target_price 未提及时返回 null

### 3.3 API 路由 — 研报上传（report_bp.py）

**`POST /api/v1/reports/upload`**（对齐 `09` §3）：

请求：`multipart/form-data`，字段 `file`

处理流程：
1. 校验文件类型 → 非 PDF 返回 400 `INVALID_FILE_TYPE`
2. 校验文件大小 → > 50MB 返回 400 `FILE_TOO_LARGE`
3. 生成 report_id（UUID）
4. 保存 PDF 到 `{DATA_DIR}/reports/{report_id}.pdf`
5. 调用 `storage.save_report()` 保存元数据
6. 返回 201

响应字段：
```json
{
  "traceId": "tr_...",
  "report_id": "uuid",
  "filename": "研报.pdf",
  "file_path": "data/reports/uuid.pdf",
  "upload_time": "2026-04-15T10:00:00Z",
  "parse_status": "pending"
}
```

### 3.4 API 路由 — 触发解析（report_bp.py）

**`POST /api/v1/reports/{id}/parse`**（对齐 `09` §4）：

处理流程：
1. 校验 report_id 存在 → 不存在返回 404 `REPORT_NOT_FOUND`
2. 更新 parse_status 为 "parsing"
3. 调用 `parser.process(pdf_path)` 执行解析
4. 成功：调用 `storage.save_parsed_report()` 保存结果（含自动入知识库）
5. 失败：更新 parse_status 为 "failed"，返回 500 `PARSE_FAILED` 或 `LLM_ERROR`
6. 返回 200 + 解析结果

响应字段：
```json
{
  "traceId": "tr_...",
  "report_id": "uuid",
  "parse_status": "completed",
  "title": "...",
  "rating": "买入",
  "target_price": 150.00,
  "key_points": "...",
  "stock_code": "600519",
  "stock_name": "贵州茅台",
  "industry": "白酒",
  "parse_time_ms": 5000
}
```

### 3.5 Flask 应用入口（app.py）

```python
# 创建 Flask app
# 注册 report_bp (url_prefix="/api/v1")
# 配置 CORS（全开放，对齐 07 §4）
# 初始化 Storage 实例（全局单例）
# 初始化 ReportParser 实例
# 配置项从环境变量读取：LLM_API_KEY, LLM_BASE_URL, DATA_DIR
```

### 3.6 traceId 机制

所有端点统一注入 traceId（对齐 `07` §3.1）：
- 格式：`tr_{uuid.hex}`（32 位十六进制）
- 优先复用请求头 `X-Trace-Id`
- 缺省时本地生成
- 成功响应顶层 + 错误响应 `error.traceId`

## 4. 前后端交互约定

### 4.1 前端调用流程

```
[前端 ReportManager]
  │
  ├── 用户选择 PDF 文件
  ├── POST /api/v1/reports/upload (multipart/form-data)
  │   ← 返回 { report_id, parse_status: "pending" }
  │
  ├── 自动触发: POST /api/v1/reports/{report_id}/parse
  │   ← 返回 { parse_status: "completed", title, rating, ... }
  │   或 ← 返回 { error: { code: "PARSE_FAILED", ... } }
  │
  └── 刷新研报列表（GET /api/v1/reports）
```

### 4.2 前端需处理的错误码

| error.code | HTTP | 前端展示 |
|-----------|------|----------|
| `INVALID_FILE_TYPE` | 400 | "仅支持 PDF 格式文件" |
| `FILE_TOO_LARGE` | 400 | "文件大小不能超过 50MB" |
| `PARSE_FAILED` | 500 | "研报解析失败，请检查文件格式" |
| `LLM_ERROR` | 500 | "AI 服务暂时不可用，请稍后重试" |
| `REPORT_NOT_FOUND` | 404 | "研报不存在或已被删除" |

### 4.3 前端 UI 状态映射

| parse_status | 前端展示 |
|-------------|----------|
| pending | 状态标签：待解析（灰色） |
| parsing | 状态标签：解析中...（蓝色，可加 loading 动画） |
| completed | 展示解析结果（标题、评级、目标价等） |
| failed | 状态标签：解析失败（红色），可重新触发解析 |

## 5. 环境配置

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `LLM_API_KEY` | 百炼平台 API 密钥 | `sk-f47c2e9de62c4375800379e938e2c25b` |
| `LLM_BASE_URL` | 百炼 DashScope API 地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `LLM_MODEL` | 主模型名称（阿里百炼 Qwen3.5） | `qwen3.5-plus` |
| `LLM_FALLBACK_MODEL` | 备用模型名称（百炼 GLM） | `glm-4-flash` |
| `DATA_DIR` | 数据存储目录 | `data` |
| `TEST_DATA_DIR` | 测试数据目录 | `test_data` |

### 5.1 LLM 模型选型说明

| 角色 | 模型 | 平台 | 说明 |
|------|------|------|------|
| 主模型 | `qwen3.5-plus` | 阿里百炼（DashScope） | Qwen3.5 系列商业版，效果好、速度快 |
| 备用模型 | `glm-4-flash` | 阿里百炼（第三方接入） | GLM-4 系列轻量版，主模型异常时自动降级 |

**降级策略**：研报解析时优先调用 Qwen3.5-Plus，若主模型返回异常（超时/错误/JSON 解析失败），自动重试备用模型 GLM-4-Flash，两个模型均失败时返回 `LLM_ERROR`。

## 6. 测试用例

### 6.1 集成测试（对齐 `13` §3.1 + §3.2）

| TC-ID | 断言要点 | 优先级 |
|-------|----------|--------|
| TC-M02-001 | `POST /reports/upload` PDF → 201, 含 report_id, parse_status="pending" | P0 |
| TC-M02-002 | 上传非 PDF → 400, `INVALID_FILE_TYPE` | P0 |
| TC-M02-003 | 上传 > 50MB → 400, `FILE_TOO_LARGE` | P0 |
| TC-M02-010 | `POST /reports/{id}/parse` → 200, parse_status="completed" | P0 |
| TC-M02-011 | 解析结果包含 title 字段，非空字符串 | P0 |
| TC-M02-012 | 解析结果包含 rating 字段，值为合法枚举 | P0 |
| TC-M02-013 | 解析结果包含 target_price（number\|null） | P0 |
| TC-M02-014 | 解析结果包含 key_points，非空字符串 | P0 |
| TC-M02-015 | 解析结果包含 stock_code 和 stock_name | P0 |

### 6.2 单元测试

| TC-ID | 覆盖方法 | 断言要点 | 优先级 |
|-------|----------|----------|--------|
| TC-M02-070 | `Storage.__init__` | 目录不存在时自动创建，JSON 文件初始化 | P0 |
| TC-M02-071 | `save_report` | 保存研报元数据，parse_status 为 pending | P0 |
| TC-M02-072 | `save_parsed_report` | 保存解析结果 + 更新 parse_status + 更新知识库 | P0 |

### 6.3 测试注意事项

- LLM 调用 MUST mock，不依赖真实 LLM API
- 准备测试用 PDF 文件（放在 `test_data/` 目录）
- Storage 测试使用临时目录，不影响生产数据

## 7. 验收标准（对齐 `05` US-001, US-002）

- [ ] AC-001-01: 上传 PDF 文件（≤ 50MB）成功，返回 report_id 和文件存储路径
- [ ] AC-001-02: 上传非 PDF 文件被拒绝，返回明确错误信息
- [ ] AC-001-03: 上传超过 50MB 的文件被拒绝，返回明确错误信息
- [ ] AC-002-01: 系统成功从 PDF 中提取文本内容
- [ ] AC-002-02: LLM 解析成功提取标题字段，非空字符串
- [ ] AC-002-03: LLM 解析成功提取评级字段
- [ ] AC-002-04: LLM 解析成功提取目标价字段
- [ ] AC-002-05: LLM 解析成功提取核心观点字段
- [ ] AC-002-06: LLM 解析成功提取股票代码和股票名称
- [ ] AC-002-07: 解析结果保存到内存数据库并持久化

## 8. DoD（Definition of Done）

- [ ] `POST /api/v1/reports/upload` 端点可用，参数校验完整
- [ ] `POST /api/v1/reports/{id}/parse` 端点可用，LLM 解析返回 6 字段
- [ ] Storage 层 save_report / save_parsed_report / update_report_status 方法可用
- [ ] Parser 引擎 PDF 文本提取 + LLM 解析完整链路可用
- [ ] 解析成功后自动入知识库（add_report_to_stock）
- [ ] traceId 注入所有响应
- [ ] 错误码与 `09` 一致
- [ ] 集成测试 TC-M02-001~003, 010~015 全绿
- [ ] 单元测试 TC-M02-070~072 全绿

---

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1 | 2026-04-15 | 首版生成 |
