# app/schemas.py

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Position(BaseModel):
    """节点在画布中的位置。"""

    model_config = ConfigDict(extra="forbid")

    x: float
    y: float


class NodeData(BaseModel):
    """节点展示信息和业务配置。"""

    model_config = ConfigDict(extra="allow")

    label: str = Field(min_length=1, max_length=100)


class WorkflowNode(BaseModel):
    """工作流中的一个节点。"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    type: str = Field(min_length=1, max_length=100)
    position: Position
    data: NodeData


class WorkflowEdge(BaseModel):
    """节点之间的一条有向连线。"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    source: str = Field(min_length=1, max_length=128)
    target: str = Field(min_length=1, max_length=128)

    sourceHandle: str | None = None
    targetHandle: str | None = None


class Workflow(BaseModel):
    """平台自己的工作流数据协议。"""

    model_config = ConfigDict(extra="forbid")

    schemaVersion: int = Field(ge=1, le=1)
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=200)

    nodes: list[WorkflowNode] = Field(max_length=500)
    edges: list[WorkflowEdge] = Field(max_length=1000)