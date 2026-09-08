# Q&A — 问题与解决方案记录

---

## Q1: 流式输出过程中 Markdown 格式不渲染，完成后才正常显示

- 日期: 2026-08-18
- 文件: `frontend/src/components/MarkdownContent.vue` · `frontend/src/stores/chat.ts` · `backend/app/api/chat.py`

### 现象

- 流式输出期间：内容挤成一行，`##`、`- `、`---`、`**` 等语法符号以原始字符显示
- 输出完成后：Markdown 格式正常渲染

### 根本原因（两个叠加问题）

**问题一：SSE 帧格式被换行符破坏（主因）**

后端 `_sse_event` 将 token 直接拼入 SSE 格式字符串，当 token 本身含真实换行符（`\n`）时，SSE 消息变成多行 `data:` 字段：

```text
event: token
data: 第一行
line2         ← 前端 SSE 解析器跳过（不以 data: 开头）
```

前端 SSE 解析器按行切分，`line2` 不以 `data:` 开头被忽略，换行符彻底丢失。所有内容挤成一行，块级 Markdown 语法（标题、列表、分隔线）无法被 `marked.parse` 识别。

**问题二：未闭合 Markdown 语法（次因）**

流式输出中途，`marked.parse` 收到未完整的 Markdown 构造：

| 流式中 | 渲染结果 |
| --- | --- |
| `**加粗文字` | `**加粗文字`（原始星号） |
| ` ``` python\ncode` | 代码块未闭合，后续内容全被当作代码 |

### 解决方案

#### Fix 1 — 后端转义换行符 (`backend/app/api/chat.py`)

在 `_sse_event` 中，对字符串类型的 data 将真实换行符转义为字面量 `\n`：

```python
async def _sse_event(event: str, data: dict | str) -> str:
    if isinstance(data, dict):
        data = json.dumps(data, ensure_ascii=False)
    else:
        data = data.replace('\n', '\\n')  # 保持 SSE 单行帧格式
    return f"event: {event}\ndata: {data}\n\n"
```

#### Fix 2 — 前端反转义换行符 (`frontend/src/stores/chat.ts`)

收到 token 时将 `\n` 还原为真实换行符：

```typescript
if (event === 'token') {
  msg.content += rawData.replace(/\\n/g, '\n')
  return
}
```

#### Fix 3 — 补全未闭合 Markdown 语法 (`frontend/src/components/MarkdownContent.vue`)

streaming 状态下，解析前先补全未闭合构造：

```typescript
function closeIncompleteMarkdown(content: string): string {
  // 优先处理代码块（破坏力最大）
  const fenceMatches = [...content.matchAll(/^(`{3,})/gm)]
  const insideCodeFence = fenceMatches.length % 2 !== 0
  if (insideCodeFence) {
    return content + '\n' + fenceMatches[fenceMatches.length - 1][1]
  }
  // 补全最后一行未闭合的行内代码
  const lastLine = content.slice(content.lastIndexOf('\n') + 1)
  const singleBackticks = (lastLine.match(/(?<!`)`(?!`)/g) || []).length
  if (singleBackticks % 2 !== 0) content += '`'
  // 补全未闭合加粗
  const boldCount = (content.match(/\*\*/g) || []).length
  if (boldCount % 2 !== 0) content += '**'
  return content
}

