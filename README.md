# StudyDash 学习管理台

一个用于练手全栈开发的学习管理台：番茄钟 + 任务管理 + 计划拆解 + 学习统计。

- 前端：Vue 3 + Vite + Vue Router + Pinia
- 后端：FastAPI + SQLAlchemy + SQLite
- 账号系统：邀请码注册 + JWT 登录，每个账号数据互相隔离；管理后台可批量生成/停用邀请码（限次、限时、备注）控制注册人数
- 计划系统：大计划无限层级拆成子计划（手动 / 模板 / AI 三种拆解），并自动生成可导出的流程图
- AI 服务接入：应用内配置 OpenAI 兼容 API（DeepSeek / 通义 / 智谱 / Kimi / 自定义），Key 加密存储、掩码回显、一键测试连接，每个账号使用自己的配置
- 习惯打卡：任务可标记为习惯，每天打卡、连续天数统计
- 复习提醒：任务/计划完成后自动生成艾宾浩斯 1/2/4/7/15/30 天复习节点
- 统计可视化：ECharts 专注热力图、30 天趋势、连续专注 streak
- UI：全新设计语言（靛蓝主色 + 卡片化 + 响应式），支持深色/浅色主题一键切换
- 个性化自定义：按账号保存外观（浅色/深色/跟随系统 + 5 色强调色）、番茄钟时长、复习间隔、习惯默认频率、任务默认分钟与科目库、首页功能卡片显隐排序、自定义计划模板，换设备自动同步
- 学习文件：用户上传学习资料（PDF / Office / Markdown / 图片），按账号隔离存储（扩展名白名单 + 文件头校验 + 大小限制），运营（管理员）可扫描查毒、放行、标记整合；杀毒接口预留（`SCAN_COMMAND`）
- 总站首页：功能区卡片门户，整合学习管理与高数复习，预留雅思 / 冲刺 / 报告等扩展位
- userstore 独立模块：每用户一个 JSON 主文件，独立快照备份（保留 10 份）+ 恢复，上传文件专属空间（UUID 命名 + manifest 索引 + 隔离区），纯标准库实现、可独立 `pytest` 测试，预留后续 FastAPI 接入
- 数据备份：一键导出 / 导入全部数据（任务、计划、专注、打卡、复习、个性化设置、计划模板、AI 配置、高数进度与笔记），换设备 / 换账号恢复
- 云端就绪：后端端口由环境变量 `PORT` 注入（Render / Docker / 单服务器通用），提供 `run.py` 统一入口与 `Dockerfile`
- 高数复习：高等数学（上）108 个考点结构化入库，KaTeX 公式渲染随前端打包（本地 / 云端均不依赖外部 CDN），支持搜索、标签筛选、进度追踪、章节笔记

## 目录结构

```text
study-dashboard/
├── backend/          # FastAPI 后端
│   ├── app/          # 应用代码（models / schemas / routers）
│   ├── tests/        # pytest 测试
│   ├── study.db      # SQLite 数据库（自动生成）
│   └── requirements.txt
├── frontend/         # Vue 3 前端
│   └── src/          # 页面、组件、状态管理
├── userstore/        # 独立用户信息储存系统（纯标准库，可独立 pytest）
├── docs/             # 过程文档（验收清单等）
└── README.md
```

## 快速开始

### 0. 一键启动（推荐）

双击项目根目录的 `start.bat`：自动检查/安装依赖 → 启动后端 → 自动打开浏览器访问 http://127.0.0.1:8000（前端页面由后端直接托管）。

- 首次运行会安装依赖（需要联网），之后每次双击直接打开网页。
- 若服务已经在运行，会跳过启动、直接打开网页，不会重复占用端口。
- 停止服务：直接关闭弹出的命令行窗口即可。
- 开发调试：在 `frontend` 目录执行 `npm.cmd run dev`，然后访问 http://localhost:5173（支持热更新）；改完代码后执行 `npm.cmd run build` 重新构建即可让 http://127.0.0.1:8000 生效。

