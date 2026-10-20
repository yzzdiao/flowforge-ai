# app/validator.py

from collections import defaultdict, deque

from app.schemas import Workflow


def validate_workflow(workflow: Workflow) -> list[str]:
    """
    校验工作流的图结构。

    返回错误列表：
    - 空列表表示结构校验通过。
    - 非空列表表示发现的问题。
    """

    errors: list[str] = []

    # 1. 检查节点 ID 是否重复。
    node_ids = [node.id for node in workflow.nodes]
    node_id_set = set(node_ids)

    if len(node_ids) != len(node_id_set):
        errors.append("节点 ID 不能重复")

    # 后续的图算法依赖唯一节点 ID。
    if errors:
        return errors

    # 2. 为每个节点初始化入度和邻接表。
    indegree = {node_id: 0 for node_id in node_id_set}
    graph: dict[str, list[str]] = defaultdict(list)

    edge_ids: set[str] = set()

    for edge in workflow.edges:
        # 3. 检查连线 ID 是否重复。
        if edge.id in edge_ids:
            errors.append(f"连线 ID 重复：{edge.id}")
            continue

        edge_ids.add(edge.id)

        # 4. 检查连线两端是否存在。
        if edge.source not in node_id_set:
            errors.append(
                f"连线 {edge.id} 的 source 节点不存在：{edge.source}"
            )
            continue

        if edge.target not in node_id_set:
            errors.append(
                f"连线 {edge.id} 的 target 节点不存在：{edge.target}"
            )
            continue

        # 5. 建立有向图，并统计目标节点的入度。
        graph[edge.source].append(edge.target)
        indegree[edge.target] += 1

    if errors:
        return errors

    # 6. Kahn 拓扑排序：
    # 入度为 0 的节点可以先处理。
    queue = deque(
        node_id
        for node_id, degree in indegree.items()
        if degree == 0
    )

    visited_count = 0

    while queue:
        current = queue.popleft()
        visited_count += 1

        for neighbor in graph[current]:
            indegree[neighbor] -= 1

            if indegree[neighbor] == 0:
                queue.append(neighbor)

    # 7. 如果没有处理完全部节点，说明图中存在环路。
    if visited_count != len(node_id_set):
        errors.append("工作流存在环路，当前版本不支持循环执行")

    return errors