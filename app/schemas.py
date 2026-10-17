from typing import TypedDict, Optional, Literal, List, Dict, Any


class MatchState(TypedDict, total=False):
    raw_requirement: str
    risk_verdict: Optional[Dict[str, Any]]
    structured_need: Optional[Dict[str, Any]]
    candidates: List[Dict[str, Any]]
    match_round: int
    retry_hint: Optional[str]
    final_status: Literal["pending", "matched", "rejected", "exhausted"]