### 1. 启动后端（端口 8000）

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

启动后可访问 http://127.0.0.1:8000/docs 查看自动生成的 API 文档。

### 2. 启动前端（端口 5173）

```powershell
cd frontend
npm install
npm run dev
```

浏览器打开 http://localhost:5173 即可使用。Vite 会把 `/api` 请求代理到后端 8000 端口。

首次使用先在「注册」页创建账号（本地默认邀请码：`studydash`，可用环境变量 `INVITE_CODE` 修改）。

> 如果你的本地库是账号系统之前的旧版本：先运行迁移脚本 `backend\.venv\Scripts\python.exe scripts\migrate_local.py --username admin --password 你的密码`（旧数据会归入该引导账号），或直接删除 `backend\study.db` 重新开始。


### 2.5 管理后台：邀请码生成器

注册成功后，用环境变量 `ADMIN_USERNAMES` 指定的管理员账号（默认 `admin`）登录，导航栏会出现「管理」入口：

- **概览**：当前注册人数、有效/未使用/累计邀请码数量。
- **生成邀请码**：一次生成 1-50 个；每个码可设「可用次数」（用完自动失效）、「有效天数」（留空=永久）、备注；生成后一键复制。
- **邀请码管理**：启用/停用、删除；已用尽的码自动标记。
- **用户列表**：查看全部注册用户与角色。

邀请码校验规则：`INVITE_CODE` 主码永远可用（用于管理员自己注册/应急）；数据库邀请码必须是「启用 + 未过期 + 未用完」才能注册成功，注册后消耗一次。
### 3. 运行后端测试

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -v
```

## API 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/tasks` | 任务列表 |
| POST | `/api/tasks` | 新建任务 |
| PATCH | `/api/tasks/{id}` | 更新任务（含状态切换） |
| DELETE | `/api/tasks/{id}` | 删除任务 |
| GET | `/api/ai/config` | 读取 AI 配置（Key 掩码返回） |
| PUT | `/api/ai/config` | 保存 AI 配置（Key 加密存储） |
| DELETE | `/api/ai/config` | 清除 AI 配置 |
| POST | `/api/ai/test` | 测试 AI 连接（可传临时参数） |
| POST | `/api/sessions` | 记录一次完成的专注 |
| GET | `/api/stats/today` | 今日统计 |
| GET | `/api/stats/trend?days=7` | 最近 N 天专注趋势 |
| POST | `/api/tasks/{id}/checkin` | 习惯任务打卡（幂等） |
| DELETE | `/api/tasks/{id}/checkin` | 撤销今日习惯打卡 |
| GET | `/api/habits` | 习惯列表（今日已打卡 / 连续天数 / 近 7 天） |
| GET | `/api/reviews?status=due` | 复习列表（due / upcoming / all） |
| POST | `/api/reviews/{id}/complete` | 标记复习完成 |
| POST | `/api/reviews/complete-due` | 一键完成到期复习 |
| GET | `/api/stats/heatmap?days=105` | 每日专注分钟（热力图数据） |
| GET | `/api/stats/streak` | 连续专注天数统计 |
| GET | `/api/settings` | 读取当前账号个性化设置 |
| PUT | `/api/settings` | 更新个性化设置（部分更新、字段校验） |
| GET | `/api/plan-templates` | 我的计划模板列表 |
| POST | `/api/plan-templates` | 新建计划模板 |
| PATCH | `/api/plan-templates/{id}` | 修改计划模板 |
| DELETE | `/api/plan-templates/{id}` | 删除计划模板 |
| GET | `/api/files` | 文件列表（本人；管理员可 `?scope=all` / `?user_id=`） |
| POST | `/api/files` | 上传文件（原始二进制 body + `filename/category/description` 查询参数） |
| GET | `/api/files/{id}/download` | 下载文件（本人或管理员；隔离文件仅管理员可下） |
| DELETE | `/api/files/{id}` | 删除文件（本人或管理员） |
| PATCH | `/api/files/{id}` | 管理员：改状态 / 整合标记 / 备注 |
| POST | `/api/files/{id}/scan` | 管理员：重新病毒扫描（查毒预留） |
| GET | `/api/math/tree` | 高数提纲树（章节 / 知识点 / 公式 / 个人进度与笔记） |
| PUT | `/api/math/items/{id}/progress` | 标记知识点「已掌握 / 未掌握」 |
| PUT | `/api/math/chapters/{id}/note` | 保存章节笔记 |
| DELETE | `/api/math/progress` | 清除当前账号全部掌握标记 |
| GET | `/api/backup/export` | 导出当前账号全部数据（JSON，不含 AI Key） |
| POST | `/api/backup/import` | 从备份 JSON 覆盖式恢复当前账号数据 |
| GET | `/api/health` | 健康检查（部署探活用） |

