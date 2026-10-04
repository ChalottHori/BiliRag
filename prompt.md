# BiliRag 开发分派说明（prompt.md）

> 本文件用于把 BiliRag 的前后端开发任务拆解成若干**自包含任务块**，分派给子 agent 顺序执行。
> 你（主 agent / 子 agent）按下面顺序逐个读取并执行任务块即可；**每个任务块都自包含**，包含目标、依赖、必读文档、交付文件、完成验证、关键约束与提交信息。
>
> **执行纪律**：
> 1. 严格**按顺序**执行，B-1 → … → B-5 → F-1 → … → F-5，不得跳步或并行（前端依赖后端 API）。
> 2. 每个任务块只有在「完成验证」全部通过后才算完成，然后提交，再进入下一个任务块。
> 3. 规范依据一律以 `documents/` 下的四件套为准；若本文件与文档冲突，以文档为准并回报。

---

## Part 0 — 全局总览与约定（每个子 agent 必读）

### 0.1 项目定位

BiliRag 是**个人自用的本地 Web 应用**：把 B 站收藏/链接里的视频「提取内容 → 结构化摘要 → 可检索问答知识库」，支持 Markdown 导出与对话历史管理。单机单用户、Windows 11、界面简体中文。

### 0.2 四件套文档（先读）

| 文档 | 路径 | 读哪些章节 |
|---|---|---|
| 需求 | `documents/requirements.md` | 全部；重点是 §5 功能需求、§6 数据模型、§7 API、§8 任务流程 |
| UI 设计 | `documents/ui设计.md` | 全部；重点是 §2 设计令牌、§4 屏幕、§5 组件库 |
| 技术架构 | `documents/技术架构设计.md` | 全部；§1 决策、§2 后端、§3 前端 |
| 风格参考 | `documents/Glassmorphism（玻璃拟态主灰色）/design.md` | 配色/字体/间距/组件样式 |

### 0.3 技术栈速查

- **后端**：Python 3.11+、FastAPI、uvicorn、SQLAlchemy、Pydantic、httpx（async）、faster-whisper（CUDA）、chromadb、sentence-transformers（本地 `BAAI/bge-small-zh-v1.5`）、cryptography（Fernet）、ffmpeg（系统依赖）。
- **前端**：React、TypeScript（strict）、Vite、react-router、Zustand、TanStack Query、Radix UI（无样式原语）、CSS Modules、qrcode、react-markdown。

### 0.4 目录结构（最终形态，各任务分步建成）

```
BiliRag/
├── backend/
│   ├── app/
│   │   ├── main.py              # 应用入口（lifespan/SSE/静态托管）
│   │   ├── config.py            # 配置加载
│   │   ├── db.py                # SQLite engine/session + create_all + FTS5 DDL
│   │   ├── security.py          # Fernet 加解密
│   │   ├── api/                 # auth/folders/import_/summarize/items/chat/export/config_api
│   │   ├── services/            # bilibili/ asr/ llm/ indexing/ queue/ history/ export/
│   │   ├── models/              # SQLAlchemy 模型
│   │   └── schemas/             # Pydantic 模型
│   ├── data/                    # 运行时数据（gitignore）
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── src/
│   │   ├── api/                 # 接口客户端
│   │   ├── pages/               # FoldersPage/ImportPage/TasksPage/ItemsPage/HistoryPage/SettingsPage
│   │   ├── components/          # ChatWindow/LoginModal/VideoRow/StatusTag/Drawer/... + ui/ + layout/
│   │   ├── hooks/               # useTaskProgress/useChatStream 等
│   │   ├── stores/              # Zustand
│   │   ├── styles/              # tokens.css
│   │   └── router.tsx
│   └── package.json
├── documents/
├── scripts/start.bat
└── README.md
```

### 0.5 通用工程约定（每个任务块都要遵守）

- **git**：由 B-1 执行 `git init`；此后每个任务块结束都要 `git add` + 提交，提交信息用该任务块标注的格式（见各块）。
- **lint/format**：
  - 后端：`ruff`（lint）+ `black`（format）。
  - 前端：`oxlint`（lint）+ `prettier`（format）。
- **类型检查**：
  - 后端：`mypy`。
  - 前端：`tsc --noEmit`（strict）。
- **完成标准**：每个任务块写明了「完成验证」命令，**全部通过才算完成**；未通过的不得进入下一块。
- **测试原则**：外部依赖（B 站接口、LLM、ASR 模型、embedding 模型）一律用 mock，保证测试离线、快速、确定性。不要求真实 GPU/账号/模型下载的端到端。

### 0.6 子 agent 协作约定（共享文件防冲突）

