from collections.abc import Callable
from typing import Any


NodeConfig = dict[str, Any]
NodeInputs = dict[str, Any]
NodeOutputs = dict[str, Any]

Executor = Callable[[NodeConfig, NodeInputs], NodeOutputs]


def execute_text_input(
    config: NodeConfig,
    inputs: NodeInputs,
) -> NodeOutputs:
    """读取输入节点配置中的文本。"""
    text = config.get("text")

    if not isinstance(text, str):
        raise ValueError("Text Input 节点必须配置 text 字符串")

    return {"text": text}


def execute_text_uppercase(
    config: NodeConfig,
    inputs: NodeInputs,
) -> NodeOutputs:
    """读取上游文本，并转换成大写。"""
    text = inputs.get("text")

    if not isinstance(text, str):
        raise ValueError("Text Uppercase 节点需要一个 text 字符串输入")

    return {"text": text.upper()}


def execute_output(
    config: NodeConfig,
    inputs: NodeInputs,
) -> NodeOutputs:
    """收集最终输出。"""
    if "text" not in inputs:
        raise ValueError("Output 节点缺少 text 输入")

    return {"value": inputs["text"]}


# 节点注册表：业务节点类型 -> 执行器函数
EXECUTORS: dict[str, Executor] = {
    "text_input": execute_text_input,
    "text_uppercase": execute_text_uppercase,
    "output": execute_output,
}