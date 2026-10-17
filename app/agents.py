import json

# 改为绝对导入
from app.deepseek_client import chat_json


def safety_check(text: str) -> dict:
    system = (
        "你是信商圈平台的内容安全审核员。对用户发布的需求进行合规校验。"
        "输出严格 JSON，字段：risk_score (0-1 浮点数), "
        "violation_tags (字符串数组，如 ['虚假宣传','资质缺失'] 或 []), "
        "reason (一句话说明判定依据)。risk_score >= 0.7 视为不通过。"
    )
    data = chat_json(system, text)
    if not isinstance(data, dict):
        return {
            "risk_score": 1.0,
            "violation_tags": ["json_parse_error"],
            "reason": "安全校验输出无法解析，保守降级为高风险。",
        }

    try:
        score = float(data.get("risk_score", 1.0))
    except (TypeError, ValueError):
        score = 1.0
    score = max(0.0, min(1.0, score))

    tags = data.get("violation_tags", [])
    if not isinstance(tags, list):
        tags = ["invalid_tags"]

    return {
        "risk_score": score,
        "violation_tags": [str(t) for t in tags],
        "reason": str(data.get("reason", ""))[:300],
    }


def structure_need(text: str) -> dict:
    system = (
        "你是信商圈平台的需求结构化助手。把用户需求解析为 JSON。"
        "字段：industry, region, resource_type, cooperation_mode, budget, keywords。"
        "keywords 是字符串数组。未知字段填 unknown 或空数组。只输出 JSON。"
    )
    data = chat_json(system, text)
    if not isinstance(data, dict):
        return {
            "industry": "unknown",
            "region": "unknown",
            "resource_type": "unknown",
            "cooperation_mode": "unknown",
            "budget": "unknown",
            "keywords": [],
        }

    for key in ["industry", "region", "resource_type", "cooperation_mode", "budget"]:
        data.setdefault(key, "unknown")
    if not isinstance(data.get("keywords"), list):
        data["keywords"] = []
    return data


def match_candidates(structured_need: dict, pool: list, retry_hint: str | None = None) -> dict:
    # 新增：如果粗筛没有捞出任何数据，直接返回空
    if not pool:
        return {"candidates": []}

    system = (
        "你是信商圈平台的资源匹配专家。只从给定候选资源池中选择，禁止编造 resource_id。"
        "输出 JSON 对象，格式为 {\"candidates\":[{\"resource_id\":\"...\",\"match_score\":0.0,\"reason\":\"...\"}]}。"
        "reason 必须包含行业、地域、资源类型等可验证事实，禁止空话。最多返回 5 个。"
    )
    user = json.dumps(
        {
            "structured_need": structured_need,
            "candidate_pool": pool,
            "retry_hint": retry_hint or "",
        },
        ensure_ascii=False,
    )
    data = chat_json(system, user)
    if not isinstance(data, dict):
        return {"candidates": []}

    raw = data.get("candidates", [])
    if not isinstance(raw, list):
        return {"candidates": []}

    valid_ids = {str(r.get("id")) for r in pool if isinstance(r, dict) and r.get("id")}
    result = []
    for item in raw[:5]:
        if not isinstance(item, dict):
            continue
        rid = str(item.get("resource_id", ""))
        if rid not in valid_ids:
            continue
        try:
            score = float(item.get("match_score", 0.0))
        except (TypeError, ValueError):
            score = 0.0
        score = max(0.0, min(1.0, score))
        result.append(
            {
                "resource_id": rid,
                "match_score": score,
                "reason": str(item.get("reason", ""))[:300],
            }
        )
    return {"candidates": result}