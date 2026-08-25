<template>
  <div class="tutor-layout">
    <!-- Mobile sidebar backdrop -->
    <div class="sidebar-overlay" :class="{ active: showSidebar }" @click="showSidebar = false" />

    <!-- Sidebar: conversation list -->
    <aside class="sidebar" :class="{ 'sidebar-open': showSidebar }">
      <div class="sidebar-header">
        <el-button type="primary" @click="newChat" :icon="Plus" size="small">新对话</el-button>
        <el-icon class="sidebar-close" @click="showSidebar = false"><Close /></el-icon>
      </div>
      <div class="conv-list">
        <div
          v-for="conv in chatStore.conversations"
          :key="conv.id"
          class="conv-item"
          :class="{ active: chatStore.currentConvId === conv.id }"
          @click="selectConv(conv.id)"
        >
          <span class="conv-title">{{ conv.title }}</span>
          <el-icon class="conv-delete" @click.stop="deleteConv(conv.id)"><Delete /></el-icon>
        </div>
      </div>
    </aside>

    <!-- Main chat area -->
    <main class="chat-main">
      <div class="messages" ref="messagesEl">
        <!-- Mobile: sidebar toggle button -->
        <button class="sidebar-toggle-btn" @click="showSidebar = true" title="对话列表">
          <el-icon size="18"><List /></el-icon>
        </button>

        <div v-if="!chatStore.messages.length" class="empty-state">
          <img src="/logo-En.png" alt="logo" style="width:100px;height:100px;object-fit:contain;" />
          <h2 class="empty-title">你好！我是你的 AI 英语老师</h2>
          <p class="empty-sub">有任何英语问题都可以问我</p>
          <div class="empty-suggestions">
            <div class="suggestion-chip" @click="inputText = '坚持是什么意思？'">坚持是什么意思？</div>
            <div class="suggestion-chip" @click="inputText = '帮我造一个用 persist 的句子'">帮我造一个用 persist 的句子</div>
            <div class="suggestion-chip" @click="inputText = '列举10个表示开心的英文单词'">列举10个表示开心的英文单词</div>
            <div class="suggestion-chip" @click="inputText = '翻译：知识是力量'">翻译：知识是力量</div>
          </div>
        </div>

        <div
          v-for="(msg, idx) in chatStore.messages"
          :key="idx"
          class="message-row"
          :class="msg.role"
        >
          <div class="avatar">{{ msg.role === 'user' ? '你' : 'AI' }}</div>
          <div class="bubble">
            <MarkdownContent :content="msg.content" :streaming="msg.streaming" />
            <span v-if="msg.streaming" class="cursor">▌</span>

            <el-tag v-if="msg.intent" size="small" type="info" class="intent-tag">
              {{ intentLabel(msg.intent) }}
            </el-tag>

            <div v-if="msg.sources?.length" class="rag-sources">
              <div class="sources-title">RAG 来源</div>
              <div v-for="(src, si) in msg.sources" :key="si" class="source-card">
                <div class="source-word">
                  {{ src.word }}
                  <span v-if="src.phonetic" class="phonetic">{{ src.phonetic }}</span>
                  <el-icon class="tts-btn" @click="playTTS(src.word)"><Microphone /></el-icon>
                </div>
                <div v-if="src.translation" class="source-def">{{ src.translation }}</div>
                <div class="source-meta">
                  <el-tag size="small">{{ src.source }}</el-tag>
                  <span class="score">Score: {{ src.retrieval_score.toFixed(2) }}</span>
                  <el-button size="small" type="success" link @click="saveWord(src.word)">+生词本</el-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Input area -->
      <div class="input-area">
        <div class="input-box" :class="{ disabled: chatStore.isStreaming }">
          <input
            v-model="inputText"
            class="chat-input"
            placeholder="发消息..."
            :disabled="chatStore.isStreaming"
            @keyup.enter.exact="sendMessage"
          />
          <div class="input-actions">
            <button
              class="action-btn"
              :class="{ recording: isRecording, transcribing: isTranscribing }"
              @click="toggleVoice"
              :disabled="isTranscribing"
              :title="isRecording ? '点击停止录音' : isTranscribing ? '识别中...' : '语音输入'"
            >
              <el-icon size="18"><Microphone /></el-icon>
            </button>
            <button
              class="action-btn send-btn"
              @click="sendMessage"
              :disabled="chatStore.isStreaming || !inputText.trim()"
              title="发送"
            >
              <el-icon size="18"><Promotion /></el-icon>
            </button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue'
import { Plus, Delete, Microphone, Promotion, List, Close } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useChatStore } from '../stores/chat'
import { useUserStore } from '../stores/user'
import { saveWord as apiSaveWord } from '../api'
import MarkdownContent from '../components/MarkdownContent.vue'
import { transcribeAudio } from '../api'

const chatStore = useChatStore()
const userStore = useUserStore()
const inputText = ref('')
const messagesEl = ref<HTMLElement>()
const isRecording = ref(false)
const isTranscribing = ref(false)
const showSidebar = ref(false)
let mediaRecorder: MediaRecorder | null = null
let audioChunks: Blob[] = []
let activeStream: MediaStream | null = null
let activeAudioCtx: AudioContext | null = null

