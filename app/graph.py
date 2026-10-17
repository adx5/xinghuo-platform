from langgraph.graph import StateGraph, END
from app.schemas import MatchState
from app.config import RISK_THRESHOLD, MAX_MATCH_ROUNDS
from app.agents import safety_check, structure_need, match_candidates

# 引入向量检索模块
from app.vector_store import search_similar_resources


def safety_node(state: MatchState):
    verdict = safety_check(state["raw_requirement"])
    return {"risk_verdict": verdict}


def structure_node(state: MatchState):
    structured = structure_need(state["raw_requirement"])
    return {"structured_need": structured}


def match_node(state: MatchState):
    structured_need = state.get("structured_need") or {}
    raw_req = state.get("raw_requirement", "")

    # 组合原始需求和结构化标签，作为向量搜索的查询语句
    query_text = f"{raw_req} 行业:{structured_need.get('industry')} 地域:{structured_need.get('region')} 类型:{structured_need.get('resource_type')}"

    # 去向量库捞最相关的 10 条数据 (完全替代了之前的 SQL 查询)
    pool = search_similar_resources(query_text, n_results=10)

    result = match_candidates(
        structured_need,
        pool,
        state.get("retry_hint"),
    )
    return {"candidates": result.get("candidates", []), "final_status": "pending"}


def retry_node(state: MatchState):
    new_round = int(state.get("match_round", 0)) + 1
    hint = (
        "上一轮候选为空或匹配理由质量不足。"
        "请放宽地域或行业限制，优先选择能力互补、资源类型契合的对象。"
    )
    return {"match_round": new_round, "retry_hint": hint, "candidates": []}


def accept_node(state: MatchState):
    return {"final_status": "matched"}


def reject_node(state: MatchState):
    return {"final_status": "rejected"}


def exhaust_node(state: MatchState):
    return {"final_status": "exhausted"}


def route_after_safety(state: MatchState):
    verdict = state.get("risk_verdict") or {}
    if float(verdict.get("risk_score", 1.0)) >= RISK_THRESHOLD:
        return "reject"
    return "structure"


def route_after_match(state: MatchState):
    candidates = state.get("candidates") or []
    if not candidates:
        return "retry"

    weak = 0
    for c in candidates:
        reason = str(c.get("reason", ""))
        try:
            score = float(c.get("match_score", 0.0))
        except (TypeError, ValueError):
            score = 0.0
        if len(reason) < 15 or score < 0.4:
            weak += 1

    if weak > len(candidates) / 2:
        return "retry"
    return "accept"


def route_retry(state: MatchState):
    if int(state.get("match_round", 0)) >= MAX_MATCH_ROUNDS:
        return "exhaust"
    return "match"


def build_graph():
    workflow = StateGraph(MatchState)

    workflow.add_node("safety", safety_node)
    workflow.add_node("structure", structure_node)
    workflow.add_node("match", match_node)
    workflow.add_node("retry", retry_node)
    workflow.add_node("accept", accept_node)
    workflow.add_node("reject", reject_node)
    workflow.add_node("exhaust", exhaust_node)

    workflow.set_entry_point("safety")

    workflow.add_conditional_edges(
        "safety",
        route_after_safety,
        {"structure": "structure", "reject": "reject"},
    )
    workflow.add_edge("structure", "match")
    workflow.add_conditional_edges(
        "match",
        route_after_match,
        {"accept": "accept", "retry": "retry"},
    )
    workflow.add_conditional_edges(
        "retry",
        route_retry,
        {"match": "match", "exhaust": "exhaust"},
    )

    workflow.add_edge("accept", END)
    workflow.add_edge("reject", END)
    workflow.add_edge("exhaust", END)

    return workflow.compile()