# 04 — 前端 Task：全部页面与交互

---

| 项 | 值 |
|---|---|
| 模块编号 | M2-IRA |
| 任务编号 | Frontend-Task |
| 交付阶段 | **S1~S4**（贯穿所有阶段，按阶段逐步交付） |
| 涉及 WBS | W7（前端视图） |
| 覆盖需求 | REQ-M2IRA-001~004, 006, 007（全部） |
| 技术栈 | React >= 18 + Vite >= 5 + 原生 CSS + fetch API |

---

## 1. 任务目标

实现投研分析平台的完整前端 SPA 应用，包含 3 个主页面（研报管理、知识库、研报比对）、API 客户端封装、统一错误处理和状态管理。

## 2. 涉及文件

| 文件 | 职责 | 新建/修改 |
|------|------|-----------|
| `frontend/src/App.jsx` | 主组件 + Tab 导航 | 新建 |
| `frontend/src/App.css` | 全局样式 | 新建 |
| `frontend/src/api.js` | API 客户端封装 | 新建 |
| `frontend/src/pages/ReportManager.jsx` | 研报管理页（上传 + 列表 + 筛选 + 删除） | 新建 |
| `frontend/src/pages/KnowledgeBase.jsx` | 知识库页（股票列表 + 详情 + 行情数据） | 新建 |
| `frontend/src/pages/ReportCompare.jsx` | 研报比对页（选择 + 比对结果） | 新建 |
| `frontend/src/components/` | 通用组件 | 新建 |
| `frontend/package.json` | 项目配置 | 新建 |
| `frontend/vite.config.js` | Vite 配置（API 代理） | 新建 |

## 3. 分阶段交付计划

### S1 阶段（配合后端 Task1）
- ReportManager 上传区域
- 解析结果展示
- API 客户端基础 + 错误处理

### S2 阶段（配合后端 Task2）
- ReportManager 列表区（研报卡片 + 筛选 + 删除 + 下载）
- KnowledgeBase 页面（股票列表 + 详情 + 观点汇总）
- Tab 导航完整

### S3 阶段（配合后端 Task3 前半）
- ReportCompare 页面（选择研报 + 比对结果展示）

### S4 阶段（配合后端 Task3 后半）
- KnowledgeBase 行情数据区域（PE/PB/市值 + 降级处理）

## 4. 详细实现

### 4.1 项目初始化

```bash
# Vite + React 项目
npm create vite@latest frontend -- --template react
cd frontend && npm install
```

**vite.config.js — API 代理配置**：
```javascript
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true
      }
    }
  }
})
```

### 4.2 API 客户端（api.js）

封装统一的 API 调用层，处理请求/响应/错误：

```javascript
const API_BASE = '/api/v1';

// === 研报管理 API（对接后端 Task1 + Task2）===
export async function uploadReport(file)
  // POST /reports/upload (multipart/form-data)
  // 返回 { report_id, filename, parse_status, ... }

export async function parseReport(reportId)
  // POST /reports/{id}/parse
  // 返回解析结果 { title, rating, target_price, ... }

export async function getReports(filters = {})
  // GET /reports?stock_code=&industry=&date_from=&date_to=
  // 返回 { reports: [...] }

export async function getReport(reportId)
  // GET /reports/{id}
  // 返回完整研报详情

export async function deleteReport(reportId)
  // DELETE /reports/{id}
  // 返回 { message: "删除成功" }

export async function downloadReportFile(reportId)
  // GET /reports/{id}/file
  // 返回 PDF Blob

// === 知识库 API（对接后端 Task2）===
export async function getStocks()
  // GET /kb/stocks
  // 返回 { stocks: [...] }

export async function getStockDetail(stockCode)
  // GET /kb/stocks/{code}
  // 返回 { stock_code, stock_name, recent_summary, reports: [...] }

export async function getStockReports(stockCode)
  // GET /kb/stocks/{code}/reports
  // 返回关联研报列表

// === 比对 API（对接后端 Task3）===
export async function compareReports(reportIds)
  // POST /reports/compare
  // 请求: { report_ids: [...] }
  // 返回 { reports_summary, similarities, differences }

// === 行情数据 API（对接后端 Task3）===
export async function getMarketData(stockCode)
  // GET /stocks/{code}/market-data
  // 返回 { pe, pb, market_cap, latest_price, source }
```

**统一错误处理**：
```javascript
// 所有 API 调用统一处理错误响应
// 解析 error.code → 映射到中文提示
// 错误码映射表:
const ERROR_MESSAGES = {
  INVALID_FILE_TYPE: '仅支持 PDF 格式文件',
  FILE_TOO_LARGE: '文件大小不能超过 50MB',
  PARSE_FAILED: '研报解析失败，请检查文件格式',
  LLM_ERROR: 'AI 服务暂时不可用，请稍后重试',
  REPORT_NOT_FOUND: '研报不存在或已被删除',
  STOCK_NOT_FOUND: '未找到该股票的知识库数据',
  COMPARE_MIN_REPORTS: '至少选择 2 份研报进行比对',
  COMPARE_DIFF_STOCK: '比对研报必须属于同一公司',
};
```

