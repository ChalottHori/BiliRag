# BiliRag

个人自用的本地 Web 应用：把 B 站收藏/链接里的视频「提取内容 → 结构化摘要 → 可检索问答知识库」，支持 Markdown 导出与对话历史管理。Windows 11 单机、界面简体中文。

## 核心链路

```
扫码登录 B 站（cookie，只读）
  → 浏览/勾选收藏视频（或粘贴 B 站链接）
     → 后台提取内容（字幕优先，无字幕则 DASH 音频 → faster-whisper 转写）
        → LLM 生成结构化摘要 + 全文稿向量化入库 Chroma
           → 检索问答（流式/多轮/带出处） / Markdown 导出 / 管理
```

## 技术栈

- **后端**：Python 3.11+ / FastAPI / SQLAlchemy / SQLite(+FTS5) / Chroma / httpx / faster-whisper / sentence-transformers / cryptography
- **前端**：React 19 / TypeScript(strict) / Vite / react-router / Zustand / TanStack Query / Radix UI / CSS Modules

## 快速开始

一键启动（Windows）：

```bat
scripts\start.bat
```

或手动：

```bash
# 后端
cd backend
pip install -r requirements.txt
python run.py                       # http://127.0.0.1:8000
# or
.venv/Scripts/python.exe -m pip install -r requirements.txt   #虚拟环境启动后端
.venv/Scripts/python.exe run.py

# 前端（开发模式）
cd frontend
npm install
npm run dev                         # http://localhost:5173（/api 代理到后端）
```

后端生产模式会静态托管 `frontend/dist`（`npm run build` 产物），仅需访问 `http://127.0.0.1:8000`。

## 配置

后端配置存于 SQLite `settings` 表（页面「设置」读写），可用环境变量覆盖（前缀 `BILIRAG_`）：

- `BILIRAG_DATA_DIR`：数据目录（默认 `backend/data`）
- `BILIRAG_LLM_BASE_URL` / `BILIRAG_LLM_API_KEY` / `BILIRAG_LLM_MODEL`：LLM（OpenAI 兼容）
- `BILIRAG_ASR_MODEL`：`small` / `medium` / `large-v3`
- `BILIRAG_CONCURRENCY`：任务并发数（默认 1）

> 首次使用需在「设置」页配置 LLM（base_url / api_key / model），并扫码登录 B 站。

## 测试

外部依赖（B 站 / LLM / ASR / embedding / Chroma）全部 mock，测试离线、快速、确定性。

```bash
# 后端
cd backend && pytest
cd backend && ruff check . && black --check . && mypy app/

# 前端
cd frontend && npm run test
cd frontend && npm run lint && npx tsc --noEmit && npx prettier --check .
```

## 目录结构

```
BiliRag/
├── backend/           # FastAPI 后端
│   ├── app/
│   │   ├── main.py    #   入口：lifespan/SSE/静态托管
│   │   ├── api/       #   路由（auth/folders/import/summarize/items/chat/export/config）
│   │   ├── services/  #   bilibili/llm/asr/indexing/queue/history/export/pipeline
│   │   ├── models/    #   SQLAlchemy 模型
│   │   └── schemas/   #   Pydantic 模型
│   └── tests/
├── frontend/          # React + TypeScript 前端
│   └── src/
│       ├── pages/     #   6 个路由页
│       ├── components/#   ChatWindow/LoginModal/VideoRow/... + ui/ + layout/
│       ├── stores/    #   Zustand
│       └── api/       #   接口客户端
├── documents/         # 需求 / UI 设计 / 技术架构 / 风格参考
└── scripts/start.bat  # 一键启动
```
