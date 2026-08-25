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