const sanitized = computed(() => {
  const raw = props.streaming ? closeIncompleteMarkdown(props.content) : props.content
  return DOMPurify.sanitize(marked.parse(raw, { gfm: true, breaks: true }) as string)
})
```

### 注意事项

- Fix 1 + Fix 2 必须配对使用，单独修改任意一侧会导致 `\n` 被当作字面量显示
- Fix 3 不处理斜体 `*`，因为普通文本中的乘号等会产生大量误判
- 流式结束（`streaming: false`）时直接使用原始内容，不做任何补全处理

---

## Q2: 语音输入 transcript 为空字符串 / 功能完全不可用

- 日期: 2026-08-21
- 文件: `frontend/src/views/TutorView.vue` · `frontend/src/api/index.ts` · `backend/app/api/stt.py`

### Q2 现象

- 方案一（Web Speech API）：`onresult` 不触发，或触发后 `transcript` 为空字符串
- 方案二（自定义管线）：识别结果为繁体字；接口耗时 ~3.6s

### Q2 根本原因链

#### 阶段一：Web Speech API 完全失效

| 症状 | 原因 |
| --- | --- |
| `onstart → onend`，无 `onresult` | `continuous: false` 默认静默超时极短，在用户开口前就结束 |
| `onresult` 触发但 `transcript = ""` | ToDesk Virtual Audio 采集到的音量 RMS ≈ 0，低于语音检测阈值 |

Web Speech API 的根本限制：**无法指定输入设备，无法控制增益**，在虚拟音频设备场景下无解。

#### 阶段二：切换自定义管线后的残留问题

1. `enumerateDevices()` 在权限授予前返回的 `label` 全为空字符串，设备过滤器失效（始终选中 `inputs[0]`，可能仍是虚拟设备）
2. `model.transcribe()` 是同步 CPU 密集操作，直接在 FastAPI async 端点调用会阻塞整个事件循环

### Q2 解决方案

#### 放弃 Web Speech API，改用自定义音频管线

```text
getUserMedia（指定设备）
  → AudioContext + GainNode（5× 放大）
  → MediaStreamDestinationNode
  → MediaRecorder（录制为 webm）
  → POST /api/stt/transcribe
  → faster-whisper（本地转录）
```

#### Fix 1 — 先请求权限再枚举设备（`TutorView.vue`）

`enumerateDevices()` 只在麦克风权限授予后才填充真实 label，必须先获取权限：

```typescript
// 先触发权限对话框，label 填充后立即停流
const permStream = await navigator.mediaDevices.getUserMedia({ audio: true })
permStream.getTracks().forEach(t => t.stop())

// 此时 label 已有值，过滤可正常工作
const preferred = devices
  .filter(d => d.kind === 'audioinput')
  .find(d => {
    const label = d.label.toLowerCase()
    return !label.includes('virtual') && !label.includes('todesk') && !label.includes('voicemeeter')
  })
```

#### Fix 2 — GainNode 解决虚拟设备音量过低（`TutorView.vue`）

```typescript
const audioCtx = new AudioContext()
const gain = audioCtx.createGain()
gain.gain.value = 5          // 5× 增益
const dest = audioCtx.createMediaStreamDestination()
source.connect(gain)
gain.connect(dest)
const recorder = new MediaRecorder(dest.stream, { mimeType: 'audio/webm' })
```

#### Fix 3 — 后端 STT 端点，阻塞调用移至线程池（`stt.py`）

```python
async def transcribe(audio: UploadFile = File(...)):
    def _run():
        model = _get_model()
        segments, _ = model.transcribe(tmp_path, ...)
        return "".join(s.text for s in segments).strip()

    transcript = await asyncio.to_thread(_run)   # 不阻塞事件循环
```

#### Fix 4 — Whisper 输出繁体字（`stt.py`）

用 `initial_prompt` 偏置 tokenizer 输出简体字：

```python
model.transcribe(
    tmp_path,
    language="zh",
    beam_size=1,
    initial_prompt="以下是普通话的句子，使用简体中文。",
    vad_filter=True,
    condition_on_previous_text=False,
)
```

#### Fix 5 — 接口性能优化（`stt.py`）

| 参数 | 改动 | 收益 |
| --- | --- | --- |
| `beam_size` | 5 → 1（贪心解码） | 最大，-40~60% |
| `vad_filter` | 新增 `True` | 中等，跳过静音段 |
| `condition_on_previous_text` | 新增 `False` | 小幅 |

若仍需更快，可将模型从 `small` 换为 `base`（~1.5s）或 `tiny`（~0.5s）。

### Q2 依赖

```bash
pip install faster-whisper==1.1.1   # 注意是双等号 ==
```

### Q2 注意事项

- `faster-whisper` 依赖 `ffmpeg`，需提前确认系统已安装（`ffmpeg -version`）
- Whisper `small` 模型首次运行自动下载 ~244MB，需要网络
- `vad_filter=True` 对极短（<0.5s）的音频片段可能误判为静音，导致空结果

---

## Q3: 手机访问局域网地址后功能异常（无法登录 / 对话无响应）

- 日期: 2026-08-25
- 文件: `frontend/vite.config.ts` · `frontend/.env` · `frontend/src/api/index.ts` · `frontend/src/stores/chat.ts` · `backend/app/core/config.py` · `backend/app/main.py`

### Q3 现象

- 手机通过 `http://192.168.1.x:5173` 访问，首页正常显示
- 输入用户名点击"开始学习"无反应（静默失败）
- 加上错误提示后显示 `Network Error`
- 登录成功后，发送消息无任何回复

