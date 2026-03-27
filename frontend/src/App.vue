<template>
  <el-container class="layout-container" v-if="!isBlankLayout">
    <el-aside width="200px" class="aside">
      <div class="logo">
        <h2>AI Ops Sec</h2>
      </div>
      <el-menu
        :default-active="route.path"
        class="el-menu-vertical"
        background-color="#001529"
        text-color="#fff"
        active-text-color="#409eff"
        router
      >
        <el-menu-item index="/dashboard">
          <el-icon><Monitor /></el-icon>
          <span>监控大盘</span>
        </el-menu-item>
        <el-menu-item index="/terminal">
          <el-icon><Monitor /></el-icon>
          <span>AI 智能终端</span>
        </el-menu-item>
        <el-menu-item index="/tenants">
          <el-icon><OfficeBuilding /></el-icon>
          <span>多租户管理</span>
        </el-menu-item>
        <el-menu-item index="/assistant">
          <el-icon><ChatDotRound /></el-icon>
          <span>数字运维助手</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-icon class="toggle-icon"><Fold /></el-icon>
          <span class="title">轻量化 AI 服务器运维防护系统</span>
        </div>
        <div class="header-right">
          <el-tag v-if="tenantContext" size="small" type="info" class="tenant-tag">
            租户 #{{ tenantContext.tenant_id }} / {{ tenantContext.role }}
          </el-tag>
          <el-dropdown>
            <span class="el-dropdown-link user-info">
              <el-avatar size="small" icon="UserFilled" />
              <span>Admin</span>
              <el-icon class="el-icon--right"><arrow-down /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item>系统设置</el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      
      <el-main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>

  <router-view v-else v-slot="{ Component }">
    <transition name="fade" mode="out-in">
      <component :is="Component" />
    </transition>
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
html, body, #app {
  height: 100%;
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background-color: #f0f2f5;
}

.layout-container {
  height: 100vh;
}

.aside {
  background-color: #001529;
  box-shadow: 2px 0 6px rgba(0,21,41,.35);
  z-index: 10;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  border-bottom: 1px solid #1f2d3d;
}

.logo h2 {
  margin: 0;
  font-size: 20px;
  background: linear-gradient(90deg, #409eff, #36cfc9);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.el-menu-vertical {
  border-right: none;
}

.header {
  background-color: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  box-shadow: 0 1px 4px rgba(0,21,41,.08);
  z-index: 9;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 15px;
}

.toggle-icon {
  font-size: 20px;
  cursor: pointer;
}

.title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #606266;
}

.tenant-tag {
  margin-right: 12px;
}

.main-content {
  padding: 20px;
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
