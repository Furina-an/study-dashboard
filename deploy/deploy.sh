#!/usr/bin/env bash
# StudyDash 单服务器一键部署脚本（Ubuntu 22.04 / 24.04）
# 前提：项目文件已放到 /opt/studydash（含 backend/、frontend/、deploy/）
# 用法：sudo bash /opt/studydash/deploy/deploy.sh
set -euo pipefail

PROJECT_DIR="/opt/studydash"
APP_USER="studydash"

if [[ $EUID -ne 0 ]]; then
  echo "请用 root 运行：sudo bash deploy.sh"
  exit 1
fi

echo "== [0/7] 安装基础软件（nginx / python / node） =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y nginx python3 python3-venv python3-pip curl openssl unzip

if ! command -v node >/dev/null 2>&1 || [[ "$(node -v)" != v22* ]]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
fi

echo "== [1/7] 检查项目文件 =="
if [[ ! -f "$PROJECT_DIR/backend/requirements.txt" ]]; then
  echo "错误：未找到 $PROJECT_DIR/backend/requirements.txt"
  echo "请先把项目上传到该目录，再运行本脚本。"
  exit 1
fi

echo "== [2/7] 创建运行用户 =="
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"

echo "== [3/7] 生成环境变量（SECRET_KEY / INVITE_CODE） =="
if [[ ! -f "$PROJECT_DIR/.env" ]]; then
  umask 077
  echo "SECRET_KEY=$(openssl rand -hex 32)" > "$PROJECT_DIR/.env"
  echo "INVITE_CODE=$(openssl rand -hex 6)" >> "$PROJECT_DIR/.env"
  echo "ADMIN_USERNAMES=admin" >> "$PROJECT_DIR/.env"
  echo "MAX_UPLOAD_MB=20" >> "$PROJECT_DIR/.env"
  echo "# SCAN_COMMAND=clamscan --no-summary" >> "$PROJECT_DIR/.env"
fi
echo "邀请码：$(grep '^INVITE_CODE=' "$PROJECT_DIR/.env" | cut -d= -f2)"
echo "管理员：$(grep '^ADMIN_USERNAMES=' "$PROJECT_DIR/.env" | cut -d= -f2)"
echo "  !! 上线后请编辑 /opt/studydash/.env 把 ADMIN_USERNAMES 改成你的运营账号！"

echo "== [4/7] 后端依赖 =="
python3 -m venv "$PROJECT_DIR/backend/.venv"
"$PROJECT_DIR/backend/.venv/bin/pip" install --upgrade pip
"$PROJECT_DIR/backend/.venv/bin/pip" install -r "$PROJECT_DIR/backend/requirements.txt"

echo "== [5/7] 前端构建 =="
(
  cd "$PROJECT_DIR/frontend"
  if [[ ! -d node_modules ]]; then
    npm install
  fi
  npm run build
)

echo "== [6/7] 安装 systemd 服务 =="
cat > /etc/systemd/system/studydash.service <<EOF
[Unit]
Description=StudyDash API
After=network.target

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$PROJECT_DIR/backend
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

echo "== [7/7] 配置 Nginx 并启动 =="
cp "$PROJECT_DIR/deploy/nginx.conf" /etc/nginx/sites-available/studydash
ln -sf /etc/nginx/sites-available/studydash /etc/nginx/sites-enabled/studydash
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

chown -R "$APP_USER":"$APP_USER" "$PROJECT_DIR"
systemctl daemon-reload
systemctl enable --now studydash

echo ""
echo "=========================================="
echo "部署完成！"
echo "访问：http://服务器公网IP"
echo "邀请码：$(grep '^INVITE_CODE=' "$PROJECT_DIR/.env" | cut -d= -f2)"
echo "管理员：$(grep '^ADMIN_USERNAMES=' "$PROJECT_DIR/.env" | cut -d= -f2)（运营账号，务必修改默认值）"
echo "常用命令："
echo "  查看状态    systemctl status studydash"
echo "  查看日志    journalctl -u studydash -f"
echo "  重启服务    systemctl restart studydash"
echo "=========================================="
