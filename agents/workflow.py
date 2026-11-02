"""
LangGraph 工作流 - 完整校准/验证 Agent 编排。

用法:
    from agents.workflow import create_workflow
    graph = create_workflow()
    result = graph.invoke({"task_text": "用 S6A 和 JA3 做星间交叉"})
"""

from typing import Dict, Any, Optional, Literal
from pathlib import Path
from langgraph.graph import StateGraph, END
from .state import AgentState
from .task_parser import parse_task
try:
    from ..operators import ALL_OPERATORS
    from ..core.op_config import LocalConfig
except ImportError:
    from operators import ALL_OPERATORS
    from core.op_config import LocalConfig


def task_parser_node(state: AgentState) -> AgentState:
    text = state.get("task_text", "")
    if not text:
        return {
            "parsed_task": {"method": None, "error": "Empty task text"},
            "status": "failed",
            "logs": state["logs"] + [{"event": "task_parsed", "status": "error"}],
        }
    parsed = parse_task(text)
    parsed["task_text"] = text
    return {
        "parsed_task": parsed,
        "logs": state["logs"] + [{"event": "task_parsed", "method": parsed.get("method")}],
    }


def data_health_check_node(state: AgentState) -> AgentState:
    """数据质量诊断节点 - 检查数据健康状况"""
    from .data_health_check import DataHealthChecker
    
    selected = state.get("selected_data") or {}
    available = state.get("available_datasets", [])
    
    if not selected and not available:
        return {
            "health_report": {"status": "no_data", "message": "无可用数据"},
            "logs": state["logs"] + [{"event": "health_check_skipped", "reason": "no_data"}],
        }
    
    checker = DataHealthChecker()
    
    # 如果有具体文件路径，进行详细检查
    if selected.get("path"):
        path = selected["path"]
        
        # NC 文件检查
        if path.endswith('.nc'):
            health = checker.check_nc_integrity(path)
        # H5 文件检查
        elif path.endswith('.h5'):
            health = checker.check_h5_integrity(path)
        # 目录检查（批量）
        else:
            from .data_health_check import quick_scan
            health = quick_scan(path)
    else:
        # 对可用数据集进行快速扫描
        health = checker.assess_coverage(available)
    
    # 生成诊断报告
    corrupted_count = health.get("corrupted", 0)
    healthy_count = health.get("healthy", 0)
    total_count = health.get("total_files", 0)
    
    # 计算损坏比例
    corruption_ratio = corrupted_count / total_count if total_count > 0 else 0
    
    # 判断健康状态等级
    if corrupted_count == total_count or corruption_ratio > 0.8:
        status = "critical"
    elif healthy_count == 0 and corrupted_count > 0:
        status = "degraded"
    elif corruption_ratio > 0.3:
        status = "warning"
    else:
        status = "healthy"
    
    report = {
        "status": status,
        "details": health,
        "recommendations": []
    }
    
    # 根据诊断结果生成建议
    if status == "critical":
        report["recommendations"].append(f"严重警告：{corrupted_count}/{total_count} 文件损坏，无法继续定标作业")
        report["recommendations"].append("建议：1. 重新下载完整数据  2. 切换 SSH 远程执行模式")
    elif status == "degraded":
        report["recommendations"].append(f"警告：{corrupted_count}/{total_count} 文件无法读取")
        report["recommendations"].append("建议：检查数据完整性或联系数据提供方")
    elif status == "warning":
        report["recommendations"].append(f"部分文件存在问题 ({corrupted_count}个)，但仍可尝试继续")
    
    return {
        "health_report": report,
        "logs": state["logs"] + [{"event": "health_check_completed", "status": status, "corrupted": corrupted_count, "healthy": healthy_count}],
    }


