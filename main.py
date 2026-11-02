"""
Main Entry Point for Cal/Val Agent.

Usage:
    python -m agents.workflow "your task description here"
    or: python main.py "your task description here"
"""

import sys
from pathlib import Path

# Add parent directory to path (for non-module invocation)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents.state import AgentState
from agents.workflow import workflow_graph

# Alias for backward compatibility
workflow = workflow_graph


def run_agent(task_text: str):
    """Run the Cal/Val Agent LangGraph workflow."""
    
    initial_state: AgentState = {
        "task_text": task_text,
        "logs": [],
        "status": "pending"
    }
    
    print(f"开始处理任务：{task_text}")
    print("=" * 60)
    
    # Run the workflow
    final_state = workflow.invoke(initial_state)
    
    # Print results
    print("=" * 60)
    print("任务完成状态:", final_state.get("status", "unknown"))
    
    if final_state.get("results"):
        print("\n结果摘要:")
        for r in final_state["results"]:
            if r.get("status") == "success":
                print(f"  ✓ 成功")
                print(f"    偏差均值：{r.get('bias_mean', 0):.4f} m")
                print(f"    RMSE: {r.get('rmse', 0):.4f} m")
                print(f"    样本数：{r.get('n_samples', 0)}")
                if r.get("r_squared") is not None:
                    print(f"    R²: {r.get('r_squared'):.4f}")
            else:
                print(f"  ✗ 失败：{r.get('error', '未知错误')}")
    
    if final_state.get("logs"):
        print(f"\n执行日志 ({len(final_state['logs'])} 条):")
        for log in final_state["logs"]:
            print(f"  [{log.get('event', '')}] {str(log.get('data', ''))[:80]}")
    
    return final_state


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法：python main.py \"任务描述\"")
        print("\n示例:")
        print('  python main.py "用 HY-1D 与 VIIRS 做夏季星间交叉定标"')
        print('  python main.py "用验潮站做绝对基准参考"')
        print('  python main.py "用同星自交叉监测漂移"')
    else:
        task = " ".join(sys.argv[1:])
        run_agent(task)