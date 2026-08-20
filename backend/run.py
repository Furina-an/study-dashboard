"""统一启动入口：支持云端端口注入。

- PORT 环境变量：默认 8000（Render / Railway / Docker 等平台会自动注入）
- HOST 环境变量：设置后用于外部访问（如 0.0.0.0）；本地默认 127.0.0.1
用法：
    本地：  python run.py
    云端：  PORT=10000 HOST=0.0.0.0 python run.py
"""
import os

import uvicorn


def main() -> None:
    port_env = os.getenv("PORT", "").strip()
    port = int(port_env) if port_env.isdigit() else 8000
    host = os.getenv("HOST", "0.0.0.0" if port_env else "127.0.0.1").strip()
    uvicorn.run("app.main:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
