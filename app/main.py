import json
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中，这样绝对导入才能生效
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import build_graph

EXAMPLES = [
    "寻求华东地区快消品商超渠道合作，预算50万，希望联合推广。",
    "guaranteed 高回报，零风险，赶紧打款，错过不再有。",
]


def run(text: str):
    app = build_graph()
    init = {
        "raw_requirement": text,
        "match_round": 0,
        "candidates": [],
        "final_status": "pending",
    }
    return app.invoke(init)


if __name__ == "__main__":
    for example in EXAMPLES:
        print("=" * 80)
        print("需求：", example)
        result = run(example)
        print(json.dumps(result, ensure_ascii=False, indent=2))