### 4.3 主组件 — App.jsx（对齐 `06` §1~§2）

```
┌─────────────────────────────────────────────────────────┐
│  header: 投研分析平台 + [导航标签页]                       │
│  [研报管理] [知识库] [研报比对]                              │
├─────────────────────────────────────────────────────────┤
│  main-content（根据 activeTab 切换页面组件）               │
└─────────────────────────────────────────────────────────┘
```

**状态**：
| State 变量 | 类型 | 初始值 | 说明 |
|------------|------|--------|------|
| `activeTab` | string | `'reports'` | 当前导航标签：reports / kb / compare |

### 4.4 研报管理页 — ReportManager.jsx（对齐 `06` §3~§4）

#### 4.4.1 上传区域（S1 阶段交付）

| 功能 | 触发 | API 调用 | 行为 |
|------|------|----------|------|
| 文件选择 | 点击"上传研报"按钮 | — | 打开文件选择器，accept=".pdf" |
| 上传文件 | 选择文件后 | `uploadReport(file)` | 显示上传进度 → 成功后自动触发解析 |
| 自动解析 | 上传成功 | `parseReport(reportId)` | 显示"解析中..." → 完成后刷新列表 |

**交互细节**：
- 上传中禁用上传按钮，显示 loading 状态
- 上传成功后自动调用解析 API（不需要用户手动触发）
- 解析完成后自动刷新研报列表
- 错误时弹出错误提示（从 error.code 映射中文）

#### 4.4.2 研报列表（S2 阶段交付）

| 功能 | 触发 | API 调用 | 行为 |
|------|------|----------|------|
| 加载列表 | 页面渲染 | `getReports()` | 渲染研报卡片列表 |
| 筛选 | 输入筛选条件 | `getReports(filters)` | 过滤列表 |
| 查看详情 | 点击研报卡片 | — | 展开解析结果 |
| 删除 | 点击删除按钮 | `deleteReport(id)` | 确认弹窗 → 删除 → 刷新列表 |
| 下载 | 点击下载按钮 | `downloadReportFile(id)` | 下载 PDF |

**研报卡片展示**（对齐 `06` §3.3）：

| 字段 | 展示方式 |
|------|----------|
| title | 卡片标题，加粗 |
| stock_code + stock_name | 蓝色标签 |
| industry | 灰色标签 |
| rating | 彩色标签（买入=绿 #52c41a、增持=浅绿 #95de64、中性=灰 #d9d9d9、减持=橙 #fa8c16、卖出=红 #ff4d4f） |
| target_price | 数值文本，单位：元 |
| upload_time | 相对时间 + tooltip 完整时间 |
| parse_status | 状态标签（pending=灰, parsing=蓝, completed=绿, failed=红） |

**筛选区域**：
| 筛选项 | 控件类型 | 对应 API 参数 |
|--------|----------|---------------|
| 股票代码 | 文本输入 | `stock_code` |
| 行业 | 文本输入 | `industry` |
| 时间范围 | 日期选择 | `date_from` + `date_to` |

**解析结果详情展示**（对齐 `06` §4）：

| 字段 | 展示方式 |
|------|----------|
| title | 大字号加粗 |
| rating | 彩色标签 + 文字 |
| target_price | 数值，单位：元 |
| key_points | 多行文本，支持折叠/展开 |
| stock_code | 链接样式，点击跳转到知识库（切换 Tab + 选中股票） |
| stock_name | 跟随股票代码显示 |
| parse_time_ms | 解析耗时 |

**State**：
| 变量 | 类型 | 初始值 | 说明 |
|------|------|--------|------|
| `reports` | Report[] | [] | 研报列表 |
| `selectedReport` | Report\|null | null | 当前查看的研报 |
| `loading` | boolean | false | 加载状态 |
| `uploadProgress` | number | 0 | 上传进度 |
| `error` | string\|null | null | 错误信息 |
| `filters` | object | {} | 筛选条件 |

### 4.5 知识库页 — KnowledgeBase.jsx（对齐 `06` §5）

#### 4.5.1 股票列表视图（S2 阶段交付）

| 功能 | 触发 | API 调用 | 行为 |
|------|------|----------|------|
| 加载列表 | 页面渲染 | `getStocks()` | 展示按股票聚合的列表 |
| 搜索 | 输入股票代码/名称 | 前端过滤 | 实时过滤列表 |
| 进入详情 | 点击股票项 | `getStockDetail(code)` | 展示详情页 |