任务状态：todo（待办）、doing（进行中）、done（已完成）。任务标记为 done 时自动记录 completed_at，用于「今日完成任务」统计。

高数复习数据来自「高等数学（上）期末复习提纲」：7 章 / 21 小节 / 108 个考点。后端启动时自动把 `backend/app/math_seed_data.json` 幂等导入 `math_chapters` / `math_items`（内容全局只读），进度与笔记按账号存在 `math_progress` / `math_notes`，互不可见。

备份说明：`/api/backup/export` 导出的 JSON 包含任务、计划、专注记录、习惯打卡、复习节点、个性化设置、计划模板、AI 配置（不含 API Key）、高数进度与章节笔记；`/api/backup/import` 会【覆盖】当前账号全部数据，导入前请先导出备份。API Key 加密存储不随备份导出，恢复后需到「AI 设置」重新填写。

计划状态同上。计划树支持无限层级；「拆解」弹层可选内置模板（学习/项目/备考）或 AI 拆解；「流程图」标签页用 SVG 自绘树状图，可一键导出 SVG / PNG。

学习文件：上传后进入「待扫描」队列（`scan_status=pending`）；磁盘按用户分目录存在 `backend/uploads/files/{user_id}/`，文件名用 UUID 重命名，**不挂载静态目录、不通过 URL 直连**，下载一律走鉴权接口。管理员（`ADMIN_USERNAMES` 环境变量指定，默认 `admin`）可查看全部文件、重新扫描、放行 / 隔离 / 拒绝、标记「已整合」。文件不包含在 JSON 备份中（二进制数据，需直接备份 `backend/uploads/` 目录）。

## 学习文件（上传与运营整合）

「文件」页（首页功能卡片「学习文件」）：

- **上传**：选文件 → 填分类 / 描述 → 上传。支持扩展名白名单（pdf / doc / docx / ppt / pptx / xls / xlsx / csv / md / txt / png / jpg / jpeg / gif / webp），默认最大 20MB（`MAX_UPLOAD_MB` 可改）；上传时做文件头魔数校验，改后缀的脚本 / 可执行文件会被拒绝。
- **隔离**：病毒扫描命中或管理员手动隔离的文件移入 `backend/uploads/quarantine/`，本人也无法下载；管理员放行后自动移回用户目录。
- **查杀病毒预留**：后端读取 `SCAN_COMMAND`（如 `clamscan --no-summary`），配置后上传 / 重新扫描都会调用；未配置时 `scan_status` 保持 `pending`（待扫描），不影响上传与本人下载。
- **运营整合**：管理员在文件列表可「放行 / 隔离 / 拒绝」「重新扫描」「标记整合」，整合后的文件可用「已整合」标签标识。
- **管理员**：`ADMIN_USERNAMES` 环境变量逗号分隔，默认 `admin`（公开部署务必改成自己的运营账号）。

上传大小与扫描说明：`MAX_UPLOAD_MB`（默认 20）、`SCAN_COMMAND`（可选）、`UPLOAD_DIR`（默认 `backend/uploads`）。云端 Nginx 已配置 `client_max_body_size 25m`。


