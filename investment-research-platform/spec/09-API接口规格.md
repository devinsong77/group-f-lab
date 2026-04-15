# 09 — API 接口规格

---

| 项 | 值 |
|---|---|
| 模块编号 | M2-IRA |
| 模块名称 | 投研分析平台（AI 研报助手） |
| 文档版本 | v0.1 |
| 阶段 | Design（How — 契约真源） |
| Base URL | `/api/v1` |

---

> **本文是全部 API 端点的契约真源**。`05` 定义"用户要什么"，**09（本文）定义"后端必须返回什么"**，`13` 的测试断言以本文为准。

## 1. 端点总览

| # | 端点 | 方法 | 功能 | 成功码 |
|---|------|------|------|--------|
| 1 | `/api/v1/reports/upload` | POST | 上传研报 | 201 |
| 2 | `/api/v1/reports` | GET | 研报列表 | 200 |
| 3 | `/api/v1/reports/{id}` | GET | 研报详情 | 200 |
| 4 | `/api/v1/reports/{id}` | DELETE | 删除研报 | 200 |
| 5 | `/api/v1/reports/{id}/parse` | POST | 触发解析 | 200 |
| 6 | `/api/v1/reports/{id}/file` | GET | 下载原文 | 200 |
| 7 | `/api/v1/reports/compare` | POST | 研报比对 | 200 |
| 8 | `/api/v1/kb/stocks` | GET | 知识库股票列表 | 200 |
| 9 | `/api/v1/kb/stocks/{code}` | GET | 股票知识库详情 | 200 |
| 10 | `/api/v1/kb/stocks/{code}/reports` | GET | 股票关联研报 | 200 |
| 11 | `/api/v1/stocks/{code}/market-data` | GET | 行情数据 | 200 |

## 2. 统一响应规范

### 成功响应

```json
{ "traceId": "tr_abc123...", /* 业务字段 */ }
```

### 错误响应

```json
{ "error": { "code": "INVALID_FILE_TYPE", "message": "仅支持 PDF 格式文件", "details": {}, "traceId": "tr_..." } }
```

### 错误码清单

| HTTP | error.code | 触发条件 | details |
|------|-----------|----------|---------|
| 400 | `INVALID_FILE_TYPE` | 上传非 PDF 文件 | `{"allowed": ["application/pdf"]}` |
| 400 | `FILE_TOO_LARGE` | 文件超过 50MB | `{"max_size_mb": 50}` |
| 400 | `COMPARE_MIN_REPORTS` | 比对研报数 < 2 | `{"min_count": 2}` |
| 400 | `COMPARE_DIFF_STOCK` | 比对研报不属于同一公司 | `{}` |
| 404 | `REPORT_NOT_FOUND` | 研报不存在 | `{}` |
| 404 | `STOCK_NOT_FOUND` | 股票知识库不存在 | `{}` |
| 500 | `PARSE_FAILED` | PDF 提取或 LLM 解析失败 | `{"reason": "..."}` |
| 500 | `LLM_ERROR` | LLM API 调用异常 | `{"reason": "..."}` |
| 500 | `AKSHARE_ERROR` | AKShare API 异常 | `{"reason": "..."}` |

## 3. POST /reports/upload — 上传研报

**请求体**：`multipart/form-data`

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| `file` | File | **是** | PDF, ≤ 50MB | 研报 PDF 文件 |

**成功响应**（201）：

| 字段 | 类型 | 必有 | 说明 |
|------|------|------|------|
| `traceId` | string | 是 | 链路追踪 ID |
| `report_id` | string | 是 | 研报唯一 ID（UUID） |
| `filename` | string | 是 | 原始文件名 |
| `file_path` | string | 是 | 服务端存储路径 |
| `upload_time` | string | 是 | 上传时间 ISO-8601 |
| `parse_status` | string | 是 | "pending" |

## 4. POST /reports/{id}/parse — 触发解析

