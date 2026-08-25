<template>
  <div class="page-container">
    <div class="page-header">
      <div class="header-actions">
        <el-input
          v-model="searchText"
          placeholder="搜索单词"
          :prefix-icon="Search"
          clearable
          class="vocab-search"
          @input="loadWords"
        />
        <el-select v-model="sortBy" @change="loadWords" class="vocab-sort">
          <el-option label="添加时间" value="created_at" />
          <el-option label="掌握度" value="mastery_score" />
          <el-option label="复习次数" value="review_count" />
        </el-select>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :sm="12" :md="8" :lg="6" v-for="uw in userWords" :key="uw.id">
        <el-card class="word-card" shadow="hover">
          <div class="word-header">
            <span class="word-text">{{ uw.word.word }}</span>
            <el-icon class="tts-icon" @click="speak(uw.word.word)"><Microphone /></el-icon>
          </div>

          <div class="phonetic" v-if="uw.word.phonetic">{{ uw.word.phonetic }}</div>

          <div class="translation">{{ uw.word.translation || uw.word.definition }}</div>

          <div class="mastery-row">
            <span class="mastery-label">掌握度</span>
            <el-progress
              :percentage="uw.mastery_score"
              :color="masteryColor(uw.mastery_score)"
              :stroke-width="8"
              style="flex:1; margin-left: 8px"
            />
          </div>

          <div class="stats-row">
            <span class="stat green">✓ {{ uw.correct_count }}</span>
            <span class="stat red">✗ {{ uw.wrong_count }}</span>
            <span class="stat gray">复习 {{ uw.review_count }}</span>
          </div>

          <div class="next-review" v-if="uw.next_review_at">
            下次复习: {{ formatDate(uw.next_review_at) }}
          </div>

          <el-button
            type="danger"
            size="small"
            link
            @click="removeWord(uw.word.word)"
            style="margin-top: 8px"
          >移出生词本</el-button>
        </el-card>
      </el-col>
    </el-row>

    <el-empty v-if="!userWords.length && !loading" description="暂无生词，去 AI Tutor 收藏单词吧" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Search, Microphone } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getVocabulary, removeWord as apiRemoveWord, getTTSUrl } from '../api'
import { useUserStore } from '../stores/user'

const userStore = useUserStore()
const userWords = ref<any[]>([])
const searchText = ref('')
const sortBy = ref('created_at')
const loading = ref(false)

onMounted(loadWords)

async function loadWords() {
  loading.value = true
  const res = await getVocabulary(userStore.userId, { search: searchText.value, sort_by: sortBy.value })
  userWords.value = res.data
  loading.value = false
}

async function removeWord(word: string) {
  await apiRemoveWord(userStore.userId, word)
  ElMessage.success(`已移除 "${word}"`)
  await loadWords()
}

function speak(word: string) {
  new Audio(getTTSUrl(word)).play()
}

function masteryColor(score: number): string {
  if (score >= 80) return '#67c23a'
  if (score >= 50) return '#e6a23c'
  return '#f56c6c'
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()}`
}
</script>

<style scoped>
.page-container { padding: 32px 40px; max-width: 1280px; margin: 0 auto; width: 100%; }

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 12px;
}

.header-actions { display: flex; gap: 12px; flex-wrap: wrap; }

.vocab-search { width: 220px; }
.vocab-sort { width: 140px; }

.word-card { margin-bottom: 16px; }

.word-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.word-text { font-size: 22px; font-weight: 700; color: #303133; }

.tts-icon { cursor: pointer; color: #409eff; font-size: 18px; }
.tts-icon:hover { color: #337ecc; }

.phonetic { color: #909399; font-size: 13px; margin: 4px 0; }

.translation { color: #606266; font-size: 14px; margin: 8px 0; min-height: 40px; }

.mastery-row {
  display: flex;
  align-items: center;
  margin: 8px 0;
}

.mastery-label { font-size: 12px; color: #909399; white-space: nowrap; }

.stats-row { display: flex; gap: 12px; margin: 6px 0; }

.stat { font-size: 13px; }
.stat.green { color: #67c23a; }
.stat.red { color: #f56c6c; }
.stat.gray { color: #909399; }

.next-review { font-size: 12px; color: #909399; }

@media (max-width: 767px) {
  .page-container { padding: 16px; }
  .page-header { flex-direction: column; align-items: flex-start; }
  .vocab-search { width: 100%; }
  .vocab-sort { width: 100%; }
  .header-actions { width: 100%; }
}
</style>
