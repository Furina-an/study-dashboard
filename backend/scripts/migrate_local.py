"""迁移旧版本地 SQLite 库：补账号、计划、习惯、复习相关字段。

用法（在 backend 目录执行）：
    .venv/Scripts/python.exe scripts/migrate_local.py --username admin --password 你的密码

说明：新表（task_checkins / reviews 等）由启动时 create_all 自动创建，
本脚本只负责给旧表补列、创建引导账号并回填 user_id，可重复执行。
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, select, text

from app.database import Base, SessionLocal, engine
from app.models import User
from app.security import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description="迁移旧版本地数据库")
    parser.add_argument("--username", default="admin", help="引导账号用户名")
    parser.add_argument("--password", default="admin123", help="引导账号密码")
    args = parser.parse_args()

    # 幂等：创建所有缺失的表（users / plans / task_checkins / reviews / ...）
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    for table in ("tasks", "sessions"):
        columns = {col["name"] for col in inspector.get_columns(table)}
        if "user_id" not in columns:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER"))
            print(f"已为 {table} 添加 user_id 列")

    user_columns = {col["name"] for col in inspector.get_columns("users")}
    if "is_active" not in user_columns:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1")
            )
        print("已为 users 添加 is_active 列")

    if "study_files" in inspector.get_table_names():
        file_columns = {col["name"] for col in inspector.get_columns("study_files")}
        if "is_recommended" not in file_columns:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE study_files ADD COLUMN is_recommended BOOLEAN DEFAULT 0"
                    )
                )
            print("已为 study_files 添加 is_recommended 列")

    task_columns = {col["name"] for col in inspector.get_columns("tasks")}
    if "plan_id" not in task_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN plan_id INTEGER"))
        print("已为 tasks 添加 plan_id 列")
    if "is_habit" not in task_columns:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE tasks ADD COLUMN is_habit BOOLEAN DEFAULT 0")
            )
        print("已为 tasks 添加 is_habit 列")
    if "habit_frequency" not in task_columns:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE tasks ADD COLUMN habit_frequency VARCHAR(10) DEFAULT 'daily'"
                )
            )
        print("已为 tasks 添加 habit_frequency 列")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == args.username))
        if user is None:
            user = User(
                username=args.username,
                password_hash=hash_password(args.password),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"已创建引导账号：{args.username} / {args.password}")
        for table in ("tasks", "sessions"):
            db.execute(
                text(f"UPDATE {table} SET user_id = :uid WHERE user_id IS NULL"),
                {"uid": user.id},
            )
        db.commit()

    print("迁移完成。旧数据已归入引导账号，之后请用该账号登录使用。")


if __name__ == "__main__":
    main()
