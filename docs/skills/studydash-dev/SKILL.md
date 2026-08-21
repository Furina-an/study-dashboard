---
name: studydash-dev
description: 在 StudyDash（E:\agent专用\study-dashboard）做全栈功能迭代：按 FastAPI 后端 + Vue 3 前端的既有分层、用户隔离与迁移约定改代码，跑测试与构建。只用于该仓库，其他项目不要用。
---

# StudyDash 全栈开发

StudyDash 是 FastAPI（SQLAlchemy + SQLite/PostgreSQL）+ Vue 3（Vite + Pinia + ECharts）的学习管理台，仓库位于 `E:\agent专用\study-dashboard`。新增功能必须保持账号数据隔离（全部按 `user_id` 过滤）。

## 后端改动顺序
1. 顺序固定：`backend/app/models.py` 建表/加列 → `backend/app/schemas.py` 加 Pydantic 模型 → `backend/app/routers/` 新增或修改路由 → `backend/app/main.py` 注册 `include_router`。
2. 新表直接由 `create_all` 自动创建（零迁移），新表 class 追加到 `models.py` 末尾即可；旧表补列用 `main.py` 的 `_ensure_column`（SQLite 缺列补列；PostgreSQL 用 `ADD COLUMN IF NOT EXISTS` + `ALTER COLUMN TYPE ... USING` 修类型；失败只警告、不阻塞启动）。
3. 所有查询带 `user_id == 当前用户.id`（`Depends(get_current_user)`），越权访问返回 404；新表要在 `User` 模型上加 relationship。
4. 新增的数据类型必须同步进 `backend/app/routers/backup.py` 的导出/导入（导出节、删除节、counts、导入节含 id 重映射），否则备份会丢数据。

## 前端改动顺序
1. 顺序固定：`frontend/src/api.js` 加请求方法 → `frontend/src/stores/` 加 Pinia store → `frontend/src/views/` 新建页面 → `frontend/src/router/index.js` 注册路由（`meta: { requiresAuth: true }`）→ `frontend/src/components/NavBar.vue` 加导航。
2. 首页功能区卡片：在 `frontend/src/views/DashboardView.vue` 的 `liveCards` 加项，同时把 key 加入 `backend/app/routers/settings.py` 的 `HUB_CARD_KEYS` 白名单（否则保存设置时会被过滤掉）。
3. 页面样式复用 `frontend/src/assets/main.css` 的设计 token（`.panel` `.btn` `.chip` `.tag` `.modal` `.form-row` 等），不要自造风格。

## 测试与构建
- 全量后端测试：`cd E:\agent专用\study-dashboard\backend; .\.venv\Scripts\python.exe -m pytest -q`（当前 155 个，全绿为准）。
- 新功能补测试：夹具用 `client` / `auth_headers` / `other_headers`（`backend/tests/conftest.py`）；AI 调用用 `monkeypatch.setattr("app.routers.<模块>.chat_completion", lambda *a, **k: "模拟回复")`；用户隔离用 `other_headers` 断言 404；备份新增表要补往返测试。
- 前端构建：`cd E:\agent专用\study-dashboard\frontend; npm.cmd run build`（需要提权），构建通过才算完成。

## 本机环境注意（重要，违反会反复踩坑）
- `apply_patch` 工具在本机被系统拦截（报 Access denied）→ 改文件用 Python 脚本：用 PowerShell here-string `@'...'@` 把补丁脚本写到 `$env:TEMP\xxx.py`，再 `python $env:TEMP\xxx.py`；脚本内 `Path.read_text(encoding='utf-8')` + 精确锚点 `replace` + `assert 锚点在`，写回 `write_text(encoding='utf-8')`。
- 含中文的路径不要内联传给 `python -c`（会乱码），一律写成脚本文件执行。
- 终端是 PowerShell：用 `Get-Content` / `Get-ChildItem` / `Select-Object`，不要用 bash 的 `echo` / `ls` / `head`。
- 系统 python 只能做 `ast.parse` 语法校验；跑测试必须用 `backend\.venv` 的 python（系统 python 没有 fastapi）。

## 提交
- 本地提交 `git add -A && git commit -m "feat:/fix: 中文说明"`，不要建分支；发布上线见 `$studydash-deploy`。
