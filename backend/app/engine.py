from collections import defaultdict, deque
from typing import Any
from uuid import uuid4

from app.executors import EXECUTORS
from app.schemas import Workflow


def topological_order(workflow: Workflow) -> list[str]:
    """校验图结构并返回拓扑执行顺序。"""
    nodes = {node.id: node for node in workflow.nodes}

    if len(nodes) != len(workflow.nodes):
        raise ValueError("工作流存在重复的节点 ID")

    node_ids = set(nodes)
    indegree = {node_id: 0 for node_id in node_ids}
    adjacency: dict[str, list[str]] = defaultdict(list)
    edge_ids: set[str] = set()

    for edge in workflow.edges:
        if edge.id in edge_ids:
            raise ValueError(f"存在重复的连线 ID: {edge.id}")
        edge_ids.add(edge.id)

        if edge.source not in node_ids or edge.target not in node_ids:
            raise ValueError(f"连线 {edge.id} 引用了不存在的节点")

        adjacency[edge.source].append(edge.target)
        indegree[edge.target] += 1

    queue = deque(
        node_id
        for node_id, degree in indegree.items()
        if degree == 0
    )
    order: list[str] = []

    while queue:
        node_id = queue.popleft()
        order.append(node_id)

        for target_id in adjacency[node_id]:
            indegree[target_id] -= 1
            if indegree[target_id] == 0:
                queue.append(target_id)

    if len(order) != len(nodes):
        raise ValueError("工作流存在环路，无法按 DAG 执行")

    return order


def run_workflow(workflow: Workflow) -> dict[str, Any]:
    """按拓扑顺序执行工作流，并记录各节点的输入与输出。"""
    order = topological_order(workflow)
    nodes = {node.id: node for node in workflow.nodes}

    incoming_edges: dict[str, list[Any]] = defaultdict(list)
    for edge in workflow.edges:
        incoming_edges[edge.target].append(edge)

    outputs_by_node: dict[str, dict[str, Any]] = {}
    node_results: dict[str, dict[str, Any]] = {}
    final_output: Any = None
    run_id = str(uuid4())

    for node_id in order:
        node = nodes[node_id]
        node_type = node.type
        executor = EXECUTORS.get(node_type)

        if executor is None:
            node_results[node_id] = {
                "status": "failed",
                "error": f"不支持的节点类型: {node_type}",
            }
            return {
                "run_id": run_id,
                "status": "failed",
                "node_results": node_results,
                "final_output": None,
            }

        # 收集所有上游节点传入的数据。
        inputs: dict[str, Any] = {}
        for edge in incoming_edges[node_id]:
            source_outputs = outputs_by_node.get(edge.source, {})
            source_handle = edge.sourceHandle or "text"
            target_handle = edge.targetHandle or "text"

            if source_handle not in source_outputs:
                node_results[node_id] = {
                    "status": "failed",
                    "error": (
                        f"上游节点 {edge.source} "
                        f"没有输出端口 {source_handle}"
                    ),
                }
                return {
                    "run_id": run_id,
                    "status": "failed",
                    "node_results": node_results,
                    "final_output": None,
                }

            if target_handle in inputs:
                node_results[node_id] = {
                    "status": "failed",
                    "error": f"输入端口 {target_handle} 收到多个值",
                }
                return {
                    "run_id": run_id,
                    "status": "failed",
                    "node_results": node_results,
                    "final_output": None,
                }

            inputs[target_handle] = source_outputs[source_handle]

        # 将 Pydantic 节点配置转换为普通字典。
        config = node.data.model_dump()

        try:
            outputs = executor(config, inputs)
            outputs_by_node[node_id] = outputs
            node_results[node_id] = {
                "status": "success",
                "inputs": inputs,
                "outputs": outputs,
            }

            if node_type == "output":
                final_output = outputs.get("value")

        except Exception as exc:
            node_results[node_id] = {
                "status": "failed",
                "inputs": inputs,
                "error": str(exc),
            }
            return {
                "run_id": run_id,
                "status": "failed",
                "node_results": node_results,
                "final_output": None,
            }

    return {
        "run_id": run_id,
        "status": "success",
        "node_results": node_results,
        "final_output": final_output,
    }