### 可选：AI 拆解配置

AI 拆解走 OpenAI 兼容的 `/chat/completions` 接口，可对接 DeepSeek、通义千问、OpenAI 等。两种配置方式：

- **应用内配置（推荐）**：登录后在「AI」页面选择服务商、填写接口地址 / 模型 / API Key，先「测试连接」再「保存配置」。Key 在服务器用 `SECRET_KEY` 加密存储，接口只返回掩码；每个账号独立配置、互相隔离。
- **服务器环境变量（兜底）**：不配置应用内 AI 时，后端也会读取以下环境变量（多账号共用同一份）：

**不配置时 AI 入口会提示去设置，模板拆解与其余功能不受影响。**

| 变量 | 说明 | 示例 |
| --- | --- | --- |
| `LLM_API_KEY` | API 密钥（必填才启用 AI） | `sk-xxxx` |
| `LLM_API_BASE` | API 基地址（默认 OpenAI） | `https://api.deepseek.com/v1` |
| `LLM_MODEL` | 模型名（默认 `gpt-4o-mini`） | `deepseek-chat` / `qwen-plus` |

本地 Windows 临时设置（PowerShell）：

```powershell
cd backend
$env:LLM_API_BASE = "https://api.deepseek.com/v1"
$env:LLM_API_KEY = "sk-你的密钥"
$env:LLM_MODEL = "deepseek-chat"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

阿里云服务器：编辑 `/opt/studydash/.env` 加入上述三项后 `systemctl restart studydash`。Render：在 Web Service 环境变量中同样添加（可选）。

配置示例：DeepSeek 用 `LLM_API_BASE=https://api.deepseek.com/v1`、`LLM_MODEL=deepseek-chat`；通义千问用 `LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1`、`LLM_MODEL=qwen-plus`；OpenAI 用默认基地址 + `gpt-4o-mini`。

## 个性化设置（按账号）

登录后进入「设置 → 🎨 个性化」，所有偏好按账号存入数据库，换设备 / 换浏览器登录自动同步；未登录访问页面仍使用浏览器本地保存的外观。

| 分区 | 可配置项 | 生效范围 |
| --- | --- | --- |
| 外观 | 主题模式（浅色 / 深色 / 跟随系统）+ 5 色强调色（靛蓝 / 绿 / 玫红 / 琥珀 / 紫罗兰） | 全站即时生效，刷新保持 |
| 番茄钟时长 | 自定义 1–5 档时长（1–180 分钟）+ 设置默认档 | 专注页时长按钮与默认选中 |
| 复习间隔 | 自定义 1–8 个间隔（1–365 天，保存时排序去重） | 此后新完成的复习节点按新间隔生成，历史节点不变 |
| 任务默认值 | 习惯默认频率（每天 / 工作日 / 自定义星期）、默认预计分钟、科目库（快捷下拉） | 任务页新建表单默认值与科目 datalist |
| 首页功能卡片 | 7 张功能卡片显隐与上移 / 下移排序 | 首页「功能中心」过滤排序（设置卡片固定展示） |
| 我的计划模板 | 增删改自定义拆解模板（名称 + 1–20 个子项） | 计划页「拆解」弹层优先展示「我的模板」 |

习惯频率说明：选择「工作日」则周末打卡会返回错误；选择「自定义星期」后只有勾选的星期可以打卡，连续天数按「应打卡日均已打卡」计算。

> 番茄钟时长至少保留 1 项，默认值必须在时长列表内；不配置时全部使用默认值（25/45/60 分钟、复习间隔 1/2/4/7/15/30 天、每天打卡）。
## 手动验收清单

见 `docs/验收清单.md`；完整使用、部署与数据库配置教程见 `docs/操作指南.md`。

## 后续路线

- Phase 2：学习数据导出 Excel（ECharts 热力图 / 趋势、习惯打卡、复习提醒已上线）
- Phase 3：邮箱/找回密码、登录限流、密码强度校验（账号系统 v1 已上线）
- Phase 4：浏览器通知（习惯打卡、复习提醒已上线）

