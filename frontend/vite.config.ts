import { sentryVitePlugin } from "@sentry/vite-plugin";
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue(), sentryVitePlugin({
    org: "shine-ds-team",
    project: "englishassistant",
    authToken: process.env.SENTRY_AUTH_TOKEN,
    release: {
      name: process.env.APP_VERSION,
    },
    sourcemaps: {
      filesToDeleteAfterUpload: ['./dist/**/*.map', './dist/**/*.js.map'],
    }
  })],

  server: {
    host: true,
  },

  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },

  build: {
    sourcemap: true
  }
})
