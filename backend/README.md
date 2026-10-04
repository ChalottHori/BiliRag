# BiliRag 后端

BiliRag 的个人自用后端：FastAPI + SQLite + Chroma。把 B 站收藏/链接视频「提取内容 → 结构化摘要 → 可检索问答知识库」，支持 Markdown 导出与对话历史管理。

## 运行

```bash
cd backend
pip install -r requirements.txt
python run.py            # 等价于 uvicorn app.main:app --host 127.0.0.1 --port 8000
```

首次启动会在 `data/` 下自动创建 SQLite（`app.db`）、FTS5 全文索引、Fernet 密钥（`.secret_key`）、Chroma 向量库目录、日志等。

## 配置

配置存于 SQLite `settings` 表（`/api/config` 读写），可用环境变量覆盖（前缀 `BILIRAG_`）：

| 环境变量 | 说明 |
|---|---|
| `BILIRAG_DATA_DIR` | 数据目录（默认 `backend/data`） |
| `BILIRAG_LLM_BASE_URL` / `BILIRAG_LLM_API_KEY` / `BILIRAG_LLM_MODEL` | LLM（OpenAI 兼容） |
| `BILIRAG_ASR_MODEL` | `small` / `medium` / `large-v3` |
| `BILIRAG_CONCURRENCY` | 任务并发数（默认 1） |
| `BILIRAG_EMBEDDING_PROVIDER` | `local`（默认） / `api` |

## 测试 / 质量

外部依赖（B 站 / LLM / ASR / embedding / Chroma）全部 mock，测试离线、快速、确定性。

```bash
pytest                 # 单元 + 集成测试
ruff check .           # lint
black --check .        # format
mypy app/              # 类型检查
```

## 目录结构

```
app/
├── main.py          # 入口：lifespan（建表/恢复/worker）、SSE、静态托管
├── config.py        # 配置加载（settings 表 + 环境变量覆盖）
├── db.py            # engine/session + create_all + FTS5 虚拟表/触发器
├── security.py      # Fernet 加解密（cookie / api_key）
├── api/             # 路由：auth/folders/import_/summarize/items/chat/export/config_api
├── services/
│   ├── bilibili/    # 扫码登录、wbi 签名、字幕、DASH 音频、收藏夹（只读）
│   ├── llm/         # OpenAI 兼容客户端、结构化摘要（map-reduce）、流式
│   ├── asr/         # faster-whisper 封装
│   ├── indexing/    # 切块、embedding、Chroma 读写
│   ├── queue/       # 任务队列、worker 线程池、事件总线、断点续跑
│   ├── history/     # FTS5 对话检索
│   ├── export/      # Markdown 生成
│   ├── pipeline.py  # 单个条目流水线（转写→摘要→向量化）
│   └── items.py     # 条目创建（去重）
├── models/          # SQLAlchemy 模型
└── schemas/         # Pydantic 请求/响应模型
```