async function toggleVoice() {
  if (isRecording.value) {
    mediaRecorder?.stop()
    return
  }

  try {
    const permStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    permStream.getTracks().forEach(t => t.stop())

    const devices = await navigator.mediaDevices.enumerateDevices()
    const inputs = devices.filter(d => d.kind === 'audioinput')
    const preferred = inputs.find(d => {
      const label = d.label.toLowerCase()
      return !label.includes('virtual') && !label.includes('todesk') && !label.includes('voicemeeter')
    }) ?? inputs[0]

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: preferred?.deviceId ? { deviceId: { exact: preferred.deviceId } } : true,
    })
    activeStream = stream

    const audioCtx = new AudioContext()
    activeAudioCtx = audioCtx
    const source = audioCtx.createMediaStreamSource(stream)
    const gain = audioCtx.createGain()
    gain.gain.value = 5
    const dest = audioCtx.createMediaStreamDestination()
    source.connect(gain)
    gain.connect(dest)

    const recorder = new MediaRecorder(dest.stream, { mimeType: 'audio/webm' })
    mediaRecorder = recorder
    audioChunks = []

    recorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunks.push(e.data) }

    recorder.onstop = async () => {
      isRecording.value = false
      activeStream?.getTracks().forEach(t => t.stop())
      activeAudioCtx?.close()

      const blob = new Blob(audioChunks, { type: 'audio/webm' })
      isTranscribing.value = true
      try {
        const { transcript } = await transcribeAudio(blob)
        if (transcript) inputText.value += transcript
        else ElMessage.warning('未识别到语音内容，请重试')
      } catch {
        ElMessage.error('语音识别失败，请检查后端服务')
      } finally {
        isTranscribing.value = false
      }
    }

    recorder.start()
    isRecording.value = true
  } catch (err: any) {
    ElMessage.error('无法访问麦克风：' + (err.message ?? err))
  }
}

onMounted(async () => {
  await chatStore.loadConversations(userStore.userId)
})

async function scrollToBottom() {
  await nextTick()
  if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
}

watch(() => chatStore.messages.length, scrollToBottom)

watch(() => {
  const last = chatStore.messages[chatStore.messages.length - 1]
  return last?.streaming ? last.content.length : 0
}, scrollToBottom)

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || chatStore.isStreaming) return
  inputText.value = ''
  await chatStore.sendMessage(userStore.userId, text)
  await chatStore.loadConversations(userStore.userId)
}

async function selectConv(id: number) {
  await chatStore.loadMessages(userStore.userId, id)
  showSidebar.value = false
}

async function deleteConv(id: number) {
  await chatStore.deleteConv(id)
}

function newChat() {
  chatStore.newConversation()
  showSidebar.value = false
}

async function saveWord(word: string) {
  await apiSaveWord(userStore.userId, word)
  ElMessage.success(`已添加 "${word}" 到生词本`)
}

function playTTS(word: string) {
  if (!window.speechSynthesis) {
    ElMessage.error('浏览器不支持语音合成')
    return
  }
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(word)
  utterance.lang = 'en-US'
  utterance.rate = 0.9
  window.speechSynthesis.speak(utterance)
}

function intentLabel(intent: string): string {
  const map: Record<string, string> = {
    word_lookup: '单词查询',
    exercise: '练习',
    translate: '翻译',
    rewrite: '改写',
    vocabulary: '生词本',
    general_chat: '对话',
  }
  return map[intent] || intent
}
</script>

<style scoped>
.tutor-layout {
  display: flex;
  height: 100%;
  position: relative;
}

/* ── Sidebar ── */
.sidebar {
  width: 220px;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  background: #f7f8fa;
  flex-shrink: 0;
}

.sidebar-header {
  padding: 12px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  gap: 8px;
}

.sidebar-header .el-button { flex: 1; }

