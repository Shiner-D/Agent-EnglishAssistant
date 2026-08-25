import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { createUser, getUser } from '../api'

export const useUserStore = defineStore('user', () => {
  const userId = ref<number>(Number(localStorage.getItem('userId')) || 0)
  const username = ref(localStorage.getItem('username') || '')
  const level = ref('CET4')
  const target = ref('CET6')

  const isLoggedIn = computed(() => userId.value > 0)

  async function login(name: string) {
    const res = await createUser(name)
    userId.value = res.data.id
    username.value = res.data.username
    level.value = res.data.level
    target.value = res.data.target
    localStorage.setItem('userId', String(userId.value))
    localStorage.setItem('username', username.value)
  }

  async function loadProfile() {
    if (!userId.value) return
    const res = await getUser(userId.value)
    level.value = res.data.level
    target.value = res.data.target
  }

  return { userId, username, level, target, isLoggedIn, login, loadProfile }
})
