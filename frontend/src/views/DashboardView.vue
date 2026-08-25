<template>
  <div class="page-container">

    <el-row :gutter="20" class="stat-cards">
      <el-col :xs="12" :sm="12" :md="6">
        <el-card class="stat-card">
          <div class="stat-num blue">{{ stats.total_words }}</div>
          <div class="stat-label">学习单词</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <el-card class="stat-card">
          <div class="stat-num green">{{ stats.mastered }}</div>
          <div class="stat-label">已掌握</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <el-card class="stat-card">
          <div class="stat-num orange">{{ stats.due_count }}</div>
          <div class="stat-label">待复习</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <el-card class="stat-card">
          <div class="stat-num purple">{{ stats.accuracy }}%</div>
          <div class="stat-label">答题正确率</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <!-- Weekly trend -->
      <el-col :xs="24" :sm="24" :md="14">
        <el-card>
          <template #header><span>本周学习趋势</span></template>
          <div v-if="stats.weekly_trend.length" class="trend-chart">
            <div
              v-for="item in trendWithDefaults"
              :key="item.day"
              class="trend-bar-wrap"
            >
              <div
                class="trend-bar"
                :style="{ height: barHeight(item.count) }"
              ></div>
              <div class="trend-label">{{ item.day.slice(5) }}</div>
              <div class="trend-count">{{ item.count }}</div>
            </div>
          </div>
          <el-empty v-else description="暂无学习数据" />
        </el-card>
      </el-col>

      <!-- Weak words -->
      <el-col :xs="24" :sm="24" :md="10">
        <el-card>
          <template #header><span>薄弱词汇 TOP 10</span></template>
          <div v-for="word in stats.weak_words" :key="word.word" class="weak-word-row">
            <span class="weak-word">{{ word.word }}</span>
            <el-progress
              :percentage="word.mastery_score"
              :stroke-width="6"
              :color="word.mastery_score < 40 ? '#f56c6c' : '#e6a23c'"
              style="flex: 1; margin: 0 8px"
            />
            <span class="weak-count">错 {{ word.wrong_count }}</span>
          </div>
          <el-empty v-if="!stats.weak_words.length" description="暂无数据" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Recent activity -->
    <el-card style="margin-top: 20px">
      <template #header><span>最近学习记录</span></template>
      <div v-for="(act, i) in stats.recent_activity" :key="i" class="activity-row">
        <el-tag :type="act.role === 'user' ? 'primary' : 'success'" size="small">
          {{ act.role === 'user' ? '你' : 'AI' }}
        </el-tag>
        <span class="activity-content">{{ act.content }}</span>
      </div>
      <el-empty v-if="!stats.recent_activity.length" description="暂无记录" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getDashboard } from '../api'
import { useUserStore } from '../stores/user'

const userStore = useUserStore()

const stats = ref<any>({
  total_words: 0,
  mastered: 0,
  due_count: 0,
  accuracy: 0,
  weekly_trend: [],
  weak_words: [],
  recent_activity: [],
})

onMounted(async () => {
  const res = await getDashboard(userStore.userId)
  stats.value = res.data
})

const maxCount = computed(() => Math.max(...stats.value.weekly_trend.map((t: any) => t.count), 1))

function barHeight(count: number): string {
  return `${Math.round((count / maxCount.value) * 120)}px`
}

const trendWithDefaults = computed(() => {
  // Show last 7 days
  const days: string[] = []
  for (let i = 6; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    days.push(d.toISOString().slice(0, 10))
  }
  return days.map(day => {
    const found = stats.value.weekly_trend.find((t: any) => t.day === day)
    return { day, count: found?.count || 0 }
  })
})
</script>

<style scoped>
.page-container { padding: 32px 40px; max-width: 1280px; margin: 0 auto; width: 100%; }

.stat-cards { margin-top: 16px; }

.stat-card { text-align: center; padding: 8px 0; }

.stat-num { font-size: 40px; font-weight: 700; }
.stat-num.blue { color: #409eff; }
.stat-num.green { color: #67c23a; }
.stat-num.orange { color: #e6a23c; }
.stat-num.purple { color: #9c27b0; }

.stat-label { color: #909399; font-size: 14px; margin-top: 4px; }

.trend-chart {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  height: 160px;
  padding: 10px 0;
}

.trend-bar-wrap { display: flex; flex-direction: column; align-items: center; flex: 1; }

.trend-bar {
  width: 100%;
  background: #409eff;
  border-radius: 4px 4px 0 0;
  min-height: 4px;
  transition: height 0.5s;
}

.trend-label { font-size: 11px; color: #909399; margin-top: 4px; }
.trend-count { font-size: 11px; color: #606266; }

.weak-word-row {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}

.weak-word { width: 80px; font-weight: 600; font-size: 14px; }
.weak-count { width: 50px; text-align: right; font-size: 12px; color: #f56c6c; }

.activity-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 10px;
}

.activity-content { font-size: 13px; color: #606266; line-height: 1.5; }

@media (max-width: 767px) {
  .page-container { padding: 16px; }
  .stat-num { font-size: 30px; }
  .stat-cards { margin-top: 8px; }
  .stat-card { padding: 4px 0; margin-bottom: 12px; }
}
</style>
