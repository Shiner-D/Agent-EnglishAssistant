import './assets/main.css'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import * as Sentry from "@sentry/vue"
import App from './App.vue'
import router from './router'

Sentry.init({
  dsn: "https://3af5e98e59355104d51617635055e41c@o4512044823937024.ingest.us.sentry.io/4512045565149184",
  environment: import.meta.env.NODE_ENV || "development",
  release: import.meta.env.APP_VERSION,
  integrations: [Sentry.browserTracingIntegration()],
  tracesSampleRate: 0.1,
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.mount('#app')