- 共享文件各有唯一 owner：后端 `main.py` 与路由注册归 **B-4**；前端 `router.tsx` 归 **F-1**、`stores/` 归 **F-2**。其他任务块如需接入，只允许在约定好的挂载点**新增**，不得改写 owner 已交付的核心逻辑；确有冲突时回报主 agent，不擅自改。
- 新增文件一律放入既定目录，禁止散落根目录。
- 保持跨任务一致的命名：后端路由按 §7 路径、模型字段按 §6.1 表名/字段名；前端组件名按 ui设计 §5.2。

### 0.7 关键防坑清单（务必内化，勿只读文档漏掉）

1. **FTS5 不是普通 SQLAlchemy 模型**：用原生 SQL 建 `chat_message_fts` 虚拟表 + 触发器，在 `db.py` 启动时执行。
2. **流式传输**：`POST /api/chat` 是流式响应，浏览器 `EventSource` 不支持 POST，前端必须用 `fetch + ReadableStream` 解析；只有 `GET /api/events`（进度）用 `EventSource`。后端 `POST /api/chat` 用 `StreamingResponse`。
3. **Chroma 一致性**：向量 id=`{item_id}:{chunk_idx}`，metadata 必带 `item_id`；删除条目用 `collection.delete(where={"item_id": ...})`；重新总结先删后写。
4. **GPU/阻塞任务进线程池**：ASR、本地 embedding、音频下载等阻塞/GPU 任务放进 `ThreadPoolExecutor`（并发数=`settings.concurrency`，默认 1），绝不放进 asyncio 事件循环；worker 线程 → async 层用 `loop.call_soon_threadsafe`。
5. **加密**：cookie 与 LLM `api_key` 用 Fernet 加密落盘，密钥独立存 `data/.secret_key`（权限 600、不与 app.db 同文件）；日志绝不输出 cookie/api_key。
6. **B 站只读**：绝不调用 B 站任何写接口；请求失败按指数退避重试、限流降速。

---

## Part 1 — 后端任务块（串行）

### B-1 脚手架 + 数据层

- **目标**：搭起可启动的后端骨架，完成配置/安全/数据库/全部数据模型。
- **前置依赖**：无（本阶段起点；在**项目根目录**执行 `git init`，让仓库同时覆盖 `backend/`、`frontend/`、`documents/`）。
- **必读文档**：`requirements.md` §6 数据模型、§8.2 批量执行、§8.4 安全与异常；`技术架构设计.md` §2.1/§2.5/§2.7。
- **交付文件**：
  - `backend/requirements.txt`、`backend/run.py`
  - `backend/app/config.py`（读取 `settings` 表配置 + 环境变量覆盖）
  - `backend/app/security.py`（Fernet 加解密 + `data/.secret_key` 密钥加载）
  - `backend/app/db.py`（SQLAlchemy engine/session；`create_all`；**FTS5 原生 SQL + 触发器**）
  - `backend/app/models/`（`settings`、`bilibili_session`、`folder`、`video`、`part`、`item`、`collection_summary`、`chat_session`、`chat_message`；字段与唯一约束按 §6.1，`item` 状态机枚举按 §6.2）
  - `backend/app/schemas/`（Pydantic 基础请求/响应模型）
  - `backend/app/main.py`（最小可启动空壳，仅 `/health`）
  - 日志配置（落 `data/logs/`，脱敏）
- **完成验证**：
  - `cd backend && pip install -r requirements.txt`
  - `uvicorn app.main:app --host 127.0.0.1 --port 8000` 能启动，`GET /health` 返回 ok。
  - 启动后 `data/app.db` 成功建表（含 `chat_message_fts` 虚拟表）。
  - `ruff check .`、`black --check .`、`mypy app/` 全绿。
- **关键约束/坑**：见 0.7 第 1、5 条；`item` 的 `(bvid, cid)` 唯一约束；`chat_session` 含 `title`/`pinned` 字段。删除占位 `backend/main.py`、`backend/test_main.http`；在根目录建 `.gitignore`（忽略 `.venv/`、`.idea/`、`__pycache__/`、`data/`、`node_modules/`、`.env`）。
- **提交信息**：`chore(backend): scaffold + data models + db/fts5`

### B-2 外部服务（B 站 / LLM / ASR）

- **目标**：实现三个外部服务封装，可被 worker 与 API 层共用。
- **前置依赖**：B-1。
- **必读文档**：`requirements.md` §5.1/§5.2/§5.4/§5.5、§8.4；`技术架构设计.md` §2.6。
- **交付文件**：
  - `backend/app/services/bilibili/`（qrcode 生成/轮询、wbi 签名、字幕获取、DASH 音频下载、收藏夹列表/视频/分P）——只读。
  - `backend/app/services/llm/`（OpenAI 兼容客户端：结构化摘要 + 长文 map-reduce + 问答流式生成）
  - `backend/app/services/asr/`（faster-whisper 封装：`small/medium/large-v3` 档位、转写返回全文稿）
