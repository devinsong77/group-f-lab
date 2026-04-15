# 投研分析平台 (Investment Research Platform)

基于 Flask + React 的金融研报智能分析平台，支持研报上传解析、知识库管理、多报告比对及实时行情数据查询。

## 功能特性

- **研报管理** — PDF 上传、LLM 智能解析（评级/目标价/核心观点/股票代码等）、列表筛选、下载、删除
- **知识库** — 按股票自动聚合研报，LLM 生成综合摘要
- **研报比对** — 同公司多份研报评级、目标价、核心观点差异对比（LLM 语义比对 + 本地降级）
- **行情数据** — 腾讯行情 → 东方财富多数据源降级，带内存缓存

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3, Flask 3, flask-cors |
| PDF 解析 | PyPDF2, pdfplumber |
| LLM | OpenAI 兼容接口（Qwen3.5 / GLM-4 双模型降级） |
| 前端 | React 19, Vite 8 |
| 行情 | 腾讯行情 API, 东方财富 API |
| 数据存储 | JSON 文件（reports.json / parsed_reports.json / knowledge_base.json） |

## 项目结构

```
investment-research-platform/
├── backend/
│   ├── blueprints/          # Flask 蓝图（report_bp / kb_bp / compare_bp）
│   ├── data/                # 运行时数据（JSON + PDF）
│   ├── tests/               # pytest 测试
│   ├── app.py               # Flask 入口 & 工厂函数
│   ├── parser.py            # PDF 提取 + LLM 结构化解析
│   ├── comparator.py        # 多研报比对引擎
│   ├── knowledge_base.py    # 知识库聚合 & 摘要生成
│   ├── stock_data.py        # 多源行情服务
│   ├── storage.py           # JSON 持久化层
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/           # 研报管理 / 知识库 / 研报比对 页面
│   │   ├── App.jsx          # 主应用 & Tab 导航
│   │   └── api.js           # 后端 API 调用封装
│   ├── package.json
│   └── vite.config.js       # 开发代理 → localhost:5002
├── spec/                    # 需求 & 设计文档
└── tasks/                   # 任务拆解清单
```

## 快速开始

### 1. 后端

```bash
cd backend

# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动服务（默认 0.0.0.0:5002）
python app.py
```

### 2. 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器（Vite 自动代理 /api → localhost:5002）
npm run dev
```

### 3. 构建前端生产包

```bash
cd frontend
npm run build    # 产出 dist/
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATA_DIR` | 数据存储目录 | `data` |
| `LLM_API_KEY` | OpenAI 兼容 API Key | 内置默认 |
| `LLM_BASE_URL` | LLM 服务地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `LLM_MODEL` | 主模型 | `qwen3.5-plus` |
| `LLM_FALLBACK_MODEL` | 降级模型 | `glm-4-flash` |

## API 概览

所有接口以 `/api/v1` 为前缀。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/reports/upload` | 上传 PDF 研报 |
| POST | `/reports/<id>/parse` | 解析研报 |
| GET | `/reports` | 研报列表（支持筛选） |
| GET | `/reports/<id>` | 研报详情 |
| DELETE | `/reports/<id>` | 删除研报 |
| GET | `/reports/<id>/file` | 下载原始 PDF |
| POST | `/reports/compare` | 多研报比对 |
| GET | `/kb/stocks` | 知识库股票列表 |
| GET | `/kb/stocks/<code>` | 股票详情 |
| GET | `/kb/stocks/<code>/reports` | 股票关联研报 |
| GET | `/stocks/<code>/market-data` | 实时行情数据 |

## 测试

```bash
cd backend
pytest tests/ -v
```
