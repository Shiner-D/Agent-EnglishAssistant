# AI 个性化英语学习助手

基于 LangGraph + RAG 的全栈 AI 英语学习平台，支持智能意图路由、词汇检索、练习生成、翻译改写和个人词库管理。

---

## 功能特性

- **AI 对话导师**：多意图路由，自动识别用户需求并调度专属处理节点
- **单词查询**：RAG 检索词典知识库，返回发音、释义、例句、搭配用法
- **练习生成**：自动生成多选题、填空题等英语练习题
- **翻译**：中英双向翻译
- **句子改写**：简化/升级句子表达
- **个人词库**：添加/删除生词，进行复习
- **学习仪表盘**：展示学习进度与统计
- **TTS 朗读**：通过 edge-tts 实现文字转语音
- **流式响应**：SSE 实时流式输出，支持 Markdown 渲染

---

## 技术栈

### 后端

| 类别 | 技术 |
| --- | --- |
| Web 框架 | FastAPI 0.115 + Uvicorn |
| AI 框架 | LangChain 0.3 + LangGraph 0.2 |
| LLM | DeepSeek / Qwen（OpenAI 兼容接口） |
| 向量数据库 | ChromaDB 0.5 |
| 嵌入模型 | BAAI/bge-m3（本地） |
| 重排序模型 | BAAI/bge-reranker-v2-m3（本地） |
| 关键词检索 | BM25（rank-bm25） |
| 数据库 | SQLite + SQLAlchemy 2.0 + aiosqlite |
| TTS | edge-tts |
| 日志 | loguru |

### 前端

| 类别 | 技术 |
| --- | --- |
| 框架 | Vue 3.4 + TypeScript 5.4 |
| 构建工具 | Vite 5.3 |
| UI 组件库 | Element Plus 2.14 |
| 状态管理 | Pinia 2.1 |
| 路由 | Vue Router 4.3 |
| HTTP 客户端 | Axios |
| Markdown 渲染 | Marked + DOMPurify |

---

## 项目结构

```text
Agent-English/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口，模型预加载，路由注册
│   │   ├── agent/
│   │   │   ├── graph.py         # LangGraph 状态机，意图路由与节点编排
│   │   │   ├── nodes.py         # 各意图节点实现（词查、练习、翻译等）
│   │   │   ├── state.py         # Agent 状态定义
│   │   │   └── prompts.py       # 系统提示词与任务提示词
│   │   ├── rag/
│   │   │   └── hybrid_search.py # 混合检索：BM25 + 向量 + RRF + 重排序
│   │   ├── api/                 # FastAPI 路由（chat/users/words/exercises/tts/dashboard）
│   │   ├── models/              # SQLAlchemy 数据模型（User/Conversation/Message/Word/Exercise）
│   │   ├── services/
│   │   │   └── llm.py           # LLM 服务封装，支持流式与非流式
│   │   ├── tools/               # Agent 工具函数
│   │   └── core/
│   │       └── config.py        # Pydantic Settings，集中管理所有环境变量
│   ├── scripts/
│   │   ├── clean_ecdict.py      # 清洗 ECDICT CSV 数据
│   │   └── build_index.py       # 构建 Chroma 向量索引
│   ├── tests/
│   │   ├── test_api.py          # API 集成测试
│   │   └── test_rag_evaluation.py # RAG 检索评估
│   ├── data/                    # SQLite 数据库、Chroma 向量库、日志
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── views/               # TutorView / VocabularyView / ReviewView / ExerciseView / DashboardView
│   │   ├── components/          # MarkdownContent 等复用组件
│   │   ├── stores/              # Pinia store（user / chat）
│   │   ├── api/                 # Axios 封装的后端接口
│   │   └── router/              # Vue Router 路由配置
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 架构说明

### LangGraph Agent 工作流

用户消息进入后，首先由意图路由节点通过 LLM 分类，识别为以下 6 种意图之一，再派发至对应节点处理：

```text
用户输入
    │
    ▼
意图路由（Intent Router）
    │
    ├─ WORD_LOOKUP   → RAG 检索 → 词义讲解
    ├─ EXERCISE      → 练习题生成
    ├─ TRANSLATE     → 中英翻译
    ├─ REWRITE       → 句子改写
    ├─ VOCABULARY    → 词库增删
    └─ GENERAL_CHAT  → 自由对话
```

### RAG 混合检索

1. **向量检索**（语义相似度，权重 0.7）：使用 BGE-M3 嵌入 + ChromaDB
2. **BM25 检索**（关键词匹配，权重 0.3）
3. **RRF 融合**（Reciprocal Rank Fusion 排序融合）
4. **重排序**（BGE-Reranker 交叉编码器精排，取 Top-5）

---

## 快速开始

### 前置要求

- Python 3.11+
- Node.js 20+
- DeepSeek / Qwen 等 OpenAI 兼容 API Key
- [ECDICT 词典数据](https://github.com/skywind3000/ECDICT)（下载 `ecdict.csv`）

### 本地开发

**后端：**

```bash
cd backend
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY 和 LLM_BASE_URL

# 构建词典索引（首次运行）
python scripts/clean_ecdict.py --input ecdict.csv --output data/words.json
python scripts/build_index.py --input data/words.json

# 启动服务
uvicorn app.main:app --reload
uvicorn app.main:app --host 0.0.0.0 --port 8000
# 访问 http://localhost:8000/docs 查看 API 文档
```

**前端（另开终端）：**

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

### Docker 部署

```bash
# 配置环境变量
cp backend/.env.example .env
# 编辑 .env，填入 LLM_API_KEY 等

docker compose up -d
# 访问 http://localhost
```

---

## 环境变量

编辑 `backend/.env`（参考 `.env.example`）：

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `LLM_API_KEY` | LLM 服务 API Key | （必填） |
| `LLM_BASE_URL` | API Base URL | `https://api.deepseek.com` |
| `LLM_MODEL` | 模型名称 | `deepseek-chat` |
| `EMBEDDING_MODEL` | 嵌入模型（本地） | `BAAI/bge-m3` |
| `RERANKER_MODEL` | 重排序模型（本地） | `BAAI/bge-reranker-v2-m3` |
| `DEBUG` | 调试模式 | `false` |

---

## API 接口

启动后访问 `http://localhost:8000/docs` 查看完整 Swagger 文档。主要接口：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/chat/stream` | 流式对话（SSE） |
| `GET/POST` | `/api/words` | 词库查询与添加 |
| `POST` | `/api/exercises/generate` | 练习题生成 |
| `POST` | `/api/tts` | 文字转语音 |
| `GET` | `/api/dashboard` | 学习统计 |
| `GET` | `/health` | 健康检查 |

---

## 测试

```bash
cd backend
pytest tests/test_api.py -v
pytest tests/test_rag_evaluation.py -v
```

---

## 开发说明

- **SSE 流式传输**：后端将换行符转义为 `\\n` 保持单行帧格式，前端接收后还原，避免 SSE 帧解析错误（详见 [QA.md](QA.md)）
- **模型预加载**：嵌入模型与重排序模型在应用启动时加载，避免首次请求延迟
- **异步架构**：全链路 async/await，数据库使用 aiosqlite，HTTP 使用 httpx/aiohttp
