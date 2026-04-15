# 03 — 后端 Task3：研报比对与行情数据

---

| 项 | 值 |
|---|---|
| 模块编号 | M2-IRA |
| 任务编号 | Backend-Task3 |
| 交付阶段 | **S3**（研报比对）+ **S4**（行情数据） |
| 涉及 WBS | W1(compare/market-data 路由), W4(Comparator 引擎), W6(StockData) |
| 覆盖需求 | REQ-M2IRA-004（研报比对）、REQ-M2IRA-007（行情数据） |
| 前置依赖 | **Task1 已完成**（Parser + Storage 基础）、**Task2 已完成**（知识库聚合数据可用） |
| 关联前端 | ReportCompare 页面 + KnowledgeBase 行情区 |

---

## 1. 任务目标

实现研报智能比对引擎（相似合并 + 差异高亮）和 AKShare 行情数据集成（PE/PB/市值 + 降级处理）。

## 2. 涉及文件

| 文件 | 职责 | 新建/修改 |
|------|------|-----------|
| `backend/comparator.py` | 研报比对引擎 — 逐字段对比 + LLM 语义比对 | 新建 |
| `backend/stock_data.py` | AKShare 行情数据接口 + 缓存 + 降级 | 新建 |
| `backend/blueprints/compare_bp.py` | 研报比对 API 路由 | 新建 |
| `backend/blueprints/report_bp.py` | 补充 market-data 路由（或独立路由） | 修改 |
| `backend/app.py` | 注册 compare_bp，初始化 Comparator + StockData | 修改 |
| `backend/tests/test_comparator.py` | 比对引擎测试 | 新建 |

## 3. 详细实现步骤

### 3.1 研报比对引擎（comparator.py）

**实现 `ReportComparator` 类**，对齐 `08` §4.2：

```python
class ReportComparator:
    def __init__(self, storage, llm_client=None):
        # 引用 Storage 实例
        # 可选 LLM 客户端（用于语义比对）

    def validate(self, report_ids: list) -> tuple[bool, str]:
        # 校验:
        # 1. report_ids 数量 ≥ 2 → 否则返回 COMPARE_MIN_REPORTS
        # 2. 所有 report_id 存在 → 否则返回 REPORT_NOT_FOUND
        # 3. 所有研报属于同一 stock_code → 否则返回 COMPARE_DIFF_STOCK

    def compare(self, report_ids: list) -> dict:
        # 完整比对流程:
        # 1. 从 Storage 获取各研报解析结果
        # 2. 生成 reports_summary（各研报核心字段摘要）
        # 3. 逐字段对比: rating, target_price, key_points
        # 4. 核心观点语义比对（LLM 调用）
        # 5. 生成 similarities[]（相似观点合并）
        # 6. 生成 differences[]（差异高亮）
        # 7. 返回比对结果

    def _compare_fields(self, parsed_reports: list) -> list:
        # 逐字段对比: rating, target_price
        # 生成 differences 列表

    def _compare_key_points(self, parsed_reports: list) -> tuple[list, list]:
        # 核心观点语义比对
        # 有 LLM: 调用 LLM 分析相似/差异
        # 无 LLM: 基于简单文本比对（降级方案）
        # 返回 (similarities, key_point_differences)

    def _build_reports_summary(self, parsed_reports: list) -> list:
        # 构建各研报核心字段摘要
        # 每项: report_id, title, rating, target_price, key_points
```

**比对结果数据结构**（对齐 `09` §8）：