- **完成验证**：
  - 每个服务配单测（mock 网络/模型），`pytest` 通过。
  - `ruff check .`、`black --check .`、`mypy app/` 全绿。
- **关键约束/坑**：见 0.7 第 4、6 条；统一 `httpx.AsyncClient` + 重试退避装饰器；worker 侧用 `asyncio.run()` 跑短网络任务。
- **提交信息**：`feat(backend): bilibili + llm + asr services`

### B-3 索引与队列

- **目标**：实现切块/向量入库与任务队列/进度事件。
- **前置依赖**：B-1（依赖模型）、B-2（可被队列调用，但可先用 stub）。
- **必读文档**：`requirements.md` §6.1（item/chunk_count）、§8.1/§8.2；`技术架构设计.md` §2.3/§2.4/§2.5。
- **交付文件**：
  - `backend/app/services/indexing/`（切块、embedding 计算、Chroma 增删、按 item_id 删除一致性）
  - `backend/app/services/queue/`（进程内队列、worker 线程池、内存事件总线、断点续跑恢复逻辑）
- **完成验证**：
  - 单测（mock embedding/ASR）：切块、Chroma 增删/删除一致性、队列入队→worker 消费→事件发布、恢复逻辑（pending/transcribing→pending，summarizing→summarizing）。
  - `ruff check .`、`black --check .`、`mypy app/` 全绿。
- **关键约束/坑**：见 0.7 第 3、4 条；事件总线经 `loop.call_soon_threadsafe` 推给 async 层。
- **提交信息**：`feat(backend): indexing + queue/worker/event-bus`

### B-4 API 层与编排

- **目标**：实现全部 REST/SSE 路由与主入口，串起完整后端。
- **前置依赖**：B-2、B-3。
- **必读文档**：`requirements.md` §7 API 全部；`技术架构设计.md` §2.2/§2.3、§4 时序。
- **交付文件**：
  - `backend/app/api/`（`auth`、`folders`、`import_`、`summarize`、`items`、`chat`、`export`、`config_api`），路径/入参/出参严格按 §7。
  - `backend/app/services/history/`（FTS5 标题+内容检索、按会话聚合返回命中数+摘录）
  - `backend/app/services/export/`（Markdown 生成：条目/收藏夹/全量 + 分目录 + 总索引；会话导出）
  - `backend/app/main.py`（lifespan：建表→恢复→启动 worker；`GET /api/events` SSE 进度；`POST /api/chat` 流式 `StreamingResponse`；静态托管前端 build）
- **完成验证**：
  - 集成测试（mock B 站/LLM/ASR/embedding），`pytest` 覆盖全部端点（含 §7.6 的 `PATCH /chat/sessions/{id}`、`GET /chat/search`、`POST /chat/sessions/{id}/export`）。
  - `uvicorn` 启动后各端点可访问、`/api/events` 能连、`/api/chat` 能流式。
  - `ruff`/`black`/`mypy` 全绿。
- **关键约束/坑**：见 0.7 第 2 条；`main.py` 与路由注册由本块 owner，其他块不得改写。
- **提交信息**：`feat(backend): api routes + main + history + export`

### B-5 后端测试与收尾

- **目标**：补齐关键单测，整体收尾。
- **前置依赖**：B-4。
- **必读文档**：`技术架构设计.md` §5 测试策略。
- **交付文件**：`backend/tests/` 关键单测（wbi 签名、`(bvid,cid)` 去重、item 状态机、FTS 检索、Chroma 删除一致性）、`backend/README` 或运行说明补充。
- **完成验证**：
  - `pytest` 全绿；`ruff check .`、`black --check .`、`mypy app/` 全绿。
  - `uvicorn app.main:app` 冷启动 smoke 通过。
- **关键约束/坑**：测试外部依赖全部 mock。
- **提交信息**：`test(backend): core unit tests + cleanup`

---

## Part 2 — 前端任务块（串行，依赖后端 API 就绪）

### F-1 脚手架 + 框架

- **目标**：搭 Vite + React + TS 工程，落地设计令牌、路由与应用壳。
- **前置依赖**：后端 B-4 完成（API 就绪）。
- **必读文档**：`ui设计.md` §2 设计令牌、§3 全局框架；`技术架构设计.md` §3.1/§3.2。
- **交付文件**：
  - `frontend/package.json`（补 `react-router-dom`、`@radix-ui/react-dialog`/`-dropdown-menu`/`-popover`/`-switch`/`-tabs`）、Vite/TS 配置（**确保 `strict: true`**）、oxlint/prettier 配置。
  - `frontend/src/styles/tokens.css`（design tokens：`--brand #FB7299`、玻璃卡片变量、8px 间距、字体栈）。
  - `frontend/src/router.tsx`（6 路由：`/folders /import /tasks /items /history /settings`）。
  - `frontend/src/components/layout/AppShell.tsx`（顶栏：左 Logo、右「登录/账号 + 设置」；纯文字可折叠侧边栏 5 项）。
  - `frontend/src/components/ui/`（Radix 无样式原语封装：Button/Chip/Input/Select/Switch/Dialog/Dropdown/Popover/Tabs，注入玻璃拟态样式）。
