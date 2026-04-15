# 02 — 后端 Task2：知识库与研报管理

---

| 项 | 值 |
|---|---|
| 模块编号 | M2-IRA |
| 任务编号 | Backend-Task2 |
| 交付阶段 | **S2** |
| 涉及 WBS | W1(reports/kb 路由), W2(Storage 读取+删除), W5(knowledge_base) |
| 覆盖需求 | REQ-M2IRA-003（知识库浏览）、REQ-M2IRA-006（研报管理） |
| 前置依赖 | **Task1 已完成**（Storage 基础层 + 解析数据可用） |
| 关联前端 | ReportManager 列表区 + KnowledgeBase 页面 |

---

## 1. 任务目标

实现知识库管理与研报管理的完整后端链路：按股票维度聚合知识库、自动生成观点汇总、研报列表/筛选/删除（含级联删除）、研报详情与文件下载。

## 2. 涉及文件

| 文件 | 职责 | 新建/修改 |
|------|------|-----------|
| `backend/knowledge_base.py` | 知识库管理 — 按股票聚合、观点汇总生成 | 新建 |
| `backend/blueprints/report_bp.py` | 补充研报列表/详情/删除/下载路由 | 修改（在 Task1 基础上扩展） |
| `backend/blueprints/kb_bp.py` | 知识库 API 路由 | 新建 |
| `backend/storage.py` | 补充 get_reports/delete_report/知识库相关方法 | 修改（在 Task1 基础上扩展） |
| `backend/tests/test_kb.py` | 知识库测试 | 新建 |

## 3. 详细实现步骤

### 3.1 Knowledge Base 管理（knowledge_base.py）

**实现 `KnowledgeBaseManager` 类**，对齐 `08` §2、`10` §5：

```python
class KnowledgeBaseManager:
    def __init__(self, storage, llm_client=None):
        # 引用 Storage 实例
        # 可选 LLM 客户端（用于生成观点汇总）

    def get_stocks(self) -> list:
        # 返回知识库股票列表
        # 每项包含: stock_code, stock_name, industry, report_count, latest_report_date

    def get_stock_detail(self, stock_code: str) -> dict | None:
        # 返回股票详情
        # 含: stock_code, stock_name, industry, report_count, recent_summary, reports[]

    def get_stock_reports(self, stock_code: str, sort_by="upload_time", order="desc") -> list:
        # 返回某只股票的关联研报列表
        # 支持时间排序

    def generate_summary(self, stock_code: str) -> str:
        # 聚合该股票所有研报的核心观点
        # 有 LLM 时：调用 LLM 生成智能汇总
        # 无 LLM 时：简单拼接各研报核心观点（降级方案）
        # 更新 Stock.recent_summary
```

**Stock 数据实体**（对齐 `10` §5）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `stock_code` | string | PK，6 位数字 |
| `stock_name` | string | 股票名称 |
| `industry` | string | 行业分类 |
| `report_ids` | string[] | 关联研报 ID 列表 |
| `recent_summary` | string | 最近观点自动汇总 |
| `updated_at` | string (ISO-8601) | 最后更新时间 |

### 3.2 Storage 层扩展（storage.py）

在 Task1 基础上补充以下方法（对齐 `10` §6）：

```python
# === 研报管理 ===
def get_reports(self, filters=None) -> list:
    # 返回全部研报列表
    # 支持筛选参数: stock_code, industry, date_from, date_to
    # 每条记录合并 Report 元数据 + ParsedReport 解析结果

def delete_report(self, report_id) -> None:
    # 级联删除:
    # 1. 删除 Report 元数据
    # 2. 删除 ParsedReport 解析结果
    # 3. 从 Stock.report_ids 中移除（remove_report_from_stock）
    # 4. 若 Stock 无关联研报，删除该 Stock 条目
    # 5. 删除 PDF 文件
    # 6. 重新生成受影响股票的观点汇总
    # 7. 写回所有 JSON 文件

# === 知识库管理 ===
def get_stocks(self) -> list:
    # 返回知识库中的股票列表

def get_stock_detail(self, stock_code) -> dict | None:
    # 返回股票详情（含关联研报信息 + 观点汇总）

def update_stock_summary(self, stock_code, summary) -> dict:
    # 更新 recent_summary 字段

def remove_report_from_stock(self, stock_code, report_id) -> None:
    # 从知识库移除研报引用
    # 若无关联研报则删除整个 Stock 条目
```

### 3.3 API 路由 — 研报管理（report_bp.py 扩展）

#### `GET /api/v1/reports`（对齐 `09` §5）

查询参数：
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `stock_code` | string | 否 | 按股票代码筛选 |
| `industry` | string | 否 | 按行业筛选 |
| `date_from` | string | 否 | 起始日期 ISO-8601 |
| `date_to` | string | 否 | 截止日期 ISO-8601 |

响应（200）：
```json
{
  "traceId": "tr_...",
  "reports": [
    {
      "report_id": "uuid",
      "filename": "研报.pdf",
      "title": "...",
      "stock_code": "600519",
      "stock_name": "贵州茅台",
      "industry": "白酒",
      "rating": "买入",
      "parse_status": "completed",
      "upload_time": "2026-04-15T10:00:00Z"
    }
  ]
}
```

#### `GET /api/v1/reports/{id}`（对齐 `09` §6）

- 不存在返回 404 `REPORT_NOT_FOUND`
- 返回完整研报详情（元数据 + 解析结果）

#### `DELETE /api/v1/reports/{id}`（对齐 `09` §7）

- 不存在返回 404 `REPORT_NOT_FOUND`
- 级联删除解析结果 + 知识库数据 + PDF 文件
- 返回 200 `{ traceId, message: "删除成功", report_id }`

#### `GET /api/v1/reports/{id}/file`（对齐 `09` §6 补充）

- 返回 PDF 文件流（Content-Type: application/pdf）
- 不存在返回 404 `REPORT_NOT_FOUND`

### 3.4 API 路由 — 知识库（kb_bp.py）

#### `GET /api/v1/kb/stocks`（对齐 `09` §9）

响应（200）：
```json
{
  "traceId": "tr_...",
  "stocks": [
    {
      "stock_code": "600519",
      "stock_name": "贵州茅台",
      "industry": "白酒",
      "report_count": 3,
      "latest_report_date": "2026-04-15T10:00:00Z"
    }
  ]
}
```

#### `GET /api/v1/kb/stocks/{code}`（对齐 `09` §10）

- 不存在返回 404 `STOCK_NOT_FOUND`
- 返回股票详情 + 关联研报列表 + 观点汇总

响应（200）：
```json
{
  "traceId": "tr_...",
  "stock_code": "600519",
  "stock_name": "贵州茅台",
  "industry": "白酒",
  "report_count": 3,
  "recent_summary": "多家券商一致看好...",
  "reports": [
    {
      "report_id": "uuid",
      "title": "...",
      "rating": "买入",
      "target_price": 2100.00,
      "key_points": "...",
      "upload_time": "..."
    }
  ]
}
```

#### `GET /api/v1/kb/stocks/{code}/reports`（对齐 `09` §10 补充）

- 返回该股票的关联研报列表
- 支持时间排序（默认按 upload_time 降序）

### 3.5 Flask 应用扩展（app.py）

- 注册 `kb_bp` Blueprint（url_prefix="/api/v1"）
- 初始化 `KnowledgeBaseManager` 实例

## 4. 前后端交互约定

### 4.1 研报管理流

```
[前端 ReportManager — 列表区]
  │
  ├── 页面加载 → GET /api/v1/reports
  │   ← 返回 { reports: [...] }
  │
  ├── 筛选操作 → GET /api/v1/reports?stock_code=600519&industry=白酒
  │   ← 返回筛选后的 { reports: [...] }
  │
  ├── 点击研报卡片 → 前端展开详情（数据已在列表中）
  │   或 → GET /api/v1/reports/{id} 获取完整详情
  │
  ├── 点击删除 → 前端弹出确认对话框
  │   → 确认后: DELETE /api/v1/reports/{id}
  │   ← 返回 { message: "删除成功" }
  │   → 前端从列表中移除该项
  │
  └── 点击下载 → GET /api/v1/reports/{id}/file
      ← 返回 PDF 文件流 → 浏览器下载
```

### 4.2 知识库浏览流

```
[前端 KnowledgeBase]
  │
  ├── 页面加载 → GET /api/v1/kb/stocks
  │   ← 返回 { stocks: [...] }
  │
  ├── 前端搜索 → 前端过滤（不调用后端）
  │
  ├── 点击某只股票 → GET /api/v1/kb/stocks/{code}
  │   ← 返回 { stock_code, stock_name, recent_summary, reports: [...] }
  │
  └── 行情数据（由 Task3 实现）
      → GET /api/v1/stocks/{code}/market-data
```

### 4.3 前端需处理的错误码

| error.code | HTTP | 前端展示 |
|-----------|------|----------|
| `REPORT_NOT_FOUND` | 404 | "研报不存在或已被删除" |
| `STOCK_NOT_FOUND` | 404 | "未找到该股票的知识库数据" |

### 4.4 研报卡片展示字段（前端对齐 `06` §3.3）

| 字段 | 展示方式 | 数据来源 |
|------|----------|----------|
| title | 卡片标题，加粗 | `GET /reports` → reports[].title |
| stock_code + stock_name | 蓝色标签 | reports[].stock_code + stock_name |
| industry | 灰色标签 | reports[].industry |
| rating | 彩色标签（买入=绿, 增持=浅绿, 中性=灰, 减持=橙, 卖出=红） | reports[].rating |
| upload_time | 相对时间 + tooltip 完整时间 | reports[].upload_time |
| parse_status | 状态标签 | reports[].parse_status |