def method_recommendation_node(state: AgentState) -> AgentState:
    """方法推荐节点 - 基于数据和诊断结果推荐最佳定标方法"""
    parsed = state.get("parsed_task", {})
    health = state.get("health_report", {})
    
    if not parsed:
        return {
            "recommendation": None,
            "logs": state["logs"] + [{"event": "recommendation_skipped", "reason": "no_parsed_task"}],
        }
    
    # 获取诊断结果
    health_status = health.get("status", "unknown")
    
    # 如果数据不健康，阻止执行
    if health_status in ("critical", "degraded"):
        return {
            "recommendation": {
                "action": "abort",
                "reason": f"数据质量不佳 ({health_status})",
                "suggestion": health.get("recommendations", ["请检查数据完整性"])
            },
            "branch_path": "abort_data_quality",
            "logs": state["logs"] + [{"event": "recommendation_abort", "reason": health_status}],
        }
    
    # 基于任务类型和数据特征推荐
    method = parsed.get("method")
    available_count = len(state.get("available_datasets", []))
    
    recommendation = {
        "action": "proceed",
        "method": method,
        "confidence": "high" if available_count > 5 else "medium" if available_count > 0 else "low",
        "reasoning": [],
        "alternative_methods": []
    }
    
    # 生成推荐理由
    if method == "star_cross":
        recommendation["reasoning"].append(f"星间交叉定标适合检测卫星间系统性偏差")
        if available_count < 2:
            recommendation["alternative_methods"].append({
                "method": "self_cross",
                "reason": "数据量不足，可考虑先做自交叉"
            })
    elif method == "self_cross":
        recommendation["reasoning"].append("自交叉适合监测单星漂移")
        recommendation["alternative_methods"].append({
            "method": "star_cross", 
            "reason": "如需更高精度，建议收集多星数据后做星间交叉"
        })
    elif method == "tide_ext":
        recommendation["reasoning"].append("验潮站参考提供绝对基准")
    
    # 添加通用建议
    recommendation["reasoning"].append(f"已找到 {available_count} 个可用数据集")
    
    return {
        "recommendation": recommendation,
        "branch_path": "execute" if available_count > 0 else "abort_no_data",
        "logs": state["logs"] + [{"event": "recommendation_generated", "action": recommendation["action"]}],
    }


def data_discovery_node(state: AgentState) -> AgentState:
    try:
        from ..data_adapter.explorer import LocalDataExplorer
    except ImportError:
        from data_adapter.explorer import LocalDataExplorer

    parsed = state.get("parsed_task", {})
    if not parsed or not parsed.get("method"):
        return {"available_datasets": [], "logs": state["logs"] + [{"event": "skipped_discovery"}]}

    method = parsed.get("method")
    data_map = {
        "star_cross": "GPF_test_data/star_cross",
        "self_cross": "GPF_test_data/self_cross",
        "sig0_cross": "GPF_test_data/sig0_cross",
        "ycz_match": "GPF_test_data/tide_ext",
        "tide_ext": "GPF_test_data/tide_ext",
    }
    base_dir = data_map.get(method, "GPF_test_data")

    try:
        explorer = LocalDataExplorer(base_dir)
        if method in ("star_cross", "self_cross"):
            # 策略: 优先找 NC 目录（用于 MATCH），其次找已有 NPZ（用于 CAL）
            nc_dirs = explorer.find_nc_files(
                sat_id=parsed.get("primary_sat"),
                date_range=(parsed.get("start_date"), parsed.get("end_date")),
            )
                
            # 按父目录聚合 NC 文件
            nc_by_dir = {}
            for f in nc_dirs:
                d = str(Path(f["path"]).parent)
                nc_by_dir.setdefault(d, {"path": d, "nc_files": [], "sat_id": f["sat_id"]})
                nc_by_dir[d]["nc_files"].append(f)
                
            nc_dataset_list = list(nc_by_dir.values())
                
            # 检查已有 MATCH 结果 (NPZ)
            match_files = explorer.find_match_files(
                sat_id=parsed.get("primary_sat"),
                date_range=(parsed.get("start_date"), parsed.get("end_date")),
            )
                
            # 如果有 NC 就建议 MATCH，否则建议 CAL (前提是 NPZ 存在)
            if nc_dataset_list:
                # 优先使用输入目录跑 MATCH
                datasets = nc_dataset_list
                next_step = "match"
            elif match_files:
                datasets = match_files
                next_step = "cal"
            else:
                datasets = []
                next_step = None
        elif method == "sig0_cross":
            datasets = explorer.find_h5_files(base_dir)
            next_step = "match" if datasets else None
        elif method in ("ycz_match", "tide_ext"):
            datasets = explorer.find_tide_data(base_dir)
            next_step = "match" if datasets else None
        else:
            datasets = []
            next_step = None
    except Exception as e:
        return {
            "available_datasets": [],
            "selected_data": None,
            "metadata": {"next_step": None},
            "logs": state["logs"] + [{"event": "discovery_error", "error": str(e)[:200]}],
        }

    return {
        "available_datasets": datasets,
        "selected_data": datasets[0] if datasets else None,
        "metadata": {"next_step": next_step},
        "logs": state["logs"] + [{"event": "datasets_found", "count": len(datasets)}],
    }