```json
{
  "stock_code": "600519",
  "stock_name": "贵州茅台",
  "reports_summary": [
    {
      "report_id": "uuid-1",
      "title": "券商A研报标题",
      "rating": "买入",
      "target_price": 2100.00,
      "key_points": "..."
    },
    {
      "report_id": "uuid-2",
      "title": "券商B研报标题",
      "rating": "增持",
      "target_price": 1980.00,
      "key_points": "..."
    }
  ],
  "similarities": [
    {
      "topic": "业绩增长预期",
      "merged_view": "两家券商均认为2026年营收增速将达15%以上...",
      "source_reports": ["uuid-1", "uuid-2"]
    }
  ],
  "differences": [
    {
      "field": "rating",
      "values": {"uuid-1": "买入", "uuid-2": "增持"},
      "highlight": "评级存在分歧：券商A给出买入，券商B给出增持"
    },
    {
      "field": "target_price",
      "values": {"uuid-1": 2100.00, "uuid-2": 1980.00},
      "highlight": "目标价差异：2100.00 vs 1980.00，差距5.7%"
    }
  ],
  "compare_time_ms": 8000
}
```

### 3.2 行情数据接口（stock_data.py）

**实现 `StockDataService` 类**，对齐 `08` §2、`09` §11：

```python
class StockDataService:
    def __init__(self, cache_ttl=300):
        # cache_ttl: 缓存有效期（秒），默认 5 分钟
        # 内存缓存: { stock_code: { data, timestamp } }

    def get_market_data(self, stock_code: str) -> dict:
        # 获取行情数据流程:
        # 1. 检查缓存 → 未过期则返回缓存数据 (source="cache")
        # 2. 调用 AKShare API 获取最新数据
        # 3. 成功: 更新缓存，返回数据 (source="akshare")
        # 4. 失败: 返回降级响应 (source="unavailable")

    def _fetch_from_akshare(self, stock_code: str) -> dict | None:
        # AKShare API 调用
        # 获取: pe, pb, market_cap, latest_price, data_time
        # 异常时返回 None

    def _get_cached(self, stock_code: str) -> dict | None:
        # 检查缓存是否存在且未过期

    def _update_cache(self, stock_code: str, data: dict) -> None:
        # 更新缓存
```

**行情数据响应**（对齐 `09` §11）：

```json
{
  "traceId": "tr_...",
  "stock_code": "600519",
  "stock_name": "贵州茅台",
  "pe": 35.2,
  "pb": 12.8,
  "market_cap": 26000.0,
  "latest_price": 1850.00,
  "data_time": "2026-04-15T15:00:00Z",
  "source": "akshare"
}
```

**降级响应**（AKShare 不可用时）：

```json
{
  "traceId": "tr_...",
  "stock_code": "600519",
  "stock_name": "贵州茅台",
  "pe": null,
  "pb": null,
  "market_cap": null,
  "latest_price": null,
  "data_time": null,
  "source": "unavailable"
}
```

### 3.3 API 路由 — 研报比对（compare_bp.py）

#### `POST /api/v1/reports/compare`（对齐 `09` §8）

请求体：
```json
{
  "report_ids": ["uuid-1", "uuid-2"]
}
```

处理流程：
1. 校验 report_ids 数量 ≥ 2 → 否则 400 `COMPARE_MIN_REPORTS`
2. 校验所有 report_id 存在 → 否则 404 `REPORT_NOT_FOUND`
3. 校验同一 stock_code → 否则 400 `COMPARE_DIFF_STOCK`
4. 调用 `comparator.compare(report_ids)` 执行比对
5. 返回 200 + 比对结果
6. LLM 异常时返回 500 `LLM_ERROR`

### 3.4 API 路由 — 行情数据

#### `GET /api/v1/stocks/{code}/market-data`（对齐 `09` §11）

处理流程：
1. 从知识库获取 stock_name（用于响应填充）
2. 调用 `stock_data_service.get_market_data(code)` 获取行情
3. 返回 200（无论 AKShare 是否可用，只改变 source 字段）

**注意**：此端点不返回 404，即使股票不在知识库中也尝试获取行情数据。stock_name 不可用时可返回空字符串。

### 3.5 Flask 应用扩展（app.py）

- 注册 `compare_bp` Blueprint
- 初始化 `ReportComparator` 实例
- 初始化 `StockDataService` 实例

## 4. 前后端交互约定

### 4.1 研报比对流

