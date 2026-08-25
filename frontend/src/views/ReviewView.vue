<template>
  <div class="page-container">

    <!-- No due words -->
    <div v-if="!loading && !dueWords.length" class="empty-state">
      <el-result icon="success" title="今日复习完成！" sub-title="暂无待复习单词，明天再来吧" />
    </div>

    <!-- Review card -->
    <div v-else-if="currentWord" class="review-card-wrap">
      <div class="progress-bar">
        <el-progress
          :percentage="Math.round(reviewedCount / totalCount * 100)"
          :format="() => `${reviewedCount}/${totalCount}`"
        />
      </div>

      <el-card class="review-card" shadow="always">
        <div class="card-front">
          <div class="word-big">{{ currentWord.word.word }}</div>
          <div class="phonetic" v-if="currentWord.word.phonetic">
            {{ currentWord.word.phonetic }}
            <el-icon @click="speak(currentWord.word.word)" class="tts-btn"><Microphone /></el-icon>
          </div>

          <el-button type="primary" @click="showAnswer = true" v-if="!showAnswer">
            显示答案
          </el-button>

          <transition name="fade">
            <div v-if="showAnswer" class="answer-area">
              <div class="translation">{{ currentWord.word.translation }}</div>
              <div class="definition" v-if="currentWord.word.definition">{{ currentWord.word.definition }}</div>

              <div class="mastery-info">
                当前掌握度: <strong>{{ currentWord.mastery_score }}%</strong>
              </div>

              <div class="action-btns">
                <el-button type="danger" size="large" @click="submitReview(false)">
                  ✗ 不会
                </el-button>
                <el-button type="success" size="large" @click="submitReview(true)">
                  ✓ 认识
                </el-button>
              </div>
            </div>
          </transition>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { Microphone } from '@element-plus/icons-vue'
import { getDueWords, reviewWord, getTTSUrl } from '../api'
import { useUserStore } from '../stores/user'

const userStore = useUserStore()
const dueWords = ref<any[]>([])
const currentIndex = ref(0)
const showAnswer = ref(false)
const loading = ref(false)
const reviewedCount = ref(0)

const totalCount = computed(() => dueWords.value.length)
const currentWord = computed(() => dueWords.value[currentIndex.value])

onMounted(async () => {
  loading.value = true
  const res = await getDueWords(userStore.userId)
  dueWords.value = res.data
  loading.value = false
})

async function submitReview(isCorrect: boolean) {
  if (!currentWord.value) return
  await reviewWord(userStore.userId, currentWord.value.word_id, isCorrect)
  reviewedCount.value++
  showAnswer.value = false

  if (currentIndex.value + 1 < dueWords.value.length) {
    currentIndex.value++
  } else {
    dueWords.value = []
  }
}

function speak(word: string) {
  new Audio(getTTSUrl(word)).play()
}
</script>

<style scoped>
.page-container { padding: 40px 24px; max-width: 700px; margin: 0 auto; width: 100%; }

.empty-state { margin-top: 60px; }

.progress-bar { margin-bottom: 24px; }

.review-card { min-height: 300px; }

.card-front { text-align: center; padding: 24px; }

.word-big { font-size: 48px; font-weight: 700; color: #303133; margin-bottom: 8px; }

.phonetic {
  font-size: 18px;
  color: #909399;
  margin-bottom: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.tts-btn { cursor: pointer; color: #409eff; }

.answer-area { margin-top: 20px; }

.translation { font-size: 24px; color: #303133; margin-bottom: 8px; }
.definition { font-size: 14px; color: #606266; margin-bottom: 16px; }
.mastery-info { font-size: 14px; color: #909399; margin-bottom: 20px; }

.action-btns { display: flex; gap: 24px; justify-content: center; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

@media (max-width: 767px) {
  .page-container { padding: 16px; }
  .word-big { font-size: 36px; }
  .translation { font-size: 20px; }
  .action-btns { gap: 12px; }
  .action-btns .el-button { flex: 1; }
}
</style>
