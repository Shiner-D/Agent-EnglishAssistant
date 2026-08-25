import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getConversations, getMessages, deleteConversation } from '../api'

export interface ChatMessage {
  id?: number
  role: 'user' | 'assistant'
  content: string
  intent?: string
  sources?: RagSource[]
  streaming?: boolean
}

export interface RagSource {
  word: string
  phonetic?: string
  pos?: string
  definition?: string
  translation?: string
  source: string
  retrieval_score: number
  rerank_score?: number
}

export interface Conversation {
  id: number
  title: string
  updated_at: string
}

export const useChatStore = defineStore('chat', () => {
  const conversations = ref<Conversation[]>([])
  const currentConvId = ref<number | null>(null)
  const messages = ref<ChatMessage[]>([])
  const isStreaming = ref(false)
  const currentIntent = ref<string | null>(null)
  const currentSources = ref<RagSource[]>([])

  async function loadConversations(userId: number) {
    const res = await getConversations(userId)
    conversations.value = res.data
  }

  async function loadMessages(userId: number, convId: number) {
    const res = await getMessages(userId, convId)
    messages.value = res.data.map((m: any) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      intent: m.intent,
      sources: m.sources ?? undefined,
    }))
    currentConvId.value = convId
  }

  async function deleteConv(convId: number) {
    await deleteConversation(convId)
    conversations.value = conversations.value.filter(c => c.id !== convId)
    if (currentConvId.value === convId) {
      currentConvId.value = null
      messages.value = []
    }
  }

  function newConversation() {
    currentConvId.value = null
    messages.value = []
    currentSources.value = []
    currentIntent.value = null
  }

  async function sendMessage(userId: number, text: string): Promise<void> {
    messages.value.push({ role: 'user', content: text })

    messages.value.push({
      role: 'assistant',
      content: '',
      streaming: true,
      sources: [],
    })
    // Take the reactive proxy reference from the array, not the plain object,
    // so property mutations trigger Vue reactivity during streaming.
    const assistantMsg = messages.value[messages.value.length - 1]
    isStreaming.value = true
    currentSources.value = []

    const API = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`

    try {
      const response = await fetch(`${API}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          conversation_id: currentConvId.value,
          message: text,
        }),
      })
      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let currentEvent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        // Process complete lines
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            const rawData = line.slice(6)
            processSSEEvent(currentEvent, rawData, assistantMsg)
          }
        }
      }
    } finally {
      assistantMsg.streaming = false
      isStreaming.value = false
    }
  }

  function processSSEEvent(event: string, rawData: string, msg: ChatMessage) {
    if (event === 'token') {
      // Backend escapes real \n as \\n to keep SSE line framing intact; unescape here.
      msg.content += rawData.replace(/\\n/g, '\n')
      return
    }

    let data: any
    try {
      data = JSON.parse(rawData)
    } catch {
      return
    }

    if (event === 'agent_start' && data.conversation_id) {
      currentConvId.value = data.conversation_id
    } else if (event === 'intent') {
      currentIntent.value = data.type
      msg.intent = data.type
    } else if (event === 'retrieval_result' || event === 'rerank_result') {
      if (data.sources?.length) {
        currentSources.value = data.sources
        msg.sources = data.sources
      }
    } else if (event === 'llm_done') {
      if (data.answer) {
        msg.content = data.answer
      }
    } else if (event === 'done' && data.conversation_id) {
      currentConvId.value = data.conversation_id
    } else if (event === 'error') {
      msg.content = `Error: ${data.message}`
    }
  }

  return {
    conversations, currentConvId, messages, isStreaming,
    currentIntent, currentSources,
    loadConversations, loadMessages, deleteConv, newConversation, sendMessage,
  }
})
