"""高数复习种子数据装载（幂等）。

数据来源：输出/高数复习/高数复习提纲_优化版.html 解析出的结构化 JSON。
chapters/items 为全局只读内容；进度与笔记按用户隔离。
"""
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import MathChapter, MathItem

_SEED_PATH = Path(__file__).resolve().parent / "math_seed_data.json"


def load_seed() -> dict:
    with open(_SEED_PATH, encoding="utf-8") as f:
        return json.load(f)


def seed_math_if_empty(db: Session) -> bool:
    """math_chapters 为空时导入高数提纲数据；可重复执行（幂等）。"""
    if db.scalar(select(MathChapter.id).limit(1)) is not None:
        return False

    data = load_seed()
    for ci, chapter in enumerate(data["chapters"]):
        row = MathChapter(
            chapter_key=chapter["chapter_key"],
            num=chapter["num"],
            title=chapter["title"],
            short=chapter["short"],
            note_label=chapter.get("note_label", ""),
            note_placeholder=chapter.get("note_placeholder", ""),
            sort_order=ci,
        )
        db.add(row)
        db.flush()
        sort_order = 0
        for sub in chapter["subs"]:
            for item in sub["items"]:
                db.add(
                    MathItem(
                        chapter_id=row.id,
                        item_key=item["item_key"],
                        sub_title=sub["sub_title"],
                        tag=item.get("tag") or sub.get("tag") or "",
                        sort_order=sort_order,
                        segments=json.dumps(item["segments"], ensure_ascii=False),
                    )
                )
                sort_order += 1
    db.commit()
    return True