## 端口与云端部署能力（已预留）

- **端口**：后端统一入口 `backend/run.py`，读取环境变量 `PORT`（默认 `8000`）与 `HOST`（云端默认 `0.0.0.0`）。本地 `start.bat` 默认 8000，也支持设置 `PORT` 覆盖。
- **Render**：`render.yaml` 已配置 `python run.py`，Web Service 自动注入 `PORT`；数据库用 `DATABASE_URL`（PostgreSQL）。
- **Docker**：根目录 `Dockerfile`（前端构建 + 后端托管一体镜像），`docker build -t studydash .`、`docker run -d -p 8000:8000 -e SECRET_KEY=... -e INVITE_CODE=... studydash`。
- **单服务器**：`deploy/deploy.sh`（Nginx + systemd，内网端口 8000）。

## 部署到阿里云（单服务器 B/S，推荐）

一台 Ubuntu 服务器搞定全部：Nginx 托管前端页面，反向代理 `/api` 到 FastAPI（systemd 守护），数据存在服务器上的 SQLite。浏览器访问 `http://服务器IP` 即完整应用。

### 第 1 步：购买服务器

1. 阿里云控制台搜索「轻量应用服务器」（或 ECS）。
2. 地域随意；**镜像选 Ubuntu 22.04 或 24.04**；配置 2 核 2G 起步即可。
3. 购买后在控制台记下**公网 IP**。

### 第 2 步：防火墙放行端口（最容易踩坑的一步）

- 轻量服务器：控制台 → 你的服务器 → **防火墙** → 添加规则，放行 **80（HTTP）** 和 **443（HTTPS）**。22（SSH）默认已放行。
- ECS：控制台 → 实例 → **安全组** → 入方向规则，放行 80/443。

> 不放行 80 的话，浏览器会一直「无法访问」。

### 第 3 步：连接服务器

- 网页终端：控制台点「远程连接 → Workbench」。
- 或本地用 SSH：`ssh root@服务器公网IP`（密码在购买时设置，也可重置）。

### 第 4 步：上传项目文件

在本地 `E:\agent专用` 目录打包（排除体积大的目录）：

```powershell
tar -a -c -f study-dashboard.zip --exclude=study-dashboard/backend/.venv --exclude=study-dashboard/backend/__pycache__ --exclude=study-dashboard/frontend/node_modules --exclude=study-dashboard/frontend/dist --exclude=study-dashboard/backend/study.db study-dashboard
```

上传并解压（在服务器上执行）：

```bash
# 方法 A：scp（本地 PowerShell 里执行）
scp E:\agent专用\study-dashboard.zip root@服务器公网IP:/tmp/

# 方法 B：Workbench 里有「文件上传」按钮，把 zip 传上去

# 然后在服务器上：
apt-get install -y unzip
mkdir -p /tmp/pj /opt/studydash
unzip /tmp/study-dashboard.zip -d /tmp/pj
cp -r /tmp/pj/study-dashboard/* /opt/studydash/
```

### 第 5 步：一键部署

```bash
sudo bash /opt/studydash/deploy/deploy.sh
```

脚本会：装 Nginx/Python/Node → 建虚拟环境装依赖 → 构建前端 → 生成 `SECRET_KEY` / 邀请码 / 管理员账号 → 安装 systemd 服务 → 配置 Nginx 并启动。最后会打印**邀请码**（务必保存，注册要用）和**管理员用户名**。

部署后建议编辑 `/opt/studydash/.env`：

- 把 `ADMIN_USERNAMES=admin` 改成你自己的运营账号（默认任何注册为 `admin` 的人都是管理员）。
- 如需 AI 拆解，添加 `LLM_API_KEY` / `LLM_API_BASE` / `LLM_MODEL`。
- 如需病毒扫描，取消 `SCAN_COMMAND=clamscan --no-summary` 注释并安装 ClamAV（`apt install -y clamav && freshclam`）。
- 改完执行 `systemctl restart studydash`。