**路径参数**：`id` — 研报 ID

**成功响应**（200）：

| 字段 | 类型 | 必有 | 说明 |
|------|------|------|------|
| `traceId` | string | 是 | 链路追踪 ID |
| `report_id` | string | 是 | 研报 ID |
| `parse_status` | string | 是 | "completed" 或 "failed" |
| `title` | string | 是 | 研报标题 |
| `rating` | string | 是 | 评级（买入/增持/中性/减持/卖出/未提及） |
| `target_price` | number\|null | 是 | 目标价（元），未提及为 null |
| `key_points` | string | 是 | 核心观点摘要 |
| `stock_code` | string | 是 | 股票代码 |
| `stock_name` | string | 是 | 股票名称 |
| `industry` | string | 是 | 行业分类 |
| `parse_time_ms` | integer | 是 | 解析耗时（毫秒） |

## 5. GET /reports — 研报列表

**查询参数**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `stock_code` | string | 否 | 按股票代码筛选 |
| `industry` | string | 否 | 按行业筛选 |
| `date_from` | string | 否 | 起始日期 ISO-8601 |
| `date_to` | string | 否 | 截止日期 ISO-8601 |

**成功响应**（200）：

| 字段 | 类型 | 必有 | 说明 |
|------|------|------|------|
| `traceId` | string | 是 | 链路追踪 ID |
| `reports` | array | 是 | 研报数组 |
| `reports[].report_id` | string | 是 | 研报 ID |
| `reports[].filename` | string | 是 | 原始文件名 |
| `reports[].title` | string\|null | 是 | 解析后的标题（未解析为 null） |
| `reports[].stock_code` | string\|null | 是 | 股票代码 |
| `reports[].stock_name` | string\|null | 是 | 股票名称 |
| `reports[].industry` | string\|null | 是 | 行业 |
| `reports[].rating` | string\|null | 是 | 评级 |
| `reports[].parse_status` | string | 是 | pending/parsing/completed/failed |
| `reports[].upload_time` | string | 是 | 上传时间 |

## 6. GET /reports/{id} — 研报详情

**成功响应**（200）：

| 字段 | 类型 | 必有 | 说明 |
|------|------|------|------|
| `traceId` | string | 是 | 链路追踪 ID |
| `report_id` | string | 是 | 研报 ID |
| `filename` | string | 是 | 原始文件名 |
| `title` | string\|null | 是 | 研报标题 |
| `rating` | string\|null | 是 | 评级 |
| `target_price` | number\|null | 是 | 目标价 |
| `key_points` | string\|null | 是 | 核心观点 |
| `stock_code` | string\|null | 是 | 股票代码 |
| `stock_name` | string\|null | 是 | 股票名称 |
| `industry` | string\|null | 是 | 行业 |
| `parse_status` | string | 是 | 解析状态 |
| `upload_time` | string | 是 | 上传时间 |
| `parse_time_ms` | integer\|null | 是 | 解析耗时 |

## 7. DELETE /reports/{id} — 删除研报

**成功响应**（200）：

| 字段 | 类型 | 必有 | 说明 |
|------|------|------|------|
| `traceId` | string | 是 | 链路追踪 ID |
| `message` | string | 是 | "删除成功" |
| `report_id` | string | 是 | 已删除的研报 ID |

**副作用**：级联删除关联的解析结果、知识库数据和 PDF 文件。

## 8. POST /reports/compare — 研报比对

**请求体**：

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| `report_ids` | string[] | **是** | ≥ 2 个，同一 stock_code | 待比对的研报 ID 列表 |

**成功响应**（200）：

