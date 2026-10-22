
"""
FlowForge AI - 工作流执行引擎

本文件负责：
1. 检查工作流中的节点和连线是否合法。
2. 使用拓扑排序确定节点的执行顺序。
3. 根据连线将上游节点的输出传递给下游节点。
4. 从 executors.py 中找到对应的执行器并执行。
5. 保存节点执行记录，返回整个工作流的运行结果。

重要区别：
- engine.py：负责调度、数据传递、结果记录。
- executors.py：负责每种节点的具体业务逻辑。
"""

from collections import defaultdict, deque
from typing import Any
from uuid import uuid4

# 导入节点执行器注册表。
#
# EXECUTORS 是一个字典，例如：
# {
#     "text_input": execute_text_input,
#     "text_uppercase": execute_text_uppercase,
#     "output": execute_output,
# }
#
# 通过节点类型，就可以查到对应的 Python 函数。
from app.executors import EXECUTORS

# Workflow 是 Pydantic 定义的工作流数据模型。
# FastAPI 接收 JSON 后，会将合法数据转换成 Workflow 对象。
from app.schemas import Workflow


def topological_order(workflow: Workflow) -> list[str]:
    """
    检查工作流的节点和连线，并返回合法的拓扑执行顺序。

    举例：
        node_1 -> node_2 -> node_3

    返回：
        ["node_1", "node_2", "node_3"]

    为什么需要拓扑排序？
    因为 node_2 需要 node_1 的输出，
    所以必须先执行 node_1，再执行 node_2。

    本函数使用 Kahn 算法，时间复杂度为 O(V + E)：
    V 是节点数量，E 是连线数量。
    """

    # 第一步：建立节点 ID 到节点对象的映射。
    #
    # 原始数据是一个列表：
    # [node_1, node_2, node_3]
    #
    # 转换后可以通过 ID 快速查找节点：
    # {
    #     "node_1": Node对象,
    #     "node_2": Node对象,
    #     "node_3": Node对象,
    # }
    nodes = {node.id: node for node in workflow.nodes}

    # 如果字典中的节点数量小于原始列表长度，
    # 说明至少有两个节点使用了相同的 ID。
    #
    # 注意：字典会覆盖重复的 key，
    # 所以必须在转换后检查数量是否一致。
    if len(nodes) != len(workflow.nodes):
        raise ValueError("工作流存在重复的节点 ID")

    # 保存所有合法节点 ID，后面用于检查连线。
    node_ids = set(nodes)

    # indegree 用来记录每个节点有多少条入边。
    #
    # 入边就是指向当前节点的连线。
    #
    # 例如：
    # node_1 -> node_2 -> node_3
    #
    # node_1 的入度为 0
    # node_2 的入度为 1
    # node_3 的入度为 1
    #
    # 初始时，所有节点的入度都设置为 0。
    indegree = {
        node_id: 0
        for node_id in node_ids
    }

    # adjacency 保存每个节点指向哪些下游节点。
    #
    # 例如：
    # node_1 -> node_2
    # node_1 -> node_3
    #
    # 对应：
    # adjacency["node_1"] = ["node_2", "node_3"]
    #
    # defaultdict(list) 的好处是：
    # 第一次访问某个不存在的 key 时，
    # 会自动创建一个空列表。
    adjacency: dict[str, list[str]] = defaultdict(list)

    # 保存已经出现过的连线 ID，
    # 用来检查连线 ID 是否重复。
    edge_ids: set[str] = set()

    # 第二步：检查每一条连线。
    for edge in workflow.edges:

        # 检查连线 ID 是否重复。
        if edge.id in edge_ids:
            raise ValueError(
                f"存在重复的连线 ID: {edge.id}"
            )

        # 将当前连线 ID 记录下来。
        edge_ids.add(edge.id)

        # 检查连线的起点和终点是否真实存在。
        #
        # source：起点节点 ID
        # target：终点节点 ID
        #
        # 如果连接到了不存在的节点，
        # 就不能继续执行工作流。
        if (
            edge.source not in node_ids
            or edge.target not in node_ids
        ):
            raise ValueError(
                f"连线 {edge.id} 引用了不存在的节点"
            )

        # 将这条连线记录到邻接表中。
        #
        # 例如：
        # source = "node_1"
        # target = "node_2"
        #
        # 等价于：
        # adjacency["node_1"].append("node_2")
        adjacency[edge.source].append(edge.target)

        # 目标节点的入度加 1。
        #
        # 因为多了一条指向 target 的连线，
        # 所以 target 需要等待更多的上游依赖。
        indegree[edge.target] += 1

    # 第三步：把所有入度为 0 的节点放入队列。
    #
    # 入度为 0 表示没有上游依赖，
    # 因此这些节点可以先执行。
    #
    # deque 是双端队列，适合使用 popleft()
    # 高效地取出队列头部元素。
    queue = deque(
        node_id
        for node_id, degree in indegree.items()
        if degree == 0
    )

    # order 用于保存最终的执行顺序。
    order: list[str] = []

    # 第四步：执行 Kahn 拓扑排序。
    while queue:

        # 取出一个当前可以执行的节点。
        node_id = queue.popleft()

        # 将这个节点加入执行顺序。
        order.append(node_id)

        # 遍历当前节点的所有下游节点。
        for target_id in adjacency[node_id]:

            # 当前节点已经被处理，
            # 相当于下游节点少了一个尚未处理的依赖。
            indegree[target_id] -= 1

            # 如果下游节点的入度变成 0，
            # 表示它的所有上游依赖都已经处理完毕。
            #
            # 因此可以把它放入队列，等待执行。
            if indegree[target_id] == 0:
                queue.append(target_id)

    # 如果最终排序出来的节点数量
    # 不等于原始节点数量，就说明存在环路。
    #
    # 例如：
    # node_1 -> node_2 -> node_3 -> node_1
    #
    # 这些节点会互相等待，无法全部进入执行顺序。
    if len(order) != len(nodes):
        raise ValueError(
            "工作流存在环路，无法按 DAG 执行"
        )

    # 返回合法的节点执行顺序。
    return order


