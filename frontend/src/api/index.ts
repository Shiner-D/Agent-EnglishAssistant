import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || ''

export const api = axios.create({ baseURL: BASE_URL })

// Users
export const createUser = (username: string) =>
  api.post('/api/users/', { username })

export const getUser = (userId: number) =>
  api.get(`/api/users/${userId}`)

export const updateUser = (userId: number, data: object) =>
  api.patch(`/api/users/${userId}`, data)

// Conversations
export const getConversations = (userId: number) =>
  api.get(`/api/chat/conversations/${userId}`)

export const getMessages = (userId: number, convId: number) =>
  api.get(`/api/chat/conversations/${userId}/${convId}/messages`)

export const deleteConversation = (convId: number) =>
  api.delete(`/api/chat/conversations/${convId}`)

// Vocabulary
export const getVocabulary = (userId: number, params?: object) =>
  api.get(`/api/words/${userId}`, { params })

export const saveWord = (userId: number, word: string) =>
  api.post(`/api/words/${userId}/save/${word}`)

export const removeWord = (userId: number, word: string) =>
  api.delete(`/api/words/${userId}/remove/${word}`)

export const getDueWords = (userId: number) =>
  api.get(`/api/words/${userId}/due`)

export const reviewWord = (userId: number, wordId: number, isCorrect: boolean) =>
  api.post(`/api/words/${userId}/review/${wordId}`, null, { params: { is_correct: isCorrect } })

// Exercises
export const generateExercise = (data: object) =>
  api.post('/api/exercises/generate', data)

export const submitExercise = (exerciseId: number, userAnswer: string) =>
  api.post('/api/exercises/submit', { exercise_id: exerciseId, user_answer: userAnswer })

export const getExerciseStats = (userId: number) =>
  api.get(`/api/exercises/${userId}/stats`)

// Dashboard
export const getDashboard = (userId: number) =>
  api.get(`/api/dashboard/${userId}`)

// TTS
export const getTTSUrl = (text: string, voice = 'en-US') =>
  `${BASE_URL}/api/tts/speak?text=${encodeURIComponent(text)}&voice=${voice}`

// STT
export const transcribeAudio = (blob: Blob): Promise<{ transcript: string }> => {
  const form = new FormData()
  form.append('audio', blob, 'recording.webm')
  return api.post('/api/stt/transcribe', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)
}
