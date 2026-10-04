"""BiliRag 后端启动入口。

用法：
    python run.py
等价于：
    uvicorn app.main:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("BILIRAG_HOST", "127.0.0.1")
    port = int(os.environ.get("BILIRAG_PORT", "8000"))
    uvicorn.run("app.main:app", host=host, port=port)


if __name__ == "__main__":
    main()