### 第 6 步：访问与常用命令

- 浏览器打开 `http://服务器公网IP`，用邀请码注册即可使用。
- 查看状态/日志/重启：
  ```bash
  systemctl status studydash
  journalctl -u studydash -f
  systemctl restart studydash
  ```

### 可选：绑定域名 + HTTPS

1. 域名解析加一条 A 记录，指向服务器公网 IP。
2. 服务器上执行：
   ```bash
   apt install -y certbot python3-certbot-nginx
   certbot --nginx -d 你的域名
   ```
3. 证书自动续期，之后用 `https://你的域名` 访问。

### 常见问题

- **浏览器打不开**：多半是第 2 步防火墙没放行 80 端口。
- **页面能开但接口报错（后端未启动）**：本地先跑 `backend\.venv\Scripts\python.exe scripts\selfcheck.py` 一键自检；云端看 `journalctl -u studydash -f`。
- **上传文件提示超限 / 被拒**：`MAX_UPLOAD_MB` 改大（Nginx 已放 25m）；确认扩展名在白名单内且文件头与扩展名一致。
- **要换邀请码/密钥**：编辑 `/opt/studydash/.env` 后 `systemctl restart studydash`。
- **数据备份**：数据库是 `/opt/studydash/backend/study.db`；学习文件在 `/opt/studydash/backend/uploads/`，两个目录一起备份。
---

## 部署上线（Netlify + Render）

> 备选方案：如果不想自己管服务器，也可以用 Netlify + Render 免运维托管（前端在 Netlify，后端在 Render，通过 `VITE_API_BASE` 连接）。

### 1. 部署后端到 Render（免费）

1. 把整个项目推到 GitHub。
2. 创建 PostgreSQL：Render 后台「New + → PostgreSQL」，创建成功后复制 **Internal Database URL**。
3. 在 https://dashboard.render.com 点「New + → Blueprint」，选择仓库；根目录已有 `render.yaml`，会自动创建 `studydash-api` 服务。
4. 在 Web Service 的环境变量里配置（必改三项）：
   - `DATABASE_URL`：粘贴第 2 步的 Internal Database URL（用于持久化数据）。
   - `SECRET_KEY`：一长串随机字符，用于 JWT 签名（重要，泄露等于别人能伪造登录）。
   - `INVITE_CODE`：你的注册邀请码。
   - `ALLOWED_ORIGINS`：Netlify 站点域名，例如 `https://你的站点名.netlify.app`。
5. 等构建完成后验证 `https://studydash-api.onrender.com/api/health` 返回 `{"status":"ok"}`。

### 2. 部署前端到 Netlify（免费）

1. 在 https://app.netlify.com 点「Add new site → Import an existing project」，连接同一个 GitHub 仓库。
2. Build command 填 `npm run build`，Publish directory 填 `dist`（`frontend/netlify.toml` 已写好，会自动识别）。
3. 环境变量 `VITE_API_BASE` 填后端地址，例如 `https://studydash-api.onrender.com`。
4. 部署完成后打开 `https://你的站点名.netlify.app` 即可使用。

### 注意事项

- 线上数据存储在 Render PostgreSQL（`DATABASE_URL`），重启/重新部署不会丢数据；本地开发仍用 `backend\study.db`。
- 后端 CORS 默认只放行本地开发地址；部署后记得把 Netlify 域名加进 `ALLOWED_ORIGINS`，否则浏览器会拦截请求。
- 本地默认 `SECRET_KEY=dev-secret-change-me`、`INVITE_CODE=studydash`，上线前务必在 Render 后台改成自己的值。
- 本地开发不受影响：`VITE_API_BASE` 留空时，前端仍走 Vite 代理到 `http://localhost:8000`。
- 后端 CORS 默认只放行本地开发地址；部署后记得把 Netlify 域名加进 `ALLOWED_ORIGINS`，否则浏览器会拦截请求。
