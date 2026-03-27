<template>
  <el-container class="bt-layout" v-if="!isBlankLayout">
    <el-aside width="230px" class="bt-aside">
      <div class="bt-logo">
        <div class="logo-dot"></div>
        <div>
          <div class="logo-title">AIOps Panel</div>
          <div class="logo-sub">Enterprise Console</div>
        </div>
      </div>

      <el-menu :default-active="route.path" class="bt-menu" router>
        <el-menu-item index="/dashboard"><el-icon><DataLine /></el-icon><span>监控大屏</span></el-menu-item>
        <el-menu-item index="/terminal"><el-icon><Monitor /></el-icon><span>终端</span></el-menu-item>
        <el-menu-item index="/services"><el-icon><Operation /></el-icon><span>服务管理</span></el-menu-item>
        <el-menu-item index="/logs"><el-icon><Document /></el-icon><span>日志中心</span></el-menu-item>
        <el-menu-item index="/backup"><el-icon><Box /></el-icon><span>备份恢复</span></el-menu-item>
        <el-menu-item index="/files"><el-icon><FolderOpened /></el-icon><span>文件管理</span></el-menu-item>
        <el-menu-item index="/batch"><el-icon><Promotion /></el-icon><span>批量命令审批</span></el-menu-item>
        <el-menu-item index="/assistant"><el-icon><ChatDotRound /></el-icon><span>智能助手</span></el-menu-item>
        <el-menu-item index="/tenants"><el-icon><OfficeBuilding /></el-icon><span>租户管理</span></el-menu-item>
      </el-menu>
    </el-aside>

    <el-container class="bt-main-wrap">
      <el-header class="bt-header">
        <div class="header-title-wrap">
          <div class="header-title">运维控制台</div>
          <div class="header-sub">实时监控 · 安全审计 · 自动化执行</div>
        </div>
        <div class="header-actions">
          <el-tag v-if="tenantContext" size="small" type="info">租户 #{{ tenantContext.tenant_id }} / {{ tenantContext.role }}</el-tag>
          <el-dropdown>
            <span class="user-entry">
              <el-avatar size="small">U</el-avatar>
              <span>控制台用户</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="bt-main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>

  <router-view v-else v-slot="{ Component }">
    <transition name="fade" mode="out-in"><component :is="Component" /></transition>
  </router-view>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from './utils/request'

const route = useRoute()
const router = useRouter()
const tenantContext = ref(null)

const isBlankLayout = computed(() => route.meta.layout === 'blank')

const handleLogout = async () => {
  try {
    await request.post('/auth/logout')
  } catch (e) {
    console.error('Logout error', e)
  } finally {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    router.push('/login')
  }
}

const loadTenantContext = async () => {
  try {
    const res = await request.get('/tenants/context')
    if (res.code === 200) {
      tenantContext.value = res.data
    }
  } catch {
    tenantContext.value = null
  }
}

onMounted(() => {
  loadTenantContext()
})
</script>

<style>
:root {
  --bt-bg: #f4f7fb;
  --bt-side: #0c172a;
  --bt-side-2: #13243e;
  --bt-primary: #2f7df6;
  --bt-text: #1f2d3d;
}

html, body, #app {
  height: 100%;
  margin: 0;
  padding: 0;
  font-family: 'Segoe UI', 'PingFang SC', sans-serif;
  background-color: var(--bt-bg);
}

.bt-layout {
  height: 100vh;
}

.bt-aside {
  background: linear-gradient(180deg, var(--bt-side), var(--bt-side-2));
  box-shadow: 4px 0 18px rgba(8, 16, 32, 0.35);
}

.bt-logo {
  height: 72px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  color: #fff;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.logo-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #34d399;
  box-shadow: 0 0 0 6px rgba(52, 211, 153, 0.18);
}

.logo-title {
  font-weight: 700;
  letter-spacing: 0.3px;
}

.logo-sub {
  opacity: 0.75;
  font-size: 12px;
}

.bt-menu {
  border-right: none;
  background: transparent;
  --el-menu-bg-color: transparent;
  --el-menu-text-color: #d5e1f7;
  --el-menu-active-color: #ffffff;
  --el-menu-hover-bg-color: rgba(10, 20, 37, 0.62);
  padding: 8px;
}

.bt-menu .el-menu-item {
  color: #d5e1f7;
  border-radius: 8px;
  margin-bottom: 4px;
  height: 42px;
  line-height: 42px;
  font-weight: 500;
}

.bt-menu .el-menu-item:hover {
  color: #ffffff;
  background: rgba(10, 20, 37, 0.62);
}

.bt-menu .el-menu-item.is-active {
  background: linear-gradient(90deg, rgba(47, 125, 246, 0.28), rgba(47, 125, 246, 0.12));
  border: 1px solid rgba(126, 173, 255, 0.32);
  color: #fff;
}

.bt-menu .el-menu-item .el-icon {
  color: #a9bde2;
}

.bt-menu .el-menu-item.is-active .el-icon,
.bt-menu .el-menu-item:hover .el-icon {
  color: #ffffff;
}

.bt-main-wrap {
  background: radial-gradient(circle at 0% 0%, #e8f0ff, #f4f7fb 28%);
}

.bt-header {
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 18px;
}

.header-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--bt-text);
}

.header-sub {
  font-size: 12px;
  color: #64748b;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-entry {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #475569;
}

.bt-main {
  padding: 16px 16px 20px;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
