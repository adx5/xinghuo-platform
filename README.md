# 信商圈 MVP：安全校验 -> 需求结构化 -> 匹配 -> 门控重试

这是一个基于 DeepSeek + LangGraph 的最小可运行闭环。

## 目录

- app/config.py：环境变量与阈值
- app/schemas.py：LangGraph 共享状态定义
- app/deepseek_client.py：DeepSeek OpenAI 兼容客户端与 JSON 解析
- app/agents.py：安全校验、需求结构化、匹配智能体
- app/graph.py：LangGraph 图、条件边、重试门控
- app/main.py：示例入口
- data/resource_pool.json：示例资源池

## 运行

~~~bash
python -m venv .venv
source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
python -m app.main
~~~

## 当前闭环

1. 内容安全智能体同步校验，risk_score >= 0.7 直接拒绝。
2. 需求结构化智能体输出行业、地域、资源类型、合作模式、预算、关键词。
3. 匹配智能体只从给定资源池中选择，禁止编造 resource_id，最多返回 5 个候选。
4. 领航员门控检查候选是否为空、匹配理由是否过短、分数是否过低。
5. 不达标则重试，最多 2 轮；超过后进入 exhausted，避免无限循环。
6. 达标进入 matched。

## 下一步

- 把 resource_pool.json 换成真实资源池。
- 资源入库时做 Embedding，先粗召回 Top-K，再交给匹配智能体精排。
- 为付费、流量托管、账号权限变更加入人工审批门。
- 把运营召回、风控告警做成事件驱动旁路，不要挤占主链路上下文。
