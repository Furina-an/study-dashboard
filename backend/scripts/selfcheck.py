"""StudyDash 环境自检：排查「后端未启动」类问题。

用法（项目根目录或 backend 目录下）：
    .venv\\Scripts\\python.exe scripts\\selfcheck.py

会检查：Python 版本、依赖、数据库、上传目录、前端产物、端口占用，并给出修复建议。
"""

import importlib
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
REQUIRED = [
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "pydantic",
    "bcrypt",
    "jwt",
    "cryptography",
    "psycopg",
]


def check(ok: bool, message: str, hint: str = "") -> bool:
    flag = "PASS" if ok else "FAIL"
    print(f"[{flag}] {message}")
    if not ok and hint:
        print(f"       -> {hint}")
    return ok


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def main() -> int:
    print("=" * 52)
    print("StudyDash 环境自检")
    print(f"项目目录: {ROOT}")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    print("=" * 52)

    all_ok = True

    all_ok &= check(
        (3, 10) <= sys.version_info[:3],
        "Python 版本 >= 3.10",
        "请安装 Python 3.11/3.12 后重建 backend/.venv",
    )

    missing = []
    for name in REQUIRED:
        try:
            importlib.import_module(name)
        except ImportError:
            missing.append(name)
    all_ok &= check(
        not missing,
        "依赖完整" if not missing else f"缺少依赖: {', '.join(missing)}",
        "运行: cd backend && .venv\\Scripts\\python.exe -m pip install -r requirements.txt",
    )

    # 数据库
    import os

    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        all_ok &= check(True, f"数据库: 使用 DATABASE_URL（{db_url.split('@')[-1][:40]}）")
    else:
        db_path = ROOT / "study.db"
        writable = True
        try:
            with open(db_path, "a"):
                pass
        except OSError:
            writable = False
        all_ok &= check(
            writable,
            f"SQLite 数据库可写（{db_path}）",
            "请确认 backend 目录有写入权限",
        )

    # 上传目录
    try:
        from app import storage

        storage.ensure_dirs()
        all_ok &= check(True, f"上传目录已就绪（{storage.upload_root()}）")
    except Exception as exc:  # noqa: BLE001
        all_ok &= check(False, f"上传目录初始化失败: {exc}", "检查 backend/uploads 权限")

    # 后端可导入
    try:
        from app.main import app

        all_ok &= check(True, f"FastAPI 应用可导入（路由 {len(app.routes)} 条）")
    except Exception as exc:  # noqa: BLE001
        all_ok &= check(False, f"FastAPI 应用导入失败: {exc}", "修复 import 错误后重试")

    # 前端产物
    dist = ROOT.parent / "frontend" / "dist" / "index.html"
    all_ok &= check(
        dist.exists(),
        "前端页面已构建（frontend/dist/index.html）",
        "运行: cd frontend && npm.cmd run build",
    )

    # 端口
    port = int(os.getenv("PORT", "8000") or "8000")
    all_ok &= check(
        not port_in_use(port),
        f"端口 {port} 未被占用",
        f"端口被占用：换个端口（set PORT=8123）或关闭占用进程",
    )

    print("=" * 52)
    if all_ok:
        print("全部检查通过，可以启动：start.bat（或后端-only 用 启动后端.bat）")
        return 0
    print("存在问题，请按上面 FAIL 项的提示修复后重试。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