| 字段 | 类型 | 必有 | 说明 |
|------|------|------|------|
| `traceId` | string | 是 | 链路追踪 ID |
| `stock_code` | string | 是 | 股票代码 |
| `stock_name` | string | 是 | 股票名称 |
| `reports_summary` | array | 是 | 各研报核心字段摘要 |
| `reports_summary[].report_id` | string | 是 | 研报 ID |
| `reports_summary[].title` | string | 是 | 标题 |
| `reports_summary[].rating` | string | 是 | 评级 |
| `reports_summary[].target_price` | number\|null | 是 | 目标价 |
| `reports_summary[].key_points` | string | 是 | 核心观点 |
| `similarities` | array | 是 | 相似观点合并列表 |
| `similarities[].topic` | string | 是 | 相似主题 |
| `similarities[].merged_view` | string | 是 | 合并后的描述 |
| `similarities[].source_reports` | string[] | 是 | 来源研报 ID |
| `differences` | array | 是 | 差异列表 |
| `differences[].field` | string | 是 | 差异字段（rating/target_price/key_points） |
| `differences[].values` | object | 是 | 各研报的不同值 `{report_id: value}` |
| `differences[].highlight` | string | 是 | 差异说明 |
| `compare_time_ms` | integer | 是 | 比对耗时（毫秒） |

## 9. GET /kb/stocks — 知识库股票列表

**成功响应**（200）：

| 字段 | 类型 | 必有 | 说明 |
|------|------|------|------|
| `traceId` | string | 是 | 链路追踪 ID |
| `stocks` | array | 是 | 股票列表 |
| `stocks[].stock_code` | string | 是 | 股票代码 |
| `stocks[].stock_name` | string | 是 | 股票名称 |
| `stocks[].industry` | string | 是 | 行业 |
| `stocks[].report_count` | integer | 是 | 关联研报数量 |
| `stocks[].latest_report_date` | string | 是 | 最新研报日期 |

## 10. GET /kb/stocks/{code} — 股票知识库详情

**成功响应**（200）：

| 字段 | 类型 | 必有 | 说明 |
|------|------|------|------|
| `traceId` | string | 是 | 链路追踪 ID |
| `stock_code` | string | 是 | 股票代码 |
| `stock_name` | string | 是 | 股票名称 |
| `industry` | string | 是 | 行业 |
| `report_count` | integer | 是 | 关联研报数量 |
| `recent_summary` | string | 是 | 最近观点自动汇总 |
| `reports` | array | 是 | 关联研报列表（含解析结果） |

## 11. GET /stocks/{code}/market-data — 行情数据

**成功响应**（200）：

| 字段 | 类型 | 必有 | 说明 |
|------|------|------|------|
| `traceId` | string | 是 | 链路追踪 ID |
| `stock_code` | string | 是 | 股票代码 |
| `stock_name` | string | 是 | 股票名称 |
| `pe` | number\|null | 是 | 市盈率 |
| `pb` | number\|null | 是 | 市净率 |
| `market_cap` | number\|null | 是 | 总市值（亿元） |
| `latest_price` | number\|null | 是 | 最新收盘价 |
| `data_time` | string\|null | 是 | 数据更新时间 |
| `source` | string | 是 | "akshare" 或 "cache" 或 "unavailable" |

## 12. 参数校验规则汇总

| 端点 | 字段 | 规则 | 失败 HTTP | error.code |
|------|------|------|-----------|-----------|
| POST /reports/upload | `file` | 类型为 PDF | 400 | `INVALID_FILE_TYPE` |
| POST /reports/upload | `file` | ≤ 50MB | 400 | `FILE_TOO_LARGE` |
| POST /reports/compare | `report_ids` | ≥ 2 个 | 400 | `COMPARE_MIN_REPORTS` |
| POST /reports/compare | `report_ids` | 同一 stock_code | 400 | `COMPARE_DIFF_STOCK` |
| GET /reports/{id} | `id` | 存在 | 404 | `REPORT_NOT_FOUND` |
| GET /kb/stocks/{code} | `code` | 存在 | 404 | `STOCK_NOT_FOUND` |

---

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1 | 2026-04-15 | 首版填写 |
