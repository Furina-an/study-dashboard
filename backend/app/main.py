import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .database import Base, SessionLocal, engine
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
    questions,
    quiz,
    reviews,
    sessions,
    settings,
    stats,
    tasks,
    tutor,
)

Base.metadata.create_all(bind=engine)


def _ensure_column(table: str, column: str, pg_default: str) -> None:
    """幂等补列/修列：兼容 SQLite 与 PostgreSQL 旧库。

    - PostgreSQL：ADD COLUMN IF NOT EXISTS（列已存在不报错）后再把列类型
      统一修正为 BOOLEAN（部分旧库该列可能是 INTEGER，写入会失败）。
    - SQLite：检查缺列后 ALTER 补列。
    - 任何迁移失败只打印警告，不阻塞服务启动，避免整站离线。
    """
    from sqlalchemy import inspect, text

    try:
        inspector = inspect(engine)
        if table not in inspector.get_table_names():
            return
        backend = engine.url.get_backend_name()
        if backend == "postgresql":
            with engine.begin() as conn:
                conn.execute(
                    text(
                        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "
                        f"{column} BOOLEAN DEFAULT {pg_default}"
                    )
                )
                conn.execute(
                    text(
                        f"ALTER TABLE {table} ALTER COLUMN {column} "
                        "TYPE BOOLEAN USING " + f"({column}::boolean)"
                    )
                )
        else:
            columns = {col["name"] for col in inspector.get_columns(table)}
            if column not in columns:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            f"ALTER TABLE {table} ADD COLUMN "
                            f"{column} BOOLEAN DEFAULT {pg_default}"
                        )
                    )
        print(f"已确保 {table}.{column}")
    except Exception as exc:  # noqa: BLE001 - 迁移失败不阻塞启动
        print(f"补列 {table}.{column} 失败（已跳过，不影响启动）：{exc}")


# 旧库迁移：users.is_active（封号能力）、study_files.is_recommended（推荐分享）
_ensure_column("users", "is_active", "true")
_ensure_column("study_files", "is_recommended", "false")
storage.ensure_dirs()

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
app.include_router(questions.router)
app.include_router(quiz.router)
app.include_router(tutor.router)
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
