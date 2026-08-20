import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .database import Base, SessionLocal, engine
from .math_data import seed_math_if_empty
from . import storage
from .routers import (
    admin,
    ai,
    auth,
    backup,
    files,
    habits,
    math,
    plan_templates,
    plans,
    reviews,
    sessions,
    settings,
    stats,
    tasks,
)

Base.metadata.create_all(bind=engine)


def _ensure_users_is_active() -> None:
    """幂等补列：老库 users 表缺 is_active 时补上（新库由 create_all 创建）。"""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("users")}
    if "is_active" not in columns:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1")
            )


_ensure_users_is_active()
storage.ensure_dirs()

# 启动时幂等装载高数提纲内容（全局只读数据）
with SessionLocal() as _seed_db:
    seed_math_if_empty(_seed_db)

app = FastAPI(title="StudyDash API", version="0.1.0")


def _allowed_origins() -> list[str]:
    """默认允许本地开发；部署时通过 ALLOWED_ORIGINS 逗号分隔配置。"""
    configured = os.getenv("ALLOWED_ORIGINS", "")
    if configured.strip():
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router)
app.include_router(ai.router)
app.include_router(auth.router)
app.include_router(backup.router)
app.include_router(files.router)
app.include_router(plan_templates.router)
app.include_router(settings.router)
app.include_router(math.router)
app.include_router(habits.router)
app.include_router(reviews.router)
app.include_router(plans.router)
app.include_router(tasks.router)
app.include_router(sessions.router)
app.include_router(stats.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

_INFO_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>StudyDash</title>
  <style>
    body { font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; padding: 48px; color: #1f2430; }
    h1 { color: #4f6ef7; }
    a { color: #3d55d6; }
  </style>
</head>
<body>
  <h1>StudyDash 后端已启动 ✅</h1>
  <p>前端页面尚未构建。两种打开方式：</p>
  <ul>
    <li>开发模式：在 <code>frontend</code> 目录运行 <code>npm.cmd run dev</code>，然后访问 <a href="http://localhost:5173">http://localhost:5173</a></li>
    <li>构建预览：在 <code>frontend</code> 目录运行 <code>npm.cmd run build</code>，再刷新本页即可看到应用</li>
  </ul>
  <p>API 文档：<a href="/docs">/docs</a></p>
</body>
</html>
"""

if FRONTEND_DIST.exists():
    # 静态资源与前端页面（含 SPA 路由回退，刷新子页面不 404）
    app.mount(
        "/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets"
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        root = FRONTEND_DIST.resolve()
        candidate = (FRONTEND_DIST / full_path).resolve()
        if (
            full_path
            and candidate.is_file()
            and str(candidate).startswith(str(root))
        ):
            return FileResponse(candidate)
        return FileResponse(root / "index.html")
else:
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index():
        return HTMLResponse(_INFO_PAGE)
