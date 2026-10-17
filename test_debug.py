import traceback
from app.graph import build_graph

# 模拟前端发来的初始状态
init_state = {
    "raw_requirement": "我有个充电桩项目，想在四川找4S店合作",
    "match_round": 0,
    "candidates": [],
    "final_status": "pending",
}

print("开始运行 LangGraph...")
try:
    workflow_app = build_graph()
    result = workflow_app.invoke(init_state)
    print("运行成功！结果如下：")
    print(result)
except Exception as e:
    print("\n❌ 抓到了！底层的真实报错如下：")
    # 这行代码会把完整的报错堆栈打印出来
    traceback.print_exc()