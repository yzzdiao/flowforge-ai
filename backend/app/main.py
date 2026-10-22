# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.schemas import Workflow
from app.validator import validate_workflow
from app.engine import run_workflow
from app.schemas import Workflow


app = FastAPI(
    title="FlowForge AI API",
    version="0.1.0",
    description="可视化 AI 工作流平台后端",
)

# 开发阶段允许本地 Vite 前端跨域访问。
# 正式部署时必须改为明确的前端域名。
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/health")
def health_check():
    """检查服务是否正常运行。"""
    return {
        "status": "ok",
        "service": "flowforge-ai-api",
    }


@app.post("/api/workflows/validate")
def validate_workflow_api(payload: dict):
    """
    接收前端工作流 JSON，检查数据格式和图结构。

    本接口仅负责校验，不会执行工作流。
    """

    try:
        workflow = Workflow.model_validate(payload)
    except ValidationError as exc:
        return {
            "valid": False,
            "stage": "schema",
            "errors": exc.errors(include_url=False),
        }

    errors = validate_workflow(workflow)

    if errors:
        return {
            "valid": False,
            "stage": "graph",
            "errors": errors,
        }

    return {
        "valid": True,
        "workflow_id": workflow.id,
        "node_count": len(workflow.nodes),
        "edge_count": len(workflow.edges),
        "message": "工作流结构校验通过",
    }
@app.post("/api/workflows/run")
def run_workflow_api(workflow: Workflow):
    """同步执行一个工作流。"""
    try:
        return run_workflow(workflow)
    except ValueError as exc:
        return {
            "run_id": None,
            "status": "failed",
            "node_results": {},
            "final_output": None,
            "error": str(exc),
        }