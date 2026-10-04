# BiliRag 前端

BiliRag 的 React + TypeScript 前端：玻璃拟态（B 站粉）风格，6 个路由页，收藏夹页内嵌对话窗口与登录模态框。

## 技术栈

- React 19 + TypeScript（strict）+ Vite
- react-router（页面路由）、Zustand（状态 + persist）、TanStack Query（服务端数据）
- Radix UI（无样式原语）+ CSS Modules + design tokens（`src/styles/tokens.css`）
- oxlint（lint）+ prettier（format）+ vitest / Testing Library（测试）

## 运行

```bash
cd frontend
npm install
npm run dev        # 开发（/api 代理到 http://127.0.0.1:8000）
npm run build      # 生产构建（产物 dist/，由后端静态托管）
```

## 脚本

| 命令                | 说明                         |
| ------------------- | ---------------------------- |
| `npm run dev`       | 启动 Vite 开发服务器         |
| `npm run build`     | `tsc --noEmit && vite build` |
| `npm run test`      | 跑 vitest 测试               |
| `npm run lint`      | oxlint                       |
| `npm run typecheck` | `tsc --noEmit`               |
| `npm run format`    | prettier 全量格式化          |

## 目录结构

```
src/
├── api/          # fetch 客户端 + 各域 endpoint 封装（对应后端 §7）
├── pages/        # 6 个路由页：Folders/Import/Tasks/Items/History/Settings
├── components/   # 业务组件（ChatWindow/LoginModal/VideoRow/...）+ ui/ + layout/
├── hooks/        # useTaskProgress(SSE) / useChatStream(fetch 流式) / useResizable
├── stores/       # Zustand：auth / ui(persist) / selection / chat
└── styles/       # tokens.css 设计令牌
```

## 关键约定

- 聊天流式 `POST /api/chat` 用 `fetch + ReadableStream`（EventSource 不支持 POST）；进度 `GET /api/events` 用 EventSource。
- 主强调色 B 站粉 `#FB7299`，玻璃卡片 `--glass-bg` / `--glass-border` 等令牌见 `tokens.css`。
