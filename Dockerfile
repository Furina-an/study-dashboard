# StudyDash 云端容器化部署（可选方案）
# 构建： docker build -t studydash .
# 运行： docker run -d -p 8000:8000 -e SECRET_KEY=... -e INVITE_CODE=... studydash
# 平台： Render / Railway / Fly.io / 阿里云容器服务 均可直接使用（平台注入 PORT）
# 阶段一：构建前端
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci || npm install
COPY frontend/ .
RUN npm run build

# 阶段二：运行后端（托管前端构建产物）
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=frontend /app/frontend/dist frontend/dist
ENV PORT=8000 HOST=0.0.0.0
EXPOSE 8000
WORKDIR /app/backend
CMD ["python", "run.py"]