### Q3 根本原因链

共四个叠加问题：

| # | 问题 | 表现 |
| - | ---- | ---- |
| 1 | Vite 只监听 `127.0.0.1` | 局域网设备无法访问 5173 端口 |
| 2 | API 地址硬编码 `localhost:8000` | 手机上 `localhost` 指向手机自身，请求直接失败 |
| 3 | 后端 CORS 白名单未包含局域网 origin | 浏览器跨域请求被拒绝，axios 显示 `Network Error` |
| 4 | `chat.ts` 独立维护了同一个 `localhost:8000` | 登录可以进去，但对话仍然打到手机自身 |

### Q3 解决方案

#### Fix 1 — Vite 监听所有网卡 (`vite.config.ts`)

```typescript
export default defineConfig({
  server: {
    host: true,   // 等价于 '0.0.0.0'
  },
})
```

#### Fix 2 — API 地址改为动态 hostname (`api/index.ts` · `stores/chat.ts`)

两个文件都需要修改，否则登录通了，对话还是打到 `localhost`：

```typescript
// api/index.ts
const BASE_URL = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`

// stores/chat.ts（sendMessage 函数内）
const API = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`
```

访问 `http://192.168.1.x:5173` 时，`window.location.hostname` 自动返回 `192.168.1.x`，无需手动配置 IP。

#### Fix 3 — 清空 `.env` 中的 `VITE_API_URL` (`frontend/.env`)

`.env` 中的显式赋值优先级高于代码中的 `||` 回退逻辑：

```dotenv
# 改为空值，让代码自动走动态 hostname 逻辑
VITE_API_URL=
```

> **注意**：修改 `.env` 必须重启 Vite（HMR 不处理环境变量变更）。

#### Fix 4 — 后端 CORS 允许所有来源 (`backend/app/core/config.py` · `main.py`)

```python
# config.py
CORS_ORIGINS: list[str] = ["*"]

# main.py — allow_origins=["*"] 时必须关闭 allow_credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,   # ["*"] 与 credentials=True 不兼容
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### Fix 5 — 后端启动命令监听所有网卡

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

默认 `--host 127.0.0.1` 只接受本机请求，局域网设备无法连接。

#### Fix 6 — 添加登录错误提示 (`App.vue`)

原始代码无 try/catch，API 失败时按钮静默无反应，难以定位问题：

```typescript
async function doLogin() {
  if (!loginName.value.trim()) return
  try {
    await userStore.login(loginName.value.trim())
    showLogin.value = false
  } catch (e: any) {
    ElMessage.error('登录失败：' + (e?.message || '无法连接服务器'))
  }
}
```

### Q3 一键启动脚本 (`start.bat`)

为避免每次手动输命令，在项目根目录创建 `start.bat`，双击同时启动前后端：

```bat
@echo off
start "Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\activate && uvicorn app.main:app --host 0.0.0.0 --port 8000"
start "Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
```

### Q3 注意事项

- `allow_origins=["*"]` 仅适合开发环境，生产环境应指定具体域名
- 局域网 IP 可能因 DHCP 变化，动态 hostname 方案无需关心 IP 变动
- Windows 防火墙可能拦截 8000 端口；若手机无法访问 `/health`，执行：

```powershell
New-NetFirewallRule -DisplayName "uvicorn 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

