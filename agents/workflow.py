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


def method_recommendation_node(state: AgentState) -> AgentState:
    """方法推荐节点 - 使用 LLM 智能分析数据特征并推荐最佳定标方法"""
    from .llm_client import LLMClient
    
    parsed = state.get("parsed_task", {})
    available_datasets = state.get("available_datasets", [])
    metadata = state.get("metadata") or {}
    
    if not parsed:
        return {
            "recommendation": None,
            "logs": state["logs"] + [{"event": "recommendation_skipped", "reason": "no_parsed_task"}],
        }
    
    # 准备 LLM 上下文（去掉健康检查部分）
    task_info = {
        "primary_satellite": parsed.get("primary_sat"),
        "auxiliary_data": parsed.get("aux_data_type"),
        "requested_method": parsed.get("method"),
        "start_date": parsed.get("start_date"),
        "end_date": parsed.get("end_date"),
    }
    
    # 构建可用数据集摘要
    dataset_summary = []
    for ds in available_datasets:
        dataset_summary.append({
            "path": ds.get("path"),
            "format": ds.get("format"),
            "size_mb": ds.get("size_mb"),
            "record_count": ds.get("record_count"),
            "time_range": ds.get("time_range"),
        })

    # 从 discovery 阶段拿统计（新版 explorer 返回的是卫星文件夹级）
    data_summary = (metadata or {}).get("data_summary", {})

    # 组装完整上下文
    context = {
        **task_info,
        "available_datasets": dataset_summary,
        "total_samples": len(dataset_summary),
        "data_summary": data_summary,
    }
    
    # 调用 LLM 生成智能推荐
    try:
        llm = LLMClient()
        recommendation_text = llm.generate_recommendation(context)
        
        recommendation = {
            "action": "proceed",
            "method": parsed.get("method"),
            "confidence": "medium",
            "reasoning": [recommendation_text],
            "alternative_methods": [],
            "llm_analysis": recommendation_text,
            "risk_factors": [],
            "warnings": []
        }
        
        text_lower = recommendation_text.lower()
        
        if "data 不足" in text_lower or "insufficient" in text_lower:
            recommendation["confidence"] = "low"
            if parsed.get("method") == "star_cross":
                recommendation["alternative_methods"].append({
                    "method": "self_cross",
                    "reason": "数据量不足，建议先用自交叉验证单星稳定性"
                })
        
        if "建议改用" in text_lower or "consider" in text_lower:
            if "自交叉" in text_lower or "self-cross" in text_lower:
                recommendation["alternative_methods"].append({
                    "method": "self_cross",
                    "reason": "LLM 建议改用自交叉方法"
                })
            elif "星间交叉" in text_lower or "cross-calibration" in text_lower:
                recommendation["alternative_methods"].append({
                    "method": "star_cross",
                    "reason": "LLM 建议改用星间交叉方法"
                })
        
        if "高风险" in text_lower or "warning" in text_lower or "caution" in text_lower:
            recommendation["warnings"].append("LLM 指出存在潜在风险，建议仔细评估")
            
        if "不建议" in text_lower or "not recommended" in text_lower:
            recommendation["action"] = "review"
            
    except Exception as e:
        recommendation = {
            "action": "proceed",
            "method": parsed.get("method"),
            "confidence": "low",
            "reasoning": [f"LLM 调用失败，使用基础规则 (错误：{str(e)[:100]})"],
            "alternative_methods": [],
            "fallback_used": True,
            "warnings": ["未启用 LLM 智能推荐，请自行评估"]
        }
    
    branch_path = "abort_no_data" if len(available_datasets) == 0 else "execute"
    if len(available_datasets) == 0:
        recommendation["action"] = "abort"
        recommendation["reasoning"].append("无可用数据集，无法执行定标")
    
    return {
        "recommendation": recommendation,
        "branch_path": branch_path,
        "logs": state["logs"] + [{"event": "recommendation_generated", "action": recommendation["action"]}],
    }