.sidebar-close { display: none; cursor: pointer; color: #909399; font-size: 18px; }
.sidebar-close:hover { color: #303133; }

.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.conv-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  cursor: pointer;
  border-radius: 6px;
  margin: 2px 6px;
  transition: background 0.2s;
}

.conv-item:hover { background: #ecf5ff; }
.conv-item.active { background: #d9ecff; color: #409eff; }
.conv-title { flex: 1; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conv-delete { color: #c0c4cc; margin-left: 6px; }
.conv-delete:hover { color: #f56c6c; }

/* ── Chat main ── */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  align-items: center;
  overflow: auto;
  position: relative;
}

.messages {
  flex: 1;
  padding: 24px 32px 100px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
  max-width: 900px;
}

/* Mobile sidebar toggle (hidden on desktop) */
.sidebar-toggle-btn {
  display: none;
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 10;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 50%;
  width: 36px;
  height: 36px;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  align-items: center;
  justify-content: center;
  color: #606266;
  transition: box-shadow 0.2s;
}

.sidebar-toggle-btn:hover { box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15); }

/* Sidebar overlay backdrop (desktop: invisible + inert) */
.sidebar-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0);
  pointer-events: none;
  z-index: 199;
  transition: background 0.3s;
}

/* ── Empty state ── */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #909399;
  gap: 8px;
  padding-bottom: 60px;
  padding-top: 20px;
}

.empty-title { margin: 8px 0 4px; font-size: 20px; font-weight: 600; color: #303133; }
.empty-sub { margin: 0 0 20px; font-size: 14px; color: #909399; }

.empty-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  max-width: 560px;
}

.suggestion-chip {
  padding: 8px 16px;
  background: #ecf5ff;
  border: 1px solid #b3d8ff;
  border-radius: 20px;
  font-size: 13px;
  color: #409eff;
  cursor: pointer;
  transition: all 0.2s;
}

.suggestion-chip:hover { background: #409eff; color: #fff; border-color: #409eff; }

/* ── Messages ── */
.message-row {
  display: flex;
  gap: 12px;
  max-width: 800px;
}

.message-row.user { align-self: flex-end; flex-direction: row-reverse; }

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #409eff;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  flex-shrink: 0;
}

.message-row.user .avatar { background: #67c23a; }

.bubble {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  padding: 12px 16px;
  max-width: 680px;
  position: relative;
}

.message-row.user .bubble { background: #ecf5ff; border-color: #b3d8ff; }

.content { line-height: 1.7; }
.cursor { animation: blink 1s infinite; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }

.intent-tag { margin-top: 8px; }

.rag-sources { margin-top: 12px; border-top: 1px dashed #e4e7ed; padding-top: 10px; }
.sources-title { font-size: 12px; color: #909399; margin-bottom: 8px; font-weight: 600; }

.source-card { background: #f5f7fa; border-radius: 8px; padding: 8px 12px; margin-bottom: 6px; }

.source-word { font-weight: 600; color: #303133; display: flex; align-items: center; gap: 6px; }
.phonetic { font-size: 12px; color: #606266; font-weight: normal; }
.tts-btn { cursor: pointer; color: #409eff; }
.tts-btn:hover { color: #337ecc; }
.source-def { font-size: 13px; color: #606266; margin: 4px 0; }

.source-meta { display: flex; align-items: center; gap: 8px; margin-top: 4px; flex-wrap: wrap; }
.score { font-size: 12px; color: #909399; }

/* ── Input area ── */
.input-area {
  padding: 16px 32px 24px;
  background: #fff;
  width: 100%;
  max-width: 900px;
  position: fixed;
  bottom: 0;
}

.input-box {
  display: flex;
  align-items: center;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 28px;
  box-shadow: 0 2px 16px rgba(0, 0, 0, 0.08);
  padding: 10px 12px 10px 20px;
  transition: box-shadow 0.2s, border-color 0.2s;
}

.input-box:focus-within { border-color: #409eff; box-shadow: 0 4px 20px rgba(64, 158, 255, 0.15); }
.input-box.disabled { background: #f5f7fa; opacity: 0.7; }

.chat-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 15px;
  color: #303133;
  line-height: 1.5;
  min-width: 0;
}

.chat-input::placeholder { color: #c0c4cc; }

.input-actions { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: #909399;
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}

.action-btn:hover { background: #f0f2f5; color: #409eff; }
.action-btn.recording { background: #fef0f0; color: #f56c6c; animation: pulse 1s infinite; }
.action-btn.transcribing { background: #f0f9eb; color: #67c23a; animation: pulse 1s infinite; cursor: not-allowed; }

.send-btn { background: #409eff; color: #fff; }
.send-btn:hover:not(:disabled) { background: #337ecc; color: #fff; }
.send-btn:disabled { background: #c0c4cc; cursor: not-allowed; }

@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

/* ── Mobile styles ── */
@media (max-width: 767px) {
  .sidebar {
    position: fixed;
    top: 50px;
    left: 0;
    /* 50px header + bottom nav height */
    height: calc(100dvh - 50px - 56px - env(safe-area-inset-bottom));
    width: 260px;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
    z-index: 200;
    box-shadow: 4px 0 12px rgba(0, 0, 0, 0.15);
  }

  .sidebar.sidebar-open {
    transform: translateX(0);
  }

  .sidebar-close { display: flex; }

  .sidebar-overlay {
    display: block;
  }

  .sidebar-overlay.active {
    background: rgba(0, 0, 0, 0.4);
    pointer-events: auto;
  }

  .sidebar-toggle-btn { display: flex; }

  .chat-main { width: 100%; }

  .messages {
    padding: 56px 12px 120px; /* top: space for toggle btn; bottom: input area + nav */
  }

  .empty-state { padding-top: 40px; }

  .message-row { max-width: 100%; }

  .bubble { max-width: calc(100vw - 80px); }

  .input-area {
    padding: 8px 12px;
    max-width: 100%;
    left: 0;
    right: 0;
    bottom: calc(56px + env(safe-area-inset-bottom));
  }

  .empty-title { font-size: 17px; text-align: center; }
  .empty-sub { font-size: 13px; text-align: center; }

  .suggestion-chip { font-size: 12px; padding: 7px 13px; }
}
</style>
