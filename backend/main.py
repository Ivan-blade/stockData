"""stockData API 入口 — 内置定时调度，程序内闭环"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from config import API_PORT
from routers.api import router as api_router
from scheduler import init_scheduler, stop_scheduler, get_scheduler_status

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

app = FastAPI(
    title="QuickView API",
    description="stockData - 轻量股票数据分析系统",
    version="0.1.0",
)

# CORS — 允许前端跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(api_router)


@app.on_event("startup")
def startup():
    """应用启动时初始化定时调度"""
    init_scheduler()


@app.on_event("shutdown")
def shutdown():
    """应用关闭时停止调度"""
    stop_scheduler()


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/scheduler/status")
def scheduler_status():
    """获取定时任务状态"""
    return get_scheduler_status()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=API_PORT, reload=True)