- **完成验证**：
  - `cd frontend && npm install && npm run build` 成功。
  - `npx tsc --noEmit`、`npm run lint` 全绿。
  - `npm run dev` 能渲染空壳 AppShell（含折叠侧边栏）。
- **关键约束/坑**：主强调色 B 站粉 `#FB7299`；侧边栏折叠态 48px 窄条、展开约 200px；`router.tsx` 由本块 owner；`index.html` 设 `lang="zh-CN"`、`title`=BiliRag；删除 Vite 演示内容（`App.tsx` 计数器/`App.css`/`assets` 演示图）。
- **提交信息**：`chore(frontend): scaffold + tokens + router + app-shell`

### F-2 状态与数据层

- **目标**：实现 Zustand stores、React Query、API 客户端与 SSE hooks。
- **前置依赖**：F-1。
- **必读文档**：`技术架构设计.md` §3.3/§3.4。
- **交付文件**：
  - `frontend/src/stores/`（`auth`、`ui`〔折叠/面板宽度，persist〕、`selection`〔跨收藏夹勾选累计〕、`chat`〔当前会话消息/流式缓冲〕）。
  - `frontend/src/api/`（fetch 客户端 + 各域 endpoint 封装，对应 §7）。
  - `frontend/src/hooks/`（`useTaskProgress`〔EventSource〕、`useChatStream`〔fetch + ReadableStream 解析 SSE 帧〕、`useResizable`）。
- **完成验证**：`npx tsc --noEmit`、`npm run lint`、`npm run build` 全绿。
- **关键约束/坑**：见 0.7 第 2 条——聊天流式必须 fetch，进度才用 EventSource。
- **提交信息**：`feat(frontend): stores + api client + sse hooks`

### F-3 业务组件

- **目标**：实现 ui设计 §5.2 全部业务组件。
- **前置依赖**：F-2。
- **必读文档**：`ui设计.md` §5.2 组件库、§4.3.1 对话窗口、§4.2 登录模态。
- **交付文件**：
  - `frontend/src/components/`：`ChatWindow`（气泡/流式/筛选弹面板/顶栏三件套）、`LoginModal`（二维码/状态）、`VideoRow`（缩略图/勾选/失效灰态/合集展开）、`StatusTag`（五态配色）、`Drawer`、`SelectionBar`、`DirPicker`、`Pagination`。
- **完成验证**：`npm run build` 通过；关键组件（ChatWindow 流式、VideoRow 勾选/整选）配 vitest/RTL 测试通过。
- **关键约束/坑**：五态配色见 ui设计 §5.2；勾选框/整选框三态。
- **提交信息**：`feat(frontend): business components`

### F-4 页面实现与联调

- **目标**：实现 6 页面 + 登录模态 + 未登录欢迎态，接后端联调。
- **前置依赖**：F-3。
- **必读文档**：`ui设计.md` §4 屏幕设计（4.1~4.8）。
- **交付文件**：
  - `frontend/src/pages/`：`FoldersPage`（三段式工作台：视频列表〔横向标签+整选+分页+跨收藏夹汇总条〕+ 对话窗口）、`ImportPage`、`TasksPage`、`ItemsPage`（筛选条+抽屉详情+合集总摘要+导出目录选择）、`HistoryPage`（左列表+右消息两栏）、`SettingsPage`（左分区导航+右表单+备份）。
  - 登录模态框挂到 AppShell 顶栏；未登录欢迎态。
- **完成验证**：`npm run build` 通过；`npm run dev` 下 6 页可渲染、与后端 API 联调 smoke（登录态、收藏夹列表、聊天流式）。
- **关键约束/坑**：收藏夹页三段式，视频列表与对话窗口可拖拽调宽并持久化。
- **提交信息**：`feat(frontend): pages + integration`

### F-5 前端收尾

- **目标**：补齐测试、全量检查、与后端联调收尾。
- **前置依赖**：F-4。
- **必读文档**：`技术架构设计.md` §5。
- **交付文件**：`frontend/src/**/*.test.tsx` 补测；README 运行说明补充。
- **完成验证**：
  - `npm run test` 通过；`npx tsc --noEmit`、`npm run lint`、`npx prettier --check .` 全绿。
  - 后端 + 前端联调 smoke：一键启动、登录态、收藏夹浏览、问答流式、对话历史检索/导出。
- **提交信息**：`test(frontend): tests + cleanup`