def data_discovery_node(state: AgentState) -> AgentState:
    try:
        from ..data_adapter.explorer import LocalDataExplorer
    except ImportError:
        from data_adapter.explorer import LocalDataExplorer
    import yaml

    parsed = state.get("parsed_task", {})
    if not parsed or not parsed.get("method"):
        return {"available_datasets": [], "logs": state["logs"] + [{"event": "skipped_discovery"}]}

    method = parsed.get("method")
    primary_sat = parsed.get("primary_sat", "S6A")
    aux_sat = parsed.get("aux_data_type", "JA3")
    start_date = parsed.get("start_date", "20230101")
    end_date = parsed.get("end_date", "20231231")

    # 从 configs/settings.yaml 读取数据路径（参数化）
    try:
        with open("configs/settings.yaml", "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        data_cfg = cfg.get("data", {})
        base_dir = data_cfg.get(method, data_cfg.get("base_dir", "data"))
    except Exception:
        base_dir = "data"

    explorer = LocalDataExplorer(base_dir)
    try:
        # 星间交叉需要两颗星的数据；自交叉只需要一颗
        if method == "star_cross":
            all_folders = explorer.discover_satellite_folders(date_range=(start_date, end_date))
            # 过滤出主星和辅星的目录
            target_sats = [primary_sat.upper(), aux_sat.upper()]
            datasets = [f for f in all_folders if f["sat_id"].upper() in target_sats]
        else:
            all_folders = explorer.discover_satellite_folders(
                sat_id=primary_sat,
                date_range=(start_date, end_date)
            )
            datasets = all_folders

        # 统计每个卫星文件夹的 NC 数量（供 LLM 决策）
        sat_stats = {}
        for f in all_folders:
            sat_stats[f["sat_id"]] = f["nc_count"]

        data_summary = {
            "primary_sat": primary_sat,
            "aux_sat": aux_sat,
            "satellite_stats": sat_stats,
            "total_files": sum(f["nc_count"] for f in all_folders),
            "matched_sats": [f["sat_id"] for f in datasets],
        }

    except Exception as e:
        return {
            "available_datasets": [],
            "selected_data": None,
            "metadata": {"next_step": None, "data_summary": {}},
            "logs": state["logs"] + [{"event": "discovery_error", "error": str(e)[:200]}],
        }

    return {
        "available_datasets": datasets,
        "selected_data": datasets[0] if datasets else None,
        "metadata": {"next_step": "match" if datasets else None, "data_summary": data_summary},
        "logs": state["logs"] + [{"event": "datasets_found", "count": len(datasets), "stats": sat_stats}],
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
    has_nc_files = isinstance(selected.get("nc_files"), list) and len(selected.get("nc_files", [])) > 0

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

    # 星间交叉/自交叉需要两颗星的数据目录
    aux_input_dir = None
    primary_input_dir = selected.get("path") or selected.get("input_dir") or ""
    
    if method in ("star_cross", "self_cross") and aux_type != "UNKNOWN":
        # 从可用数据集里找两颗星的目录
        available = state.get("available_datasets", [])
        for ds in available:
            if ds.get("sat_id", "").upper() == sat_id.upper():
                primary_input_dir = ds.get("path") or primary_input_dir
            elif ds.get("sat_id", "").upper() == aux_type.upper():
                aux_input_dir = ds.get("path") or aux_input_dir
        
        # 如果找不到，就用选中的那个（默认同目录）
        if not aux_input_dir:
            aux_input_dir = primary_input_dir

    cfg_kwargs = {
        "sat_id": sat_id,
        "aux_data_type": aux_type if aux_type != "UNKNOWN" else parsed.get("aux_data_type", ""),
        "start_date": parsed.get("start_date", "20230101"),
        "end_date": parsed.get("end_date", "20231231"),
        "output_dir": f"output_local_test/{method}_{retry_count}",
        "input_dir": primary_input_dir,
        "aux_input_dir": aux_input_dir or primary_input_dir,
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
    graph_builder.add_edge("data_discovery", "method_recommendation")

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

    graph_builder.add_edge("fallback", "result_summarizer")
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