---

## Q4: 生产环境部署到腾讯云轻量服务器（2核4G）的系列问题

- 日期: 2026-08-26
- 涉及文件: `backend/app/rag/embedder.py` · `backend/app/rag/reranker.py` · `backend/app/main.py` · `backend/Dockerfile` · `frontend/Dockerfile` · `docker-compose.yml` · `frontend/src/api/index.ts` · `frontend/src/stores/chat.ts`

---

### Q4-1: 服务器内存不足，本地 AI 模型无法加载

**现象**：2核4G 服务器启动时加载 BGE-M3（~1.2GB）+ reranker（~600MB），合计约 2GB，加上 OS 和应用后内存不足。

**根本原因**：`embedder.py` 和 `reranker.py` 虽然 config 中已预留 API 模式配置项（`EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`），但代码始终走本地加载路径，未实现 API 分支。

**解决方案**：

#### Fix 1 — embedder 支持 API 模式 (`backend/app/rag/embedder.py`)

有 `EMBEDDING_API_KEY` 时走 OpenAI-compatible API（如 SiliconFlow 免费托管 BGE-M3），否则加载本地模型：

```python
@property
def _use_api(self) -> bool:
    return bool(settings.EMBEDDING_API_KEY and settings.EMBEDDING_BASE_URL)

def _embed_via_api(self, texts):
    url = settings.EMBEDDING_BASE_URL.rstrip("/") + "/embeddings"
    headers = {"Authorization": f"Bearer {settings.EMBEDDING_API_KEY}"}
    payload = {"model": settings.EMBEDDING_MODEL, "input": texts}
    with httpx.Client(timeout=60) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
    data = resp.json()["data"]
    data.sort(key=lambda x: x["index"])
    return [item["embedding"] for item in data]
```

#### Fix 2 — reranker 支持禁用 (`backend/app/rag/reranker.py`)

`RERANKER_MODEL` 为空时跳过加载，`rerank()` 直接返回原始排序结果：

```python
@property
def _enabled(self) -> bool:
    return bool(settings.RERANKER_MODEL)

def rerank(self, query, docs, top_k=5):
    if not self._enabled or self._model is None:
        return docs[:top_k]
    ...
```

#### Fix 3 — main.py 按模式选择性预加载

```python
if embedding_service._use_api:
    logger.info(f"Embedding: API mode ({settings.EMBEDDING_BASE_URL})")
else:
    embedding_service._load_local_model()
if reranker._enabled:
    reranker._load_model()
else:
    logger.info("Reranker: disabled.")
```

#### 服务器 `.env` 配置（根目录，供 docker-compose 读取）

```env
LLM_API_KEY=你的DeepSeek密钥
EMBEDDING_API_KEY=你的SiliconFlow密钥
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=BAAI/bge-m3
RERANKER_MODEL=
```

**内存对比**：

| | 改造前 | 改造后 |
| -- | -- | -- |
| BGE-M3 | ~1.2GB | 0（云端） |
| Reranker | ~600MB | 0（关闭） |
| 合计 | ~2.2GB | ~400MB |

> SiliconFlow 注册地址：siliconflow.cn，免费额度足够个人使用。

---

### Q4-2: Docker 构建时 pip 安装失败

**现象**：`ERROR: Could not find a version that satisfies the requirement pydantic==2.9.2 (from versions: none)`

**根本原因**：服务器（国内）访问 PyPI 超时或被限速，`from versions: none` 说明完全连不上。

**解决方案**：在 `backend/Dockerfile` 中改用清华镜像源：

```dockerfile
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn
```

前端 npm 同理，在 `frontend/Dockerfile` 中：

```dockerfile
RUN npm ci --registry=https://registry.npmmirror.com
```

---

### Q4-3: 前端容器启动失败，端口 80 被占用

**现象**：`failed to bind host port 0.0.0.0:80/tcp: address already in use`

**根本原因**：服务器已有其他进程（如系统 nginx）占用 80 端口。

