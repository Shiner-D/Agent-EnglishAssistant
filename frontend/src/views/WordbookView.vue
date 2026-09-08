<template>
  <div class="wordbook-view">
    <!-- Level tabs -->
    <div class="level-tabs">
      <button v-for="level in store.levels" :key="level.id"
        :class="['level-btn', { active: store.currentLevelId === level.id }]" @click="selectLevel(level.id)">
        {{ level.name }}
      </button>
    </div>

    <!-- Progress bar -->
    <div v-if="currentProgress" class="progress-bar-section">
      <div class="progress-labels">
        <span>已掌握 {{ currentProgress.mastered }} / {{ currentProgress.total }}</span>
        <span class="progress-pct">{{ masteredPct }}%</span>
      </div>
      <el-progress :percentage="masteredPct" :stroke-width="8" :show-text="false" color="#67c23a"
        define-back-color="#e4e7ed" />
      <div class="progress-sub">
        已学习 {{ currentProgress.learned }} 词 &nbsp;·&nbsp; 共 {{ currentProgress.total }} 词
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="!store.levels.length && !store.loading" class="empty-state">
      <el-empty description="暂无单词数据，请先导入单词表">
        <template #description>
          <p>暂无单词数据</p>
          <p class="empty-hint">运行 <code>python scripts/import_wordlist.py</code> 导入单词表后刷新</p>
        </template>
      </el-empty>
    </div>

    <!-- Word list -->
    <el-row v-loading="store.loading" :gutter="16">
      <el-col :xs="24" :sm="12" :md="8" :lg="6" v-for="word in store.words" :key="word.id" class="word-col">
        <div :class="['word-card', `status-${word.status ?? 'unlearned'}`]">
          <!-- Card header -->
          <div class="card-header">
            <div class="word-main">
              <span class="word-text">{{ word.word }}</span>
              <el-icon class="tts-icon" @click.stop="speak(word.word)"><Headset /></el-icon>
              <span v-if="word.phonetic" class="phonetic">/{{ word.phonetic }}/</span>
              <el-tag v-if="word.pos" size="small" type="info" class="pos-tag">{{ word.pos }}</el-tag>
            </div>
            <el-tag :type="statusTagType(word.status)" size="small" class="status-tag">
              {{ statusLabel(word.status) }}
            </el-tag>
          </div>

          <!-- Image -->
          <div v-if="word.image_path" class="card-image">
            <img :src="imageUrl(word.image_path)" :alt="word.word" />
          </div>

          <!-- Definition -->
          <div v-if="word.definition" class="definition">{{ word.definition }}</div>

          <!-- Mnemonic -->
          <div v-if="word.mnemonic" class="mnemonic">
            <div v-for="section in parseMnemonic(word.mnemonic)" :key="section.label" class="mnemonic-section">
              <span class="mnemonic-label">{{ section.label }}</span>
              <span class="mnemonic-text">{{ section.content }}</span>
            </div>
          </div>

          <!-- Example -->
          <div v-if="word.example" class="example">
            <div class="example-en-row">
              <el-icon class="tts-icon tts-icon--sm" @click.stop="speak(word.example)">
                <Headset />
              </el-icon>
              <span class="example-en">{{ word.example }}</span>
            </div>
            <span v-if="word.example_translation" class="example-zh">{{ word.example_translation }}</span>
          </div>

          <!-- Status buttons -->
          <div class="card-actions">
            <button v-for="s in statuses" :key="s.value"
              :class="['action-btn', s.value, { active: (word.status ?? 'unlearned') === s.value }]"
              @click="setStatus(word, s.value)">
              {{ s.label }}
            </button>
          </div>
        </div>
      </el-col>
    </el-row>


    <!-- Load more -->
    <div v-if="store.hasMore && store.words.length > 0" class="load-more">
      <el-button @click="loadMore" :loading="store.loading" plain>加载更多</el-button>
      <el-button @click="testError">测试错误</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { Headset } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useWordbookStore } from '../stores/wordbook'
import { useUserStore } from '../stores/user'

function parseMnemonic(text: string): { label: string; content: string }[] {
  const pattern = /【([^】]+)】([^【]*)/g
  const sections: { label: string; content: string }[] = []
  let match
  while ((match = pattern.exec(text)) !== null) {
    sections.push({ label: match[1], content: match[2].trim() })
  }
  return sections.length ? sections : [{ label: '助记', content: text.trim() }]
}

const store = useWordbookStore()
const userStore = useUserStore()

const BASE_URL = import.meta.env.VITE_API_URL || ''

const statuses = [
  { value: 'unlearned', label: '未学' },
  { value: 'learning', label: '学习中' },
  { value: 'mastered', label: '已掌握' },
]

const currentProgress = computed(() =>
  store.currentLevelId ? store.getLevelProgress(store.currentLevelId) : null
)

const masteredPct = computed(() => {
  const p = currentProgress.value
  if (!p || !p.total) return 0
  return Math.round((p.mastered / p.total) * 100)
})