def branch_decision_node(state: AgentState) -> AgentState:
    parsed = state.get("parsed_task", {})
    datasets = state.get("available_datasets", [])
    retry_count = state.get("retry_count", 0)

    method = parsed.get("method")
    if not method:
        return {
            "branch_path": "fail_immediate",
            "status": "failed",
            "logs": state["logs"] + [{"event": "branch_decision", "decision": "no_method"}],
        }

    if datasets and len(datasets) >= 1:
        return {
            "branch_path": f"execute_{method}",
            "status": "running",
            "logs": state["logs"] + [{"event": "branch_decision", "decision": "execute", "n": len(datasets)}],
        }

    if retry_count < 3:
        return {
            "branch_path": "fallback_relax_params",
            "retry_count": retry_count + 1,
            "logs": state["logs"] + [{"event": "branch_decision", "decision": "fallback", "retry": retry_count + 1}],
        }

    return {
        "branch_path": "fail_exhausted",
        "status": "failed",
        "logs": state["logs"] + [{"event": "branch_decision", "decision": "fail_exhausted"}],
    }


def execute_operator_node(state: AgentState) -> AgentState:
    parsed = state.get("parsed_task", {})
    selected = state.get("selected_data") or {}
    metadata = state.get("metadata") or {}
    retry_count = state.get("retry_count", 0)

    method = parsed.get("method")
    sat_id = parsed.get("primary_sat", "UNKNOWN")
    aux_type = parsed.get("aux_data_type", "UNKNOWN")

    if not method:
        return {"operator_result": {"status": "failed", "error": "No method"}, "status": "failed"}

    # 根据 discovery 阶段的 next_step 决定 MATCH/CAL
    next_step = metadata.get("next_step", "match")  # 默认 match
    has_nc_files = isinstance(selected.get("nc_files"), list) and len(selected["nc_files"]) > 0
    
    operator_name = None
    if method == "star_cross":
        operator_name = "star_cross_match" if next_step == "match" or has_nc_files else "star_cross_cal"
    elif method == "self_cross":
        operator_name = "self_cross_match" if next_step == "match" or has_nc_files else "self_cross_cal"
    elif method == "sig0_cross":
        operator_name = "sig0_cross_match" if has_nc_files else "sig0_cross_cal"
    elif method in ("ycz_match", "tide_ext"):
        operator_name = "ycz_match" if next_step == "match" else "ycz_cal"

    if operator_name is None or operator_name not in ALL_OPERATORS:
        return {"operator_result": {"status": "failed", "error": f"Unknown op: {operator_name}"}, "status": "failed"}

    op_cls = ALL_OPERATORS[operator_name]

    cfg_kwargs = {
        "sat_id": sat_id,
        "aux_data_type": aux_type if aux_type != "UNKNOWN" else parsed.get("aux_data_type", ""),
        "start_date": parsed.get("start_date", "20230101"),
        "end_date": parsed.get("end_date", "20231231"),
        "output_dir": f"output_local_test/{method}_{retry_count}",
        "input_dir": selected.get("path", "GPF_test_data"),
    }

    if method in ("ycz_match", "tide_ext"):
        cfg_kwargs.update({
            "yz_data_dir": selected.get("wstg_dir"),
            "mss_path": selected.get("mss_path"),
            "fes2014_path": selected.get("fes2014_path"),
        })

    config = LocalConfig(**cfg_kwargs)

    try:
        result = op_cls(config).run_local(cfg_kwargs["input_dir"])
    except Exception as e:
        result = {"status": "failed", "error": str(e), "traceback": str(e)[:500]}

    return {
        "operator_result": result,
        "status": "success" if result.get("status") == "success" else "failed",
        "logs": state["logs"] + [{"event": "operator_executed", "operator": operator_name, "status": result.get("status")}],
    }