**解决方案**：将 `docker-compose.yml` 前端端口改为 8080：

```yaml
ports:
  - "8080:80"
```

同时在腾讯云轻量服务器**防火墙**中添加 TCP:8080 入站规则（轻量服务器防火墙与云服务器安全组入口不同，在实例详情页的「防火墙」标签下配置）。

---

### Q4-4: 服务器未创建 .env 文件，LLM_API_KEY 未设置并尝试从 HuggingFace 下载模型

**现象**：

```text
WARN: The "LLM_API_KEY" variable is not set. Defaulting to a blank string.
Failed to establish connection to huggingface.co: [Errno 101] Network is unreachable
```

**根本原因**：docker-compose 从**根目录** `.env` 读取变量，但服务器上未创建该文件。同时 HuggingFace 在国内不可访问。

**解决方案**：在服务器 docker-compose.yml 同目录下创建 `.env`（见 Q4-1 配置示例）。

> **注意**：`backend/.env` 是本地开发用的，服务器上 docker-compose 读的是根目录 `.env`，两者互不干扰。

---

### Q4-5: 前端 API 请求直接打 :8000 端口，产生 Mixed Content 警告

**现象**：HTTPS 页面下点击按钮报 `Network Error`，浏览器安全提示"连接不安全"，API 请求打到 `http://IP:8000`。

**根本原因**：`api/index.ts` 和 `stores/chat.ts` 两处 fallback URL 均硬编码为 `http://${window.location.hostname}:8000`，绕过了 nginx 代理，在 HTTPS 页面下触发 Mixed Content 拦截。

**解决方案**：两处均改为空字符串，让请求走相对路径经 nginx 代理：

```typescript
// api/index.ts 和 stores/chat.ts
const BASE_URL = import.meta.env.VITE_API_URL || ''
```

请求路径变为 `/api/...`，由 nginx 代理到后端，浏览器只看到同源 HTTPS 请求。

---

### Q4-6: HTTPS 证书申请失败（.cn 域名 DNSSEC 链路问题）

**现象**：

```text
DNSSEC: DNSKEY Missing: validation failure
DNS problem: query timed out looking up A for xxx.cn
```

**根本原因**：`.cn` 顶级域在 Let's Encrypt 境外解析器上存在 DNSSEC 链路问题，与用户是否主动开启 DNSSEC 无关。DNSPod 免费版无法修复，升级付费也无必要。

**解决方案**：将域名 DNS 迁移到 Cloudflare（免费）：

1. 注册 Cloudflare → Add a Site → 自动导入现有 DNS 记录
2. 获取 Cloudflare NS 地址，在腾讯云域名注册控制台修改 NS 服务器
3. 在 Cloudflare 手动添加子域名 A 记录，**Proxy status 选「DNS only」（灰色云朵）**
4. NS 生效后重新运行 `sudo certbot --nginx -d your.domain.cn`

#### nginx 手动配置 HTTPS（certbot 自动安装失败时）

```nginx
server {
    listen 80;
    server_name english.yourdomain.cn;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name english.yourdomain.cn;

    ssl_certificate /etc/letsencrypt/live/english.yourdomain.cn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/english.yourdomain.cn/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8080/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection '';
        proxy_set_header Host $host;
        proxy_buffering off;
        proxy_read_timeout 300s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/english-tutor /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

### Q4 注意事项

- **本地 vs 生产配置分离**：本地用 `backend/.env`（reranker 开启，本地模型），服务器用根目录 `.env`（API 模式，reranker 关闭），docker-compose `environment:` 覆盖容器内文件，两套互不干扰
- **uvicorn workers 必须为 1**：有本地模型时多 worker 会重复加载导致 OOM
- **轻量服务器防火墙**：入口在实例详情页「防火墙」标签，不同于云服务器的「安全组」
- **Chrome 缓存**：切换 HTTP→HTTPS 后 Chrome 可能缓存旧警告，F12 开发者工具 → 右键刷新 → 「清空缓存并硬性重新加载」

---
