"""
FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .routes import router

app = FastAPI(
    title="多Agent医疗临床辅助决策系统",
    description=(
        "企业级多Agent医疗临床辅助决策系统。"
        "5个专业Agent通过LangGraph管线协作：接诊、诊断、治疗、编码、审计。"
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

# 前端静态文件
static_dir = Path(__file__).parent.parent.parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "clinical-decision-system", "version": "2.0.0"}