def run_workflow(workflow: Workflow) -> dict[str, Any]:
    """
    执行一个完整的工作流。

    参数：
        workflow：
            经过 Pydantic 校验的工作流对象。

    返回：
        包含运行 ID、运行状态、各节点结果和最终输出的字典。
    """

    # 第一步：获取拓扑排序。
    #
    # 如果工作流存在重复 ID、非法连线或环路，
    # topological_order 会抛出 ValueError，
    # 当前函数就不会开始执行节点。
    order = topological_order(workflow)

    # 建立节点 ID 到节点对象的映射。
    # 这样后续就可以通过 node_id 快速查找节点。
    nodes = {
        node.id: node
        for node in workflow.nodes
    }

    # incoming_edges 用来保存每个节点的所有入边。
    #
    # 例如：
    # node_1 -> node_3
    # node_2 -> node_3
    #
    # 那么：
    # incoming_edges["node_3"] = [edge_1, edge_2]
    #
    # 为什么需要它？
    # 因为执行 node_3 时，
    # 需要收集 node_1 和 node_2 的输出。
    incoming_edges: dict[str, list[Any]] = defaultdict(list)

    # 遍历所有连线，将它们按目标节点分组。
    for edge in workflow.edges:
        incoming_edges[edge.target].append(edge)

    # 保存每个节点执行成功后产生的输出。
    #
    # 例如：
    # {
    #     "node_1": {"text": "Hello AI"},
    #     "node_2": {"text": "HELLO AI"},
    # }
    #
    # 后续节点通过这个字典读取上游结果。
    outputs_by_node: dict[str, dict[str, Any]] = {}

    # 保存每个节点的执行状态、输入、输出或错误。
    #
    # 它与 outputs_by_node 的用途不同：
    # outputs_by_node 专门保存成功节点的输出，
    # node_results 保存更完整的执行记录。
    node_results: dict[str, dict[str, Any]] = {}

    # 用于保存最终输出节点的结果。
    # 如果工作流没有输出节点，此值将保持 None。
    final_output: Any = None

    # 为本次运行生成一个唯一 ID。
    # 当前版本只在内存中使用，还没有保存到数据库。
    run_id = str(uuid4())

    # 第二步：按照拓扑排序结果逐个执行节点。
    for node_id in order:

        # 根据 ID 找到当前节点对象。
        node = nodes[node_id]

        # 获取当前节点的业务类型。
        #
        # 例如：
        # "text_input"
        # "text_uppercase"
        # "output"
        node_type = node.type

        # 从注册表中找到对应的执行函数。
        executor = EXECUTORS.get(node_type)

        # 如果注册表中不存在这种节点类型，
        # 就不能知道该如何执行这个节点。
        if executor is None:

            # 记录失败原因。
            node_results[node_id] = {
                "status": "failed",
                "error": f"不支持的节点类型: {node_type}",
            }

            # 立即终止当前工作流，并返回失败结果。
            #
            # 注意：这里没有抛出异常，
            # 而是选择将失败状态作为正常 JSON 结果返回。
            return {
                "run_id": run_id,
                "status": "failed",
                "node_results": node_results,
                "final_output": None,
            }

        # 第三步：准备当前节点的输入。
        #
        # 初始为空字典。
        # 每条入边都可能为 inputs 添加一个字段。
        inputs: dict[str, Any] = {}

        # 获取所有指向当前节点的连线。
        for edge in incoming_edges[node_id]:

            # 找到这条连线的起点节点已经产生的输出。
            #
            # 例如：
            # edge.source = "node_1"
            #
            # source_outputs 可能是：
            # {"text": "Hello AI"}
            #
            # 如果上游没有可用的输出，
            # 这里会得到空字典。
            source_outputs = outputs_by_node.get(
                edge.source,
                {},
            )

            # sourceHandle 表示从上游节点的哪个输出端口取值。
            #
            # targetHandle 表示把值传到当前节点的哪个输入端口。
            #
            # 如果前端没有指定端口名称，
            # 这里暂时统一默认使用 "text"。
            source_handle = edge.sourceHandle or "text"
            target_handle = edge.targetHandle or "text"

            # 检查上游节点是否真的输出了指定端口。
            #
            # 例如：
            # source_outputs = {"text": "Hello AI"}
            # source_handle = "text"
            #
            # 这时就可以取出对应的值。
            if source_handle not in source_outputs:

                # 记录当前节点的失败原因。
                node_results[node_id] = {
                    "status": "failed",
                    "error": (
                        f"上游节点 {edge.source} "
                        f"没有输出端口 {source_handle}"
                    ),
                }

                # 终止工作流，并返回失败状态。
                return {
                    "run_id": run_id,
                    "status": "failed",
                    "node_results": node_results,
                    "final_output": None,
                }

            # 检查当前输入端口是否已经收到数据。
            #
            # 当前版本规定：
            # 同一个输入端口不能通过多条连线接收多个值。
            #
            # 如果允许多个值，就需要进一步设计
            # 列表输入、合并策略或聚合节点。
            if target_handle in inputs:

                node_results[node_id] = {
                    "status": "failed",
                    "error": (
                        f"输入端口 {target_handle} "
                        "收到多个值"
                    ),
                }

                return {
                    "run_id": run_id,
                    "status": "failed",
                    "node_results": node_results,
                    "final_output": None,
                }

            # 真正完成数据传递的语句。
            #
            # 例如：
            # source_outputs["text"] == "Hello AI"
            #
            # 那么：
            # inputs["text"] = "Hello AI"
            #
            # 注意：这是数据映射，不是在这里执行节点。
            inputs[target_handle] = source_outputs[source_handle]

        # 第四步：读取当前节点自己的配置。
        #
        # node.data 是 Pydantic 模型对象。
        # model_dump() 将其转换为普通 Python 字典。
        #
        # 例如：
        # {
        #     "label": "Text Input",
        #     "nodeType": "text_input",
        #     "text": "Hello AI"
        # }
        config = node.data.model_dump()

        try:
            # 第五步：调用当前节点的执行器。
            #
            # executor 是前面从 EXECUTORS 注册表
            # 中找到的函数。
            #
            # 对输入节点来说，相当于：
            # execute_text_input(config, inputs)
            #
            # 对大写节点来说，相当于：
            # execute_text_uppercase(config, inputs)
            #
            # 执行器返回的 outputs 是当前节点的输出字典。
            outputs = executor(config, inputs)

            # 保存当前节点的输出。
            #
            # 之后的下游节点会从这里读取数据。
            outputs_by_node[node_id] = outputs

            # 保存更完整的节点执行记录。
            node_results[node_id] = {
                "status": "success",
                "inputs": inputs,
                "outputs": outputs,
            }

            # 如果当前节点是最终输出节点，
            # 就从其 outputs 中读取 value。
            #
            # execute_output 返回：
            # {"value": "HELLO AI"}
            #
            # 因此最终结果就是 "HELLO AI"。
            if node_type == "output":
                final_output = outputs.get("value")

        except Exception as exc:
            # 如果执行器发生异常，例如：
            # - 输入类型错误
            # - 缺少必要配置
            # - 节点内部逻辑报错
            #
            # 就记录失败状态和错误信息。
            node_results[node_id] = {
                "status": "failed",
                "inputs": inputs,
                "error": str(exc),
            }

            # 当前版本遇到节点失败就终止整个工作流。
            return {
                "run_id": run_id,
                "status": "failed",
                "node_results": node_results,
                "final_output": None,
            }

    # 所有节点执行完毕后，返回最终结果。
    #
    # run_id：
    #     本次运行的唯一标识。
    #
    # status：
    #     整个工作流的状态。
    #
    # node_results：
    #     所有已执行节点的结果记录。
    #
    # final_output：
    #     最终输出节点产生的 value。
    return {
        "run_id": run_id,
        "status": "success",
        "node_results": node_results,
        "final_output": final_output,
    }