## 5. 关键业务逻辑

### 5.1 级联删除（对齐 `10` §7）

删除研报时必须执行完整级联：

```
delete_report(report_id)
  ├── 获取 ParsedReport → 得到 stock_code
  ├── 删除 Report 元数据
  ├── 删除 ParsedReport 解析结果
  ├── remove_report_from_stock(stock_code, report_id)
  │   ├── 从 Stock.report_ids 中移除
  │   ├── 若 report_ids 为空 → 删除整个 Stock 条目
  │   └── 否则 → 重新生成 recent_summary
  ├── 删除 PDF 文件
  └── 写回所有 JSON 文件
```

### 5.2 观点汇总生成

新增或删除研报后，自动重新生成对应股票的 `recent_summary`：
- 收集该股票所有研报的 key_points
- 有 LLM：调用 LLM 生成智能汇总
- 无 LLM：按时间倒序拼接各研报的核心观点

## 6. 测试用例

### 6.1 集成测试（对齐 `13` §3.3 + §3.6）

| TC-ID | 断言要点 | 优先级 |
|-------|----------|--------|
| TC-M02-020 | `GET /kb/stocks` → 200, 返回 stocks 数组 | P0 |
| TC-M02-021 | `GET /kb/stocks/{code}` → 200, 含 stock_code, recent_summary, reports | P0 |
| TC-M02-022 | 知识库按 stock_code 正确聚合多份研报 | P0 |
| TC-M02-023 | recent_summary 非空，包含多份研报的观点汇总 | P0 |
| TC-M02-024 | 不存在的 stock_code → 404, `STOCK_NOT_FOUND` | P0 |
| TC-M02-025 | `GET /kb/stocks/{code}/reports` 支持时间排序 | P1 |
| TC-M02-050 | `GET /reports` → 200, 返回 reports 数组 | P0 |
| TC-M02-051 | `GET /reports/{id}` → 200, 含完整研报详情 | P0 |
| TC-M02-052 | `GET /reports?stock_code=xxx` 筛选正确 | P0 |
| TC-M02-053 | `DELETE /reports/{id}` → 200, 级联删除解析结果 + 知识库数据 | P0 |
| TC-M02-054 | 删除不存在的研报 → 404, `REPORT_NOT_FOUND` | P0 |
| TC-M02-055 | `GET /reports/{id}/file` → 200, 返回 PDF 文件 | P1 |

### 6.2 单元测试

| TC-ID | 覆盖方法 | 断言要点 | 优先级 |
|-------|----------|----------|--------|
| TC-M02-073 | `get_reports` | 返回全部研报 + 筛选条件生效 | P0 |
| TC-M02-074 | `delete_report` | 级联删除：解析结果 + 知识库引用 + PDF 文件 | P0 |
| TC-M02-075 | `get_stocks` | 返回按股票聚合的列表 | P0 |
| TC-M02-076 | `get_stock_detail` | 返回股票详情含关联研报和观点汇总 | P0 |

## 7. 验收标准（对齐 `05` US-003, US-006）

- [ ] AC-003-01: 知识库页面以股票为维度展示列表，每个股票显示关联研报数量
- [ ] AC-003-02: 点击某只股票后展示所有关联研报的解析结果
- [ ] AC-003-03: 展示该股票的最近观点汇总
- [ ] AC-003-04: 支持按时间筛选和排序研报
- [ ] AC-006-01: 展示已上传研报列表，包含标题、股票代码、行业、上传时间
- [ ] AC-006-02: 支持按股票代码、行业、时间筛选研报
- [ ] AC-006-03: 删除研报时级联删除关联的解析结果和知识库数据
- [ ] AC-006-04: 删除前弹出确认对话框（前端实现）

## 8. DoD（Definition of Done）

- [ ] `GET /api/v1/reports` 端点可用，支持 4 种筛选参数
- [ ] `GET /api/v1/reports/{id}` 端点可用，返回完整详情
- [ ] `DELETE /api/v1/reports/{id}` 端点可用，级联删除完整
- [ ] `GET /api/v1/reports/{id}/file` 端点可用，返回 PDF 文件
- [ ] `GET /api/v1/kb/stocks` 端点可用，返回股票聚合列表
- [ ] `GET /api/v1/kb/stocks/{code}` 端点可用，含 recent_summary
- [ ] `GET /api/v1/kb/stocks/{code}/reports` 端点可用，支持排序
- [ ] KnowledgeBaseManager 观点汇总生成可用
- [ ] 级联删除逻辑完整（解析结果 + 知识库 + PDF）
- [ ] 集成测试 TC-M02-020~025, 050~055 全绿
- [ ] 单元测试 TC-M02-073~076 全绿

---

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1 | 2026-04-15 | 首版生成 |