```
[前端 ReportCompare]
  │
  ├── 进入比对页 → GET /api/v1/kb/stocks（复用 Task2 的知识库接口）
  │   ← 返回股票列表（用于下拉选择）
  │
  ├── 选择股票后 → 前端加载该股票下的研报列表（从 stocks 响应中获取）
  │   或 → GET /api/v1/kb/stocks/{code} 获取关联研报
  │
  ├── 用户勾选 ≥ 2 份研报 → 前端启用"开始比对"按钮
  │
  ├── 点击"开始比对" → POST /api/v1/reports/compare
  │   请求: { "report_ids": ["uuid-1", "uuid-2", ...] }
  │   ← 返回 {
  │       reports_summary: [...],
  │       similarities: [...],
  │       differences: [...]
  │   }
  │
  └── 前端渲染比对结果
      ├── 基本信息对照表（reports_summary → 表格）
      ├── 相似观点合并区（similarities → 合并视图）
      └── 差异高亮区（differences → 高亮标注）
```

### 4.2 行情数据流

```
[前端 KnowledgeBase — 股票详情页]
  │
  ├── 进入股票详情后 → GET /api/v1/stocks/{code}/market-data
  │
  ├── source="akshare" 或 "cache"
  │   → 展示 PE、PB、市值、最新价、数据时间
  │
  └── source="unavailable"
      → 展示"暂无数据"（不影响页面其他区域）
```

### 4.3 前端需处理的错误码

| error.code | HTTP | 前端展示 | 触发场景 |
|-----------|------|----------|----------|
| `COMPARE_MIN_REPORTS` | 400 | "至少选择 2 份研报进行比对" | 勾选研报数 < 2 |
| `COMPARE_DIFF_STOCK` | 400 | "比对研报必须属于同一公司" | 选择了不同公司的研报 |
| `LLM_ERROR` | 500 | "AI 服务暂时不可用，请稍后重试" | LLM 比对失败 |
| `REPORT_NOT_FOUND` | 404 | "部分研报不存在" | 比对时某研报已被删除 |

### 4.4 比对结果展示映射（对齐 `06` §6.2）

| 后端字段 | 前端展示 |
|----------|----------|
| `reports_summary` | 基本信息对照表（表格，每列一份研报，行：标题、评级、目标价） |
| `similarities` | 相似观点合并区（统一描述 + 来源研报标注） |
| `differences` 中 `field="rating"` | 不同评级用不同颜色标签 |
| `differences` 中 `field="target_price"` | 数值差异高亮 + 差距百分比 |
| `differences` 中 `field="key_points"` | 差异内容黄色/红色高亮标注 |

### 4.5 行情数据展示映射（对齐 `06` §5.3）

| 后端字段 | 前端展示 | 降级 |
|----------|----------|------|
| `pe` | PE（市盈率） | null → "暂无数据" |
| `pb` | PB（市净率） | null → "暂无数据" |
| `market_cap` | 总市值（亿元） | null → "暂无数据" |
| `latest_price` | 最新收盘价 | null → "暂无数据" |
| `data_time` | 数据更新时间 | null → 不显示 |
| `source` | 数据来源标注（前端可选展示） | "unavailable" → 提示 |

## 5. AKShare 集成细节

### 5.1 推荐使用的 AKShare 接口

```python
import akshare as ak

# 获取个股基本面数据
# 具体接口根据 AKShare 文档选择，示例:
# ak.stock_individual_info_em(symbol="600519")  # 个股信息
# ak.stock_a_indicator_lg(symbol="600519")      # 基本面指标
```

### 5.2 降级链（对齐 `07` §1.2）

```
AKShare 降级链:
  ├─[1] AKShare API 正常 → source="akshare"
  ├─[2] API 异常但缓存有效 → source="cache" + 标注缓存时间
  └─[3] API 异常且无缓存 → source="unavailable", 所有数值为 null
```

### 5.3 缓存策略

| 项 | 规格 |
|----|------|
| 缓存位置 | 内存 dict（不持久化） |
| TTL | 300 秒（5 分钟） |
| 缓存键 | stock_code |
| 过期行为 | 重新调用 AKShare API |

