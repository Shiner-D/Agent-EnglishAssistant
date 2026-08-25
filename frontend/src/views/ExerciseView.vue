<template>
  <div class="page-container">

    <!-- Settings -->
    <el-card v-if="!currentExercise && !loading" class="settings-card">
      <el-form label-width="100px">
        <el-form-item label="题型">
          <el-radio-group v-model="exerciseType">
            <el-radio value="multiple_choice">选择题</el-radio>
            <el-radio value="chinese_to_english">中译英</el-radio>
            <el-radio value="english_to_chinese">英译中</el-radio>
            <el-radio value="fill_blank">完形填空</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="指定单词">
          <el-input v-model="targetWord" placeholder="留空则从生词本选择" clearable style="width: 250px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="generateExercise" size="large">开始练习</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Exercise card -->
    <el-card v-if="currentExercise" class="exercise-card" shadow="always">
      <div class="ex-type-tag">
        <el-tag>{{ typeLabel(currentExercise.exercise_type) }}</el-tag>
        <span v-if="currentExercise.word" class="ex-word">{{ currentExercise.word }}</span>
      </div>

      <div class="question" v-html="renderMarkdown(currentExercise.question)"></div>

      <!-- Answer input -->
      <div v-if="!submitted" class="answer-input">
        <el-input
          v-model="userAnswer"
          placeholder="输入你的答案..."
          size="large"
          @keyup.enter="submit"
        />
        <el-button type="primary" @click="submit" :disabled="!userAnswer.trim()">提交答案</el-button>
      </div>

      <!-- Result -->
      <div v-if="submitted" class="result-area">
        <el-alert
          :title="resultMsg"
          :type="isCorrect ? 'success' : 'error'"
          show-icon
          :closable="false"
        />
        <div class="answer-reveal">
          <span class="label">正确答案:</span>
          <strong>{{ currentExercise.answer }}</strong>
        </div>
        <div class="btn-row">
          <el-button type="primary" @click="nextExercise">下一题</el-button>
          <el-button @click="goBack">返回设置</el-button>
        </div>
      </div>

      <div class="stats-mini">
        本次练习: {{ sessionCorrect }} 正确 / {{ sessionTotal }} 题 ({{ sessionAccuracy }}%)
      </div>
    </el-card>

    <el-skeleton v-if="loading" :rows="6" animated />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { generateExercise as apiGenerate, submitExercise } from '../api'
import { useUserStore } from '../stores/user'

const userStore = useUserStore()
const exerciseType = ref('multiple_choice')
const targetWord = ref('')
const currentExercise = ref<any>(null)
const userAnswer = ref('')
const submitted = ref(false)
const isCorrect = ref(false)
const loading = ref(false)

const sessionTotal = ref(0)
const sessionCorrect = ref(0)
const sessionAccuracy = computed(() =>
  sessionTotal.value ? Math.round(sessionCorrect.value / sessionTotal.value * 100) : 0
)

const resultMsg = computed(() =>
  isCorrect.value ? '回答正确！' : '回答错误'
)

async function generateExercise() {
  loading.value = true
  try {
    const res = await apiGenerate({
      user_id: userStore.userId,
      exercise_type: exerciseType.value,
      word: targetWord.value || undefined,
    })
    currentExercise.value = res.data
    userAnswer.value = ''
    submitted.value = false
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '生成练习失败，请先添加生词')
  }
  loading.value = false
}

async function submit() {
  if (!userAnswer.value.trim()) return
  const res = await submitExercise(currentExercise.value.id, userAnswer.value)
  isCorrect.value = res.data.is_correct
  submitted.value = true
  sessionTotal.value++
  if (isCorrect.value) sessionCorrect.value++
}

async function nextExercise() {
  submitted.value = false
  userAnswer.value = ''
  await generateExercise()
}

function goBack() {
  currentExercise.value = null
  submitted.value = false
}

function typeLabel(t: string): string {
  const map: Record<string, string> = {
    multiple_choice: '选择题',
    chinese_to_english: '中译英',
    english_to_chinese: '英译中',
    fill_blank: '完形填空',
    rewrite: '改写',
  }
  return map[t] || t
}

function renderMarkdown(text: string): string {
  return text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>')
}
</script>

<style scoped>
.page-container { padding: 40px 24px; max-width: 800px; margin: 0 auto; width: 100%; }

.settings-card, .exercise-card { margin-top: 20px; }

.ex-type-tag {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.ex-word { font-weight: 600; font-size: 16px; color: #409eff; }

.question {
  font-size: 18px;
  line-height: 1.8;
  color: #303133;
  margin-bottom: 24px;
  white-space: pre-wrap;
}

.answer-input { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }

.result-area { margin-top: 16px; }

.answer-reveal {
  margin: 12px 0;
  font-size: 16px;
}

.answer-reveal .label { color: #909399; margin-right: 8px; }

.btn-row { display: flex; gap: 12px; margin-top: 16px; }

.stats-mini {
  margin-top: 20px;
  padding-top: 12px;
  border-top: 1px dashed #e4e7ed;
  font-size: 13px;
  color: #909399;
  text-align: right;
}

@media (max-width: 767px) {
  .page-container { padding: 16px; }
  .answer-input { flex-direction: column; }
  .answer-input .el-button { width: 100%; }
  .btn-row { flex-direction: column; }
  .btn-row .el-button { width: 100%; }
  .question { font-size: 16px; }
}
</style>
