import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..crypto import decrypt_secret
from ..llm import chat_completion, env_config, extract_error_message, parse_children_json
from ..models import AIConfig, Plan, PlanTemplate, Task, User
from ..schemas import (
    BreakdownRequest,
    BreakdownResult,
    PlanCreate,
    PlanOut,
    PlanUpdate,
)
from ..security import get_current_user
from .reviews import generate_reviews

router = APIRouter(prefix="/api/plans", tags=["plans"])

TEMPLATES: dict[str, dict] = {
    "study": {
        "label": "学习计划",
        "children": [
            ("预习资料", "收集并浏览相关教材、讲义与视频资料"),
            ("学习核心内容", "按章节系统学习重点知识"),
            ("练习巩固", "完成课后习题与专项练习"),
            ("复习总结", "整理笔记、归纳易错点"),
            ("测试检验", "做自测题检验掌握程度"),
        ],
    },
    "project": {
        "label": "项目计划",
        "children": [
            ("需求分析", "明确目标、范围与验收标准"),
            ("方案设计", "设计技术方案与模块划分"),
            ("开发实现", "按模块开发并逐步集成"),
            ("测试验收", "功能测试与问题修复"),
            ("部署上线", "部署发布并收集反馈"),
        ],
    },
    "exam": {
        "label": "备考计划",
        "children": [
            ("了解考纲", "梳理考试范围与分值分布"),
            ("分科复习", "按科目制定复习节奏"),
            ("真题练习", "限时完成历年真题"),
            ("查漏补缺", "针对薄弱点专项突破"),
            ("模拟考试", "全真模拟并复盘"),
        ],
    },
}


def _get_owned_plan(plan_id: int, user_id: int, db: Session) -> Plan:
    plan = db.scalar(
        select(Plan).where(Plan.id == plan_id, Plan.user_id == user_id)
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="计划不存在")
    return plan


def _is_descendant(db: Session, node_id: int, ancestor_id: int) -> bool:
    """判断 node_id 是否是 ancestor_id 的后代。"""
    current = node_id
    seen: set[int] = set()
    while current is not None and current not in seen:
        if current == ancestor_id:
            return True
        seen.add(current)
        row = db.execute(
            select(Plan.parent_id).where(Plan.id == current)
        ).first()
        current = row[0] if row else None
    return False


def _descendant_ids(db: Session, root_ids: list[int]) -> list[int]:
    """返回 root_ids 及其全部后代 id。"""
    all_ids: list[int] = list(root_ids)
    frontier = list(root_ids)
    while frontier:
        children = list(
            db.scalars(select(Plan.id).where(Plan.parent_id.in_(frontier))).all()
        )
        all_ids.extend(children)
        frontier = children
    return all_ids


@router.get("", response_model=list[PlanOut])
def list_plans(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(Plan).where(Plan.user_id == user.id).order_by(Plan.id)
    ).all()


@router.post("", response_model=PlanOut, status_code=201)
def create_plan(
    payload: PlanCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.parent_id is not None:
        _get_owned_plan(payload.parent_id, user.id, db)
    plan = Plan(**payload.model_dump(), user_id=user.id)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.patch("/{plan_id}", response_model=PlanOut)
def update_plan(
    plan_id: int,
    payload: PlanUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = _get_owned_plan(plan_id, user.id, db)
    changes = payload.model_dump(exclude_unset=True)
    new_parent = changes.get("parent_id")
    if new_parent is not None:
        if new_parent == plan.id:
            raise HTTPException(status_code=400, detail="不能把计划设为自己的子计划")
        _get_owned_plan(new_parent, user.id, db)
        if _is_descendant(db, new_parent, plan.id):
            raise HTTPException(status_code=400, detail="不能把计划移动到自己的子计划下")
    became_done = changes.get("status") == "done" and plan.status != "done"
    for key, value in changes.items():
        setattr(plan, key, value)
    db.commit()
    db.refresh(plan)
    if became_done:
        generate_reviews(db, user.id, "plan", plan.id, datetime.now())
        db.commit()
    return plan


@router.delete("/{plan_id}", status_code=204)
def delete_plan(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_plan(plan_id, user.id, db)
    ids = _descendant_ids(db, [plan_id])
    db.execute(update(Task).where(Task.plan_id.in_(ids)).values(plan_id=None))
    db.execute(delete(Plan).where(Plan.id.in_(ids)))
    db.commit()


@router.post("/{plan_id}/breakdown", response_model=BreakdownResult)
def breakdown_plan(
    plan_id: int,
    payload: BreakdownRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = _get_owned_plan(plan_id, user.id, db)
    if payload.mode == "template":
        if payload.template_id is not None:
            tpl = db.scalar(
                select(PlanTemplate).where(
                    PlanTemplate.id == payload.template_id,
                    PlanTemplate.user_id == user.id,
                )
            )
            if tpl is None:
                raise HTTPException(status_code=404, detail="模板不存在")
            try:
                children = json.loads(tpl.children or "[]")
            except (TypeError, ValueError):
                children = []
        elif payload.template_key and payload.template_key in TEMPLATES:
            children = [
                {"title": title, "description": description}
                for title, description in TEMPLATES[payload.template_key]["children"]
            ]
        else:
            raise HTTPException(status_code=400, detail="请选择有效的模板")
    else:
        children = _ai_children(user.id, plan.title, plan.description, db)

    created: list[Plan] = []
    for child in children:
        item = Plan(
            user_id=user.id,
            parent_id=plan.id,
            title=child["title"],
            description=child.get("description", ""),
        )
        db.add(item)
        created.append(item)
    db.commit()
    for item in created:
        db.refresh(item)
    return BreakdownResult(created=created)


def _resolve_llm(user_id: int, db: Session) -> dict:
    """AI 配置优先级：当前用户已保存配置 > 服务器环境变量。未配置返回 None。"""
    config = db.scalar(select(AIConfig).where(AIConfig.user_id == user_id))
    if config is not None:
        api_key = decrypt_secret(config.api_key_encrypted)
        if api_key:
            return {
                "base_url": config.base_url.rstrip("/"),
                "model": config.model,
                "api_key": api_key,
            }
    env = env_config()
    if env["api_key"]:
        return env
    return None


def _ai_children(user_id: int, title: str, description: str, db: Session) -> list[dict]:
    resolved = _resolve_llm(user_id, db)
    if resolved is None:
        raise HTTPException(
            status_code=400,
            detail="尚未配置 AI 服务：请先在「AI 设置」中配置 API，或由服务器设置 LLM_API_KEY 环境变量",
        )

    prompt = (
        "请把下面的计划拆解成 3-6 个可执行、互相独立的小计划。\n"
        f"计划标题：{title}\n"
        f"计划描述：{description or '（无）'}\n"
        '只返回 JSON，格式：{"children":[{"title":"小计划标题","description":"一句话说明"}]}'
    )
    try:
        content = chat_completion(
            resolved["base_url"],
            resolved["model"],
            resolved["api_key"],
            [{"role": "user", "content": prompt}],
        )
    except Exception as exc:  # noqa: BLE001 - 统一转成用户可读错误
        raise HTTPException(status_code=502, detail=f"AI 调用失败：{extract_error_message(exc)}")

    children = parse_children_json(content)
    if not children:
        raise HTTPException(status_code=502, detail="AI 返回内容无法解析")
    return children
