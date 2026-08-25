<template>
  <div class="app-layout">
    <!-- Login dialog -->
    <el-dialog v-model="showLogin" title="欢迎使用 AI 英语学习助手" width="400px" :close-on-click-modal="false" :show-close="false" class="login-dialog" modal-class="login-overlay" top="40vh">
      <el-form @submit.prevent="doLogin">
        <el-form-item label="用户名">
          <el-input v-model="loginName" placeholder="输入你的用户名" size="large" @keyup.enter="doLogin" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" @click="doLogin" size="large" style="width: 100%">开始学习</el-button>
      </template>
    </el-dialog>

    <template v-if="userStore.isLoggedIn">
      <!-- Desktop top navbar -->
      <el-menu mode="horizontal" :default-active="activeRoute" router class="top-nav desktop-nav" :ellipsis="false">
        <div class="nav-logo"><img src="/logo-En.png" class="nav-logo-img" alt="logo" />AI English Tutor</div>
        <el-menu-item index="/tutor">AI Tutor</el-menu-item>
        <el-menu-item index="/vocabulary">生词本</el-menu-item>
        <el-menu-item index="/review">智能复习</el-menu-item>
        <el-menu-item index="/exercise">智能练习</el-menu-item>
        <el-menu-item index="/dashboard">Dashboard</el-menu-item>
        <div class="nav-spacer" />
        <div class="nav-user">
          <el-avatar size="small" :style="{ background: '#409eff' }">
            {{ userStore.username[0]?.toUpperCase() }}
          </el-avatar>
          <span class="username">{{ userStore.username }}</span>
          <el-tag size="small" type="info">{{ userStore.level }}</el-tag>
        </div>
      </el-menu>

      <!-- Mobile compact header -->
      <header class="mobile-header">
        <img src="/logo-En.png" class="nav-logo-img" alt="logo" />
        <span class="mobile-title">{{ currentPageTitle }}</span>
        <div class="mobile-user">
          <el-avatar size="small" :style="{ background: '#409eff' }">
            {{ userStore.username[0]?.toUpperCase() }}
          </el-avatar>
          <el-tag size="small" type="info" style="margin-left: 6px">{{ userStore.level }}</el-tag>
        </div>
      </header>

      <!-- Page content -->
      <div class="page-content">
        <RouterView />
      </div>

      <!-- Mobile bottom tab bar -->
      <nav class="mobile-bottom-nav">
        <router-link
          v-for="tab in navTabs"
          :key="tab.path"
          :to="tab.path"
          class="bottom-tab"
        >
          <el-icon :size="20"><component :is="tab.icon" /></el-icon>
          <span>{{ tab.label }}</span>
        </router-link>
      </nav>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from './stores/user'
import { ChatDotRound, Collection, Tickets, EditPen, DataAnalysis } from '@element-plus/icons-vue'

const userStore = useUserStore()
const route = useRoute()
const showLogin = ref(false)
const loginName = ref('')

const activeRoute = computed(() => route.path)

const navTabs = [
  { path: '/tutor', label: 'AI 对话', icon: ChatDotRound },
  { path: '/vocabulary', label: '生词本', icon: Collection },
  { path: '/review', label: '复习', icon: Tickets },
  { path: '/exercise', label: '练习', icon: EditPen },
  { path: '/dashboard', label: '统计', icon: DataAnalysis },
]

const currentPageTitle = computed(() => {
  const tab = navTabs.find(t => t.path === activeRoute.value)
  return tab?.label || 'AI English Tutor'
})

onMounted(async () => {
  if (!userStore.isLoggedIn) {
    showLogin.value = true
  } else {
    await userStore.loadProfile()
  }
})

async function doLogin() {
  if (!loginName.value.trim()) return
  try {
    await userStore.login(loginName.value.trim())
    showLogin.value = false
  } catch (e: any) {
    ElMessage.error('登录失败：' + (e?.message || '无法连接服务器'))
  }
}
</script>

<style>
* { box-sizing: border-box; }

html, body, #app {
  width: 100%;
  height: 100%;
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.app-layout {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
}

/* ── Desktop top nav ── */
.top-nav {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  padding: 0 16px;
  height: 56px;
  border-bottom: 1px solid #e4e7ed !important;
  background: #fff;
}

.top-nav.el-menu--horizontal > .el-menu-item.is-active {
  border-bottom: 2px solid #409eff !important;
}

.nav-logo {
  font-size: 16px;
  font-weight: 700;
  color: #303133;
  margin-right: 60px;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
}

.nav-logo-img {
  height: 32px;
  width: auto;
  display: block;
}

.nav-spacer { flex: 1; }

.nav-user {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  color: #606266;
}

.username { font-size: 14px; }

/* ── Page content ── */
.page-content {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.page-content > .tutor-layout {
  flex: 1;
  overflow: hidden;
}

/* ── Mobile header (hidden on desktop) ── */
.mobile-header {
  display: none;
  align-items: center;
  padding: 0 16px;
  height: 50px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  flex-shrink: 0;
  gap: 8px;
  padding-top: env(safe-area-inset-top);
}

.mobile-title {
  flex: 1;
  font-size: 16px;
  font-weight: 700;
  color: #303133;
}

.mobile-user {
  display: flex;
  align-items: center;
}

/* ── Mobile bottom tab bar (hidden on desktop) ── */
.mobile-bottom-nav {
  display: none;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: #fff;
  border-top: 1px solid #e4e7ed;
  z-index: 1000;
  padding-bottom: env(safe-area-inset-bottom);
}

.bottom-tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  color: #909399;
  text-decoration: none;
  font-size: 10px;
  padding: 8px 0;
  transition: color 0.2s;
}

.bottom-tab.router-link-exact-active {
  color: #409eff;
}

/* ── Login overlay / dialog ── */
.login-overlay {
  background-image: url('/en-back.png') !important;
  background-size: cover !important;
  background-position: center !important;
  background-repeat: no-repeat !important;
  background-color: transparent !important;
  align-items: flex-start !important;
}

.login-dialog {
  background: rgba(255, 255, 255, 0.18) !important;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.35);
  border-radius: 16px !important;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
  overflow: hidden;
}

.login-dialog .el-dialog__header { background: transparent; padding-bottom: 8px; }
.login-dialog .el-dialog__title {
  font-weight: 700;
  font-size: 18px;
  color: #fff;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
}
.login-dialog .el-dialog__body { background: transparent; }
.login-dialog .el-dialog__footer { background: transparent; padding-top: 0; }
.login-dialog .el-form-item__label {
  color: #fff;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
  font-weight: 600;
}

/* ── Mobile breakpoint ── */
@media (max-width: 767px) {
  .desktop-nav { display: none !important; }
  .mobile-header { display: flex; }
  .mobile-bottom-nav { display: flex; }

  /* Extra bottom space for bottom nav + safe area */
  .page-content {
    padding-bottom: calc(56px + env(safe-area-inset-bottom));
  }

  /* Login dialog responsive */
  .login-dialog {
    width: min(380px, 92vw) !important;
  }

  /* Prevent iOS input zoom (inputs must be ≥16px) */
  input, textarea, select {
    font-size: 16px !important;
  }
}
</style>