**股票列表项展示**：
| 字段 | 展示方式 |
|------|----------|
| stock_code | 代码标签 |
| stock_name | 名称文本 |
| industry | 行业标签 |
| report_count | "共 N 份研报" |
| latest_report_date | 最新研报日期 |

#### 4.5.2 股票详情视图（S2 阶段交付）

| 区域 | 内容 | API |
|------|------|-----|
| 股票概要 | stock_code, stock_name, industry | `getStockDetail(code)` |
| 最近观点汇总 | recent_summary（多行文本） | 同上 |
| 关联研报列表 | 研报卡片列表 | 同上 |

#### 4.5.3 行情数据区域（S4 阶段交付）

| 区域 | 内容 | API |
|------|------|-----|
| 行情数据 | PE、PB、市值、最新价、数据时间 | `getMarketData(code)` |

**降级处理**（对齐 `06` §5.3、`07` §1.2）：
- `source="akshare"` 或 `"cache"`：正常展示指标
- `source="unavailable"`：每个指标位置显示"暂无数据"
- `source="cache"`：额外标注"数据更新于 {data_time}"
- 行情数据区域加载失败不影响页面其他功能

**State**：
| 变量 | 类型 | 初始值 | 说明 |
|------|------|--------|------|
| `stocks` | Stock[] | [] | 股票列表 |
| `selectedStock` | Stock\|null | null | 当前股票 |
| `marketData` | MarketData\|null | null | 行情数据 |
| `searchQuery` | string | '' | 搜索关键词 |
| `loading` | boolean | false | 加载状态 |

### 4.6 研报比对页 — ReportCompare.jsx（对齐 `06` §6）

#### 4.6.1 研报选择区域（S3 阶段交付）

| 功能 | 触发 | API 调用 | 行为 |
|------|------|----------|------|
| 选择股票 | 下拉选择 | `getStocks()` | 加载该股票的研报列表 |
| 加载研报 | 选股后 | `getStockDetail(code)` | 展示可选研报 |
| 选择研报 | 勾选 checkbox | — | 勾选 ≥ 2 份后启用"开始比对" |
| 发起比对 | 点击"开始比对" | `compareReports(ids)` | loading → 展示结果 |

**交互细节**：
- 股票下拉选择器：显示 stock_code + stock_name
- 研报列表带 checkbox，显示标题 + 评级 + 上传时间
- 勾选数 < 2 时"开始比对"按钮禁用
- 比对中显示 loading 状态（比对耗时可能较长，对齐 `07` §1.1 P95 < 15s）

#### 4.6.2 比对结果展示（S3 阶段交付）

| 区域 | 数据来源 | 展示方式 |
|------|----------|----------|
| 基本信息对照表 | `reports_summary` | 表格：每列一份研报，行=标题/评级/目标价 |
| 相似观点合并 | `similarities` | 卡片列表：主题 + 合并描述 + 来源标注 |
| 差异高亮 | `differences` | 对比卡片：字段名 + 各研报值 + 差异说明 |

**差异展示样式**：
- `field="rating"` → 不同评级用各自颜色标签并排展示
- `field="target_price"` → 数值高亮 + 差距百分比（如"差距 5.7%"）
- `field="key_points"` → 差异内容黄色背景高亮

**State**：
| 变量 | 类型 | 初始值 | 说明 |
|------|------|--------|------|
| `stocks` | Stock[] | [] | 股票列表（用于选择器） |
| `selectedStockCode` | string\|null | null | 选中的股票 |
| `stockReports` | Report[] | [] | 该股票的研报列表 |
| `compareReportIds` | string[] | [] | 勾选的研报 ID |
| `compareResult` | CompareResult\|null | null | 比对结果 |
| `loading` | boolean | false | 比对中 |
| `error` | string\|null | null | 错误信息 |

## 5. 通用组件

| 组件 | 用途 | 使用页面 |
|------|------|----------|
| `ErrorMessage` | 统一错误提示 | 全部 |
| `Loading` | 加载中 spinner | 全部 |
| `ConfirmDialog` | 确认弹窗（删除等危险操作） | ReportManager |
| `RatingTag` | 评级彩色标签 | ReportManager, ReportCompare |
| `StatusTag` | 解析状态标签 | ReportManager |

## 6. 样式规范（App.css）

### 6.1 颜色系统

| 用途 | 颜色值 |
|------|--------|
| 主色调 | #1890ff |
| 成功/买入 | #52c41a |
| 增持 | #95de64 |
| 中性 | #d9d9d9 |
| 警告/减持 | #fa8c16 |
| 错误/卖出 | #ff4d4f |
| 背景色 | #f5f5f5 |
| 卡片背景 | #ffffff |
| 文字主色 | #333333 |
| 文字次色 | #666666 |
| 差异高亮背景 | #fff7e6（黄色）/ #fff1f0（红色） |

### 6.2 布局

