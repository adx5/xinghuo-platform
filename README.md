# 星火引力｜品牌增长资源撮合平台

星火引力｜聚星火之力，引商业共生。

这是一个基于 **FastAPI + LangGraph + DeepSeek** 的智能商业资源撮合平台。通过 AI 语义理解，实现需求发布、安全风控、智能匹配与线索对接的完整商业闭环。

## 🌟 核心功能

- **引力撮合**：基于大模型的语义理解，精准匹配商业供需双方。
- **安全拦截**：同步内容风控，自动识别并拦截虚假宣传与黑产信息。
- **资源节点库**：支持商业资源发布，并包含 VIP 流量置顶（引力加速）机制。
- **线索收集**：真实对接弹窗，收集客户联系方式与需求留言。
- **运营后台**：数据仪表盘、线索池管理、资源上下架管理。

## 🏗️ 技术架构

- **前端**：原生 HTML + Tailwind CSS + Fetch API（托管于 GitHub Pages）
- **后端 API**：FastAPI（部署于 FastAPI Cloud）
- **AI 工作流**：LangGraph（状态管理、条件路由、重试门控）
- **大语言模型**：DeepSeek API（OpenAI 兼容格式）
- **云数据库**：Turso (libsql) 云端持久化存储

## 📂 项目结构

```text
├── app/                  # 后端核心代码
│   ├── server.py         # FastAPI 路由与 API 入口
│   ├── graph.py          # LangGraph 工作流编排
│   ├── agents.py         # 安全、结构化、匹配等智能体
│   ├── database.py       # 数据库模型与 Turso 连接
│   └── vector_store.py   # 本地语义检索算法
├── data/                 # 本地资源池数据
├── index.html            # 前台首页（引力撮合/资源库）
├── admin.html            # 运营管理后台
├── requirements.txt      # Python 依赖
└── pyproject.toml        # FastAPI Cloud 部署配置