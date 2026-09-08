import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  getWordbookLevels,
  getWordbookWords,
  getWordbookProgress,
  updateWordbookProgress,
} from '../api'

export interface WordbookLevel {
  id: number
  name: string
  description: string
  sort_order: number
  word_count: number
}

export interface WordbookWord {
  id: number
  word: string
  level_id: number
  phonetic: string | null
  pos: string | null
  definition: string | null
  mnemonic: string | null
  example: string | null
  example_translation: string | null
  image_path: string | null
  sort_order: number
  status: string
}

export interface StudyProgressSummary {
  level_id: number
  level_name: string
  total: number
  learned: number
  mastered: number
}

export const useWordbookStore = defineStore('wordbook', () => {
  const levels = ref<WordbookLevel[]>([])
  const currentLevelId = ref<number | null>(null)
  const words = ref<WordbookWord[]>([])
  const progress = ref<StudyProgressSummary[]>([])
  const loading = ref(false)
  const currentPage = ref(1)
  const hasMore = ref(true)

  async function loadLevels() {
    const { data } = await getWordbookLevels()
    levels.value = data
    if (data.length && !currentLevelId.value) {
      currentLevelId.value = data[0].id
    }
  }

  async function loadWords(levelId: number, page = 1) {
    loading.value = true
    try {
      const { data } = await getWordbookWords(levelId, page)
      words.value = page === 1 ? data : [...words.value, ...data]
      hasMore.value = data.length === 20
      currentPage.value = page
    } finally {
      loading.value = false
    }
  }

  async function loadProgress(userId: number) {
    const { data } = await getWordbookProgress(userId)
    progress.value = data
  }

  async function updateStatus(userId: number, wordId: number, status: string) {
    await updateWordbookProgress(userId, wordId, status)
    const word = words.value.find(w => w.id === wordId)
    if (word) word.status = status
    await loadProgress(userId)
  }

  function getLevelProgress(levelId: number) {
    return progress.value.find(p => p.level_id === levelId) ?? null
  }

  return {
    levels,
    currentLevelId,
    words,
    progress,
    loading,
    currentPage,
    hasMore,
    loadLevels,
    loadWords,
    loadProgress,
    updateStatus,
    getLevelProgress,
  }
})