| 规格 | 值 |
|------|-----|
| 页面最大宽度 | 1200px |
| 卡片间距 | 16px |
| 内边距 | 24px |
| 圆角 | 8px |
| 阴影 | 0 2px 8px rgba(0,0,0,0.1) |

## 7. 前后端联调要点

### 7.1 Vite 代理配置

开发环境通过 Vite proxy 将 `/api` 请求转发到 Flask 后端 `http://localhost:5000`，避免跨域问题。

### 7.2 联调顺序

| 阶段 | 前端 | 后端 | 联调重点 |
|------|------|------|----------|
| S1 | 上传区 + 解析展示 | Task1 upload + parse | 文件上传 multipart → 自动解析 → 状态轮转 |
| S2 | 列表 + 筛选 + 知识库 | Task2 reports + kb | 列表渲染 + 筛选参数 + 级联删除后列表刷新 |
| S3 | 比对页 | Task3 compare | 研报选择 → 比对请求 → 结果渲染 |
| S4 | 行情区 | Task3 market-data | 行情数据展示 + 降级 "暂无数据" |

### 7.3 联调 Checklist

- [ ] S1: 上传 PDF → 返回 report_id → 自动触发解析 → 解析结果展示
- [ ] S1: 上传非 PDF → 前端显示 "仅支持 PDF 格式文件"
- [ ] S2: 研报列表渲染 → 筛选生效 → 删除确认 → 列表刷新
- [ ] S2: 知识库股票列表 → 点击详情 → 观点汇总展示
- [ ] S3: 选择股票 → 勾选研报 → 比对结果三区域展示
- [ ] S4: 行情数据正常展示 → AKShare 不可用时显示 "暂无数据"

## 8. 测试

### 8.1 手动测试 Checklist

| # | 场景 | 预期 |
|---|------|------|
| 1 | 上传 PDF 研报 | 上传成功 → 自动解析 → 列表刷新 |
| 2 | 上传非 PDF 文件 | 错误提示 "仅支持 PDF 格式文件" |
| 3 | Tab 切换 | 3 个页面正常切换 |
| 4 | 研报列表筛选 | 按股票代码/行业筛选生效 |
| 5 | 删除研报 | 弹出确认 → 确认后删除 → 列表刷新 |
| 6 | 知识库浏览 | 股票列表 → 详情 → 观点汇总 |
| 7 | 知识库搜索 | 前端过滤生效 |
| 8 | 研报比对 | 选择 ≥ 2 份 → 比对结果展示 |
| 9 | 行情数据展示 | PE/PB/市值正常显示 |
| 10 | 行情数据降级 | AKShare 不可用时显示 "暂无数据" |

## 9. 验收标准（汇总全部 US 中前端相关 AC）

### US-001 研报上传
- [ ] AC-001-01: 上传 PDF 成功，页面显示上传结果
- [ ] AC-001-02: 上传非 PDF 被拒绝，前端显示错误信息
- [ ] AC-001-03: 上传超大文件被拒绝，前端显示错误信息

### US-002 研报解析
- [ ] AC-002: 上传后自动触发解析，解析结果在页面展示

### US-003 知识库浏览
- [ ] AC-003-01: 以股票维度展示列表
- [ ] AC-003-02: 点击股票展示关联研报
- [ ] AC-003-03: 展示最近观点汇总
- [ ] AC-003-04: 支持时间筛选/排序
- [ ] AC-003-05: 展示行情数据

### US-004 研报比对
- [ ] AC-004-01: 选择 ≥ 2 份同公司研报发起比对
- [ ] AC-004-02: 展示相似信息合并视图
- [ ] AC-004-03: 差异内容高亮标注
- [ ] AC-004-04: 包含每份研报核心字段

### US-006 研报管理
- [ ] AC-006-01: 研报列表展示完整信息
- [ ] AC-006-02: 支持筛选
- [ ] AC-006-03: 删除时级联删除
- [ ] AC-006-04: 删除前确认弹窗

### US-007 行情数据
- [ ] AC-007-01: 展示 PE/PB/市值
- [ ] AC-007-03: 不可用时降级显示"暂无数据"

## 10. DoD（Definition of Done）

- [ ] 3 个页面组件全部实现并可交互
- [ ] Tab 导航正常切换
- [ ] API 客户端封装完整（11 个端点）
- [ ] 统一错误处理 + 中文错误提示
- [ ] 研报上传 → 自动解析完整流程
- [ ] 研报列表 + 筛选 + 删除 + 下载
- [ ] 知识库浏览 + 观点汇总 + 行情数据 + 降级
- [ ] 研报比对 + 结果三区域展示
- [ ] 确认弹窗、Loading 状态、空状态处理
- [ ] Vite 代理配置，开发环境前后端联调无跨域

---

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1 | 2026-04-15 | 首版生成 |