def fallback_node(state: AgentState) -> AgentState:
    retry_count = state.get("retry_count", 0)
    if retry_count >= 3:
        return {"logs": state["logs"] + [{"event": "fallback_exhausted"}], "status": "failed"}

    relax_map = {1: {"distance_to_coast": 100.0}, 2: {"ocean_depth": 2000.0}, 3: {"wind_speed": [0, 50]}}
    rel = relax_map.get(retry_count, {})

    return {
        "retry_count": retry_count,
        "logs": state["logs"] + [{"event": "fallback_applied", "attempt": retry_count, "relaxation": rel}],
    }


def result_summarizer_node(state: AgentState) -> AgentState:
    result = state.get("operator_result", {})
    parsed = state.get("parsed_task", {})
    summary = {
        "task_text": state.get("task_text", ""),
        "method": parsed.get("method"),
        "satellite": parsed.get("primary_sat"),
        "aux_data": parsed.get("aux_data_type"),
        "status": state.get("status", "unknown"),
        "details": result,
        "logs": state.get("logs", []),
    }
    return {"results": [summary], "logs": state["logs"] + [{"event": "result_summarized"}]}


def create_workflow(debug: bool = False):
    graph_builder = StateGraph(AgentState)
    nodes = {
        "task_parser": task_parser_node,
        "data_discovery": data_discovery_node,
        "data_health_check": data_health_check_node,
        "method_recommendation": method_recommendation_node,
        "branch_decision": branch_decision_node,
        "execute_operator": execute_operator_node,
        "fallback": fallback_node,
        "result_summarizer": result_summarizer_node,
    }
    for name, func in nodes.items():
        graph_builder.add_node(name, func)

    graph_builder.set_entry_point("task_parser")
    graph_builder.add_edge("task_parser", "data_discovery")
    graph_builder.add_edge("data_discovery", "data_health_check")
    graph_builder.add_edge("data_health_check", "method_recommendation")

    def route_after_recommendation(state: AgentState) -> Literal["branch_decision", "result_summarizer"]:
        recommendation = state.get("recommendation", {})
        if recommendation.get("action") == "abort":
            return "result_summarizer"  # 直接结束，返回诊断报告
        return "branch_decision"

    graph_builder.add_conditional_edges(
        "method_recommendation",
        route_after_recommendation,
        {"branch_decision": "branch_decision", "result_summarizer": "result_summarizer"},
    )

    def route_branch(state: AgentState) -> Literal["execute_operator", "fallback", "result_summarizer"]:
        branch = state.get("branch_path", "")
        if branch.startswith("execute_"):
            return "execute_operator"
        elif branch.startswith("fallback"):
            return "fallback"
        elif branch.startswith("abort"):
            return "result_summarizer"
        return "result_summarizer"

    graph_builder.add_conditional_edges(
        "branch_decision",
        route_branch,
        {
            "execute_operator": "execute_operator",
            "fallback": "fallback",
            "result_summarizer": "result_summarizer"
        },
    )

    graph_builder.add_conditional_edges(
        "execute_operator",
        lambda s: "result_summarizer" if s.get("status") == "success" else "fallback",
        {"result_summarizer": "result_summarizer", "fallback": "fallback"},
    )

    graph_builder.add_edge("fallback", "branch_decision")
    graph_builder.add_edge("result_summarizer", END)
    return graph_builder.compile()


workflow_graph = create_workflow()


def run_agent(task_text: str, debug: bool = False) -> Dict[str, Any]:
    initial_state = {
        "task_text": task_text,
        "parsed_task": None,
        "available_datasets": [],
        "selected_data": None,
        "metadata": None,
        "health_report": None,
        "recommendation": None,
        "current_operator": None,
        "operator_config": None,
        "operator_result": None,
        "branch_path": None,
        "fallback_needed": False,
        "retry_count": 0,
        "results": [],
        "logs": [],
        "messages": [],
        "status": "pending",
    }
    result = workflow_graph.invoke(initial_state)
    if debug:
        print("\n=== Agent Execution Log ===")
        for log in result.get("logs", []):
            print(f"  [{log.get('event')}] {log.get('status', '')}")
        print("\n=== Final Result ===")
        print(result.get("results", [{}])[0])
    return result


if __name__ == "__main__":
    test_tasks = [
        "用 S6A 和 JA3 做 2023 年 5 月的星间交叉",
        "用 JA3 自交叉定标",
        "用验潮站做绝对基准校准",
    ]
    for task in test_tasks:
        print(f"\n{'=' * 60}")
        print(f"Task: {task}")
        print("=" * 60)
        run_agent(task, debug=True)
