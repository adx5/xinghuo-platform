import json
import time
from openai import OpenAI

# 改为绝对导入
from app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL, MOCK_MODE

client = None
if not MOCK_MODE and DEEPSEEK_API_KEY:
    masked = DEEPSEEK_API_KEY[:6] + "..." + DEEPSEEK_API_KEY[-4:] if len(DEEPSEEK_API_KEY) > 10 else "***"
    print(f"[deepseek] 真实 API 模式已加载: {masked}")
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
elif MOCK_MODE:
    print("[deepseek] ⚠️ Mock 模式已开启，不会发起真实的网络请求，不消耗 Token")


def chat_json(system: str, user: str):
    if MOCK_MODE:
        time.sleep(0.5)  # 模拟一点网络延迟，让运行过程看起来更真实
        # 1. 模拟安全校验节点
        if "内容安全审核员" in system:
            if "高回报" in user or "风险" in user:
                return {"risk_score": 0.9, "violation_tags": ["虚假宣传"], "reason": "包含诱导性词汇"}
            return {"risk_score": 0.1, "violation_tags": [], "reason": "正常商业需求"}

        # 2. 模拟需求结构化节点
        elif "需求结构化助手" in system:
            return {
                "industry": "快消品",
                "region": "华东",
                "resource_type": "商超渠道",
                "cooperation_mode": "联合推广",
                "budget": "50万",
                "keywords": ["华东", "快消", "商超", "联合推广"]
            }

        # 3. 模拟匹配节点
        elif "资源匹配专家" in system:
            # 为了演示领航员门控和重试逻辑，故意检测如果是重试，就返回空或者低分
            if "重试" in user or "质量不足" in user:
                # 模拟重试后找到了好结果
                return {"candidates": [
                    {"resource_id": "r001", "match_score": 0.95,
                     "reason": "重试后：华东快消渠道联盟完美匹配快消品和商超需求"},
                    {"resource_id": "r004", "match_score": 0.88, "reason": "重试后：品牌联合推广服务商符合联合推广需求"}
                ]}

            # 默认返回正常结果
            return {"candidates": [
                {"resource_id": "r001", "match_score": 0.92,
                 "reason": "覆盖华东地区300+商超门店，擅长新品铺货，完美符合需求。"},
                {"resource_id": "r004", "match_score": 0.85, "reason": "提供跨品牌联名活动策划，擅长快消异业合作。"}
            ]}

        return {}

    # 以下是真实的 API 调用逻辑
    if client is None:
        raise RuntimeError("DEEPSEEK_API_KEY 未设置，且未开启 MOCK_MODE。请检查 .env")

    resp = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = resp.choices[0].message.content or ""
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:].strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None