## 6. LLM 比对 Prompt 设计要点

- 输入：多份研报的核心观点文本
- 任务：识别相似观点并合并描述，标注差异点
- 输出格式：严格 JSON（similarities + differences）
- 安全：系统 Prompt 与研报内容隔离（对齐 `11` §5）
- 降级：LLM 不可用时基于简单文本规则进行对比

## 7. 测试用例

### 7.1 集成测试（对齐 `13` §3.4 + §3.7）

| TC-ID | 断言要点 | 优先级 |
|-------|----------|--------|
| TC-M02-030 | `POST /reports/compare` 2 份同公司研报 → 200 | P0 |
| TC-M02-031 | 响应包含 similarities 数组（相似合并） | P0 |
| TC-M02-032 | 响应包含 differences 数组（差异高亮） | P0 |
| TC-M02-033 | reports_summary 包含每份研报的核心字段 | P0 |
| TC-M02-034 | report_ids < 2 → 400, `COMPARE_MIN_REPORTS` | P0 |
| TC-M02-035 | 不同公司研报 → 400, `COMPARE_DIFF_STOCK` | P0 |
| TC-M02-060 | `GET /stocks/{code}/market-data` → 200, 含 pe, pb, market_cap | P1 |
| TC-M02-061 | source 字段为 "akshare" 或 "cache" | P1 |
| TC-M02-062 | AKShare 不可用时 source="unavailable", 数值为 null | P1 |
| TC-M02-063 | 不存在的 stock_code 降级处理 | P1 |

### 7.2 单元测试

| TC-ID | 覆盖 | 断言要点 | 优先级 |
|-------|------|----------|--------|
| TC-COMP-001 | `ReportComparator.validate` | report_ids < 2 返回错误 | P0 |
| TC-COMP-002 | `ReportComparator.validate` | 不同 stock_code 返回错误 | P0 |
| TC-COMP-003 | `ReportComparator._compare_fields` | 正确检测 rating/target_price 差异 | P0 |
| TC-COMP-004 | `ReportComparator._build_reports_summary` | 正确构建摘要 | P0 |
| TC-STOCK-001 | `StockDataService.get_market_data` | 缓存命中返回 cache | P1 |
| TC-STOCK-002 | `StockDataService.get_market_data` | AKShare 异常返回 unavailable | P1 |

### 7.3 测试注意事项

- LLM 调用 MUST mock
- AKShare API 调用 MUST mock
- 准备至少 2 份同一公司的测试研报解析数据
- 比对测试需预置知识库中的解析结果（依赖 Task1 + Task2 的 Storage）

## 8. 验收标准（对齐 `05` US-004, US-007）

- [ ] AC-004-01: 成功选择 ≥ 2 份同一公司的研报发起比对
- [ ] AC-004-02: 比对结果展示相似信息合并视图
- [ ] AC-004-03: 比对结果中差异内容以高亮方式标注
- [ ] AC-004-04: 比对结果包含每份研报的核心字段
- [ ] AC-007-01: 知识库股票详情页展示 PE、PB、市值等基本面指标
- [ ] AC-007-02: 数据来自 AKShare API，数据有明确时间戳
- [ ] AC-007-03: AKShare API 不可用时降级显示"暂无数据"，不影响页面其他功能

## 9. DoD（Definition of Done）

- [ ] `POST /api/v1/reports/compare` 端点可用，校验完整（数量 + 同一公司）
- [ ] 比对结果包含 reports_summary + similarities + differences
- [ ] `GET /api/v1/stocks/{code}/market-data` 端点可用
- [ ] AKShare 三级降级链可用（akshare → cache → unavailable）
- [ ] 比对引擎 LLM 降级方案可用（无 LLM 时简单文本比对）
- [ ] 集成测试 TC-M02-030~035, 060~063 全绿
- [ ] 单元测试全绿

---

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1 | 2026-04-15 | 首版生成 |