function imageUrl(path: string) {
  return `${BASE_URL}/static/wordbook_images/${path}`
}


function statusLabel(status?: string) {
  return { unlearned: '未学', learning: '学习中', mastered: '已掌握' }[status ?? 'unlearned'] ?? '未学'
}

function statusTagType(status?: string) {
  return { unlearned: 'info', learning: 'warning', mastered: 'success' }[status ?? 'unlearned'] ?? 'info'
}

async function selectLevel(levelId: number) {
  store.currentLevelId = levelId
  await store.loadWords(levelId, 1)
}

async function setStatus(word: any, status: string) {
  if (!userStore.userId) return
  await store.updateStatus(userStore.userId, word.id, status)
}

async function loadMore() {
  if (!store.currentLevelId) return
  await store.loadWords(store.currentLevelId, store.currentPage + 1)
}

function testError() {
  throw new Error('This is a test error for Sentry.')
}

function speak(word: string) {
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

onMounted(async () => {
  await store.loadLevels()
  if (userStore.userId) {
    await store.loadProgress(userStore.userId)
  }
  if (store.currentLevelId) {
    await store.loadWords(store.currentLevelId, 1)
  }
})

watch(
  () => store.currentLevelId,
  async (id) => {
    if (id) await store.loadWords(id, 1)
  }
)
</script>

<style scoped>
.wordbook-view {
  margin: 0 auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Level tabs */
.level-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.level-btn {
  padding: 6px 16px;
  border: 1px solid #dcdfe6;
  border-radius: 20px;
  background: #fff;
  color: #606266;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.level-btn:hover {
  border-color: #409eff;
  color: #409eff;
}

.level-btn.active {
  background: #409eff;
  border-color: #409eff;
  color: #fff;
}

/* Progress */
.progress-bar-section {
  background: #fff;
  border-radius: 10px;
  padding: 14px 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.progress-labels {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
}

.progress-pct {
  font-weight: 600;
  color: #67c23a;
}

.progress-sub {
  font-size: 12px;
  color: #909399;
  margin-top: 6px;
}

/* Empty */
.empty-state {
  text-align: center;
  padding: 40px 0;
}

.empty-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.empty-hint code {
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
}

/* Word list */
.word-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 60px;
}

.word-col {
  height: 370px;
  margin-bottom: 16px;
}

.word-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  border-left: 4px solid #dcdfe6;
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: 100%;
  position: relative;
}

.word-card.status-learning {
  border-left-color: #e6a23c;
}

.word-card.status-mastered {
  border-left-color: #67c23a;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.word-main {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.word-text {
  font-size: 20px;
  font-weight: 700;
  color: #303133;
}

.tts-icon {
  cursor: pointer;
  color: #409eff;
  font-size: 16px;
  flex-shrink: 0;
}

.tts-icon:hover {
  color: #337ecc;
}

.phonetic {
  font-size: 13px;
  color: #909399;
}

.pos-tag {
  flex-shrink: 0;
}

.status-tag {
  flex-shrink: 0;
}

.card-image img {
  width: 100%;
  max-height: 180px;
  object-fit: cover;
  border-radius: 8px;
}

.definition {
  font-size: 15px;
  color: #303133;
  font-weight: 500;
}

.mnemonic {
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: #f5f0ff;
  border-radius: 8px;
  padding: 10px 12px;
}

.mnemonic-section {
  display: flex;
  gap: 6px;
  font-size: 13px;
  line-height: 1.6;
  color: #4a3570;
}

.mnemonic-label {
  flex-shrink: 0;
  font-weight: 600;
  color: #7c4dcc;
  white-space: nowrap;
}

.mnemonic-text {
  color: #4a3570;
}

.example {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.example-en-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.example-en {
  font-size: 13px;
  color: #409eff;
  font-style: italic;
}

.tts-icon--sm {
  font-size: 13px;
  flex-shrink: 0;
}

.example-zh {
  font-size: 12px;
  color: #909399;
}

/* Status buttons */
.card-actions {
  display: flex;
  gap: 8px;
  position: absolute;
  bottom: 16px;
  width: calc(100% - 32px);
}

.action-btn {
  flex: 1;
  padding: 6px 0;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  border: 1px solid #dcdfe6;
  background: #f5f7fa;
  color: #606266;
  transition: all 0.15s;
}

.action-btn:hover {
  opacity: 0.85;
}

.action-btn.unlearned.active {
  background: #f5f7fa;
  border-color: #909399;
  color: #303133;
  font-weight: 600;
}

.action-btn.learning.active {
  background: #fdf6ec;
  border-color: #e6a23c;
  color: #e6a23c;
  font-weight: 600;
}

.action-btn.mastered.active {
  background: #f0f9eb;
  border-color: #67c23a;
  color: #67c23a;
  font-weight: 600;
}

/* Load more */
.load-more {
  text-align: center;
  padding: 8px 0;
}

/* Mobile */
@media (max-width: 767px) {
  .wordbook-view {
    padding: 12px;
  }

  .word-text {
    font-size: 18px;
  }
}
</style>
