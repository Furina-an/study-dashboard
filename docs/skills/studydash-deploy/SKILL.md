---
name: studydash-deploy
description: 把 StudyDash 改动发布上线并验证：推送 GitHub 触发 Render 自动部署，轮询 openapi.json 确认新路由上线，检查受保护接口返回 401。只用于 studydash 仓库。
---

# StudyDash 发布上线

仓库 `github.com/Furina-an/study-dashboard`（main 分支）；线上是 Render Web Service `studydash-api`，`https://study-dashboard-api-zs60.onrender.com`，push 到 main 后自动部署。

## 发布步骤
1. 本地 `git add -A && git commit -m "feat:/fix: 中文说明"`，然后 `git push origin main`（push 需要提权）。
2. 等待自动部署：Render 免费版构建排队，通常 4–10 分钟，最慢可达 25 分钟；没立即上线是正常的，先轮询再判断失败。

## 验证是否上线
- 轮询 `https://study-dashboard-api-zs60.onrender.com/openapi.json` 是否已包含本次新增路由（`-match '/api/xxx'`）。
- 受保护接口不带 token 应返回 `401 {"detail":"请先登录"}`；若返回 SPA 的 `index.html`（`<!doctype html>`），说明仍是旧版，继续等。
- 健康检查 `https://study-dashboard-api-zs60.onrender.com/api/health` 应返回 200 `{"status":"ok"}`。
- Render 不会在 GitHub 写部署状态，只能通过 openapi/接口行为判断；长时间不更新时让用户在 Render 控制台看部署日志或点「Manual Deploy」。

## 线上环境与数据库
- 环境变量在 Render 后台配置（新增依赖时提醒用户）：`SECRET_KEY`、`INVITE_CODE`、`ADMIN_USERNAMES`、`DATABASE_URL`、`ALLOWED_ORIGINS`；AI 相关 `LLM_API_BASE`、`LLM_MODEL`、`LLM_API_KEY`；查杀预留 `SCAN_COMMAND`。
- 线上用 PostgreSQL：新表由启动时 `create_all` 自动建；旧表列类型不匹配由 `_ensure_column` 自动修正（如 integer→boolean），迁移失败只警告、不阻塞启动。
- AI 助教「免费（管理员共享）」模式依赖服务端 `LLM_API_KEY`；未配置时前端自动禁用该选项。
