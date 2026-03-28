<template>
  <div v-if="!isBlankLayout" class="shell-layout">
    <aside class="shell-sidebar">
      <div class="brand-panel">
        <div class="brand-mark">AIOps</div>
        <div>
          <div class="brand-title">智能运维控制台</div>
          <div class="brand-subtitle">观测、安全、执行一体化工作台</div>
        </div>
      </div>

      <div class="nav-groups">
        <section v-for="group in navGroups" :key="group.label" class="nav-group">
          <div class="nav-group__label">{{ group.label }}</div>
          <button
            v-for="item in group.items"
            :key="item.path"
            type="button"
            :class="['nav-item', { 'is-active': route.path === item.path }]"
            @click="router.push(item.path)"
          >
            <el-icon class="nav-item__icon">
              <component :is="item.icon" />
            </el-icon>
            <span class="nav-item__copy">
              <span class="nav-item__title">{{ item.label }}</span>
              <span class="nav-item__desc">{{ item.description }}</span>
            </span>
          </button>
        </section>
      </div>

      <div class="sidebar-foot">
        <div class="sidebar-foot__title">运行状态</div>
        <div :class="['status-pill', shellStatusClass]">
          {{ shellStatusText }}
        </div>
        <div class="sidebar-foot__meta">当前租户 {{ tenantContext?.tenant_id ?? '--' }} / {{ tenantContext?.role ?? 'guest' }}</div>
      </div>
    </aside>

    <div class="shell-main">
      <header class="shell-header">
        <div class="shell-header__copy">
          <div class="shell-header__eyebrow">Enterprise AIOps Console</div>
          <h1 class="shell-header__title">{{ currentTitle }}</h1>
          <p class="shell-header__subtitle">{{ currentSubtitle }}</p>
        </div>

        <div class="shell-header__actions">
          <div class="header-context surface-panel">
            <div class="header-context__label">租户上下文</div>
            <div class="header-context__value">
              #{{ tenantContext?.tenant_id ?? '--' }} / {{ tenantContext?.role ?? '未识别' }}
            </div>
          </div>

          <div class="action-row">
            <el-button plain @click="router.push('/dashboard')">返回总览</el-button>
            <el-button type="primary" @click="loadTenantContext">刷新上下文</el-button>
          </div>

          <el-dropdown>
            <span class="user-entry">
              <el-avatar size="small">U</el-avatar>
              <span>控制台用户</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="loadTenantContext">刷新租户信息</el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="shell-content">
        <router-view v-slot="{ Component }">
          <transition name="fade-slide" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>

  <router-view v-else v-slot="{ Component }">
    <transition name="fade-slide" mode="out-in">
      <component :is="Component" />
    </transition>
  </router-view>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from './utils/request'

const route = useRoute()
const router = useRouter()
const tenantContext = ref(null)

const navGroups = [
  {
    label: '总览',
    items: [
      { path: '/dashboard', label: '监控总览', description: '指标、预测、安全事件', icon: 'DataLine' },
      { path: '/terminal', label: '运维终端', description: '实时执行与操作审计', icon: 'Monitor' },
      { path: '/assistant', label: '智能助手', description: '先规划、再确认、后执行', icon: 'ChatDotRound' },
    ],
  },
  {
    label: '运营操作',
    items: [
      { path: '/services', label: '服务治理', description: '服务状态与自启动配置', icon: 'Operation' },
      { path: '/logs', label: '日志中心', description: '审计搜索与异常聚类', icon: 'Document' },
      { path: '/backup', label: '备份恢复', description: '任务、产物与回滚风险', icon: 'Box' },
      { path: '/files', label: '文件工作台', description: '目录浏览与在线编辑', icon: 'FolderOpened' },
      { path: '/batch', label: '批量审批', description: '批量命令的创建与审核', icon: 'Promotion' },
    ],
  },
  {
    label: '平台治理',
    items: [
      { path: '/tenants', label: '租户治理', description: '多租户上下文与隔离', icon: 'OfficeBuilding' },
    ],
  },
]

const isBlankLayout = computed(() => route.meta.layout === 'blank')
const currentTitle = computed(() => route.meta.title || 'AIOps 控制台')
const currentSubtitle = computed(() => route.meta.subtitle || '统一管理监控、安全和自动化执行')

const shellStatusText = computed(() => {
  if (!tenantContext.value) return '上下文未加载'
  return ['tenant_admin', 'platform_admin', 'superadmin'].includes(tenantContext.value.role)
    ? '管理员上下文已就绪'
    : '只读 / 受控上下文'
})

const shellStatusClass = computed(() => {
  if (!tenantContext.value) return 'status-pill--warning'
  return ['tenant_admin', 'platform_admin', 'superadmin'].includes(tenantContext.value.role)
    ? 'status-pill--success'
    : 'status-pill--warning'
})

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
    tenantContext.value = res.code === 200 ? res.data : null
  } catch {
    tenantContext.value = null
  }
}

watch(() => route.path, () => {
  if (!isBlankLayout.value) loadTenantContext()
})

onMounted(() => {
  loadTenantContext()
})
</script>

<style scoped>
.shell-layout {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 290px minmax(0, 1fr);
  gap: 18px;
  padding: 18px;
}

.shell-sidebar {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 18px;
  border-radius: 30px;
  background:
    radial-gradient(circle at top, rgba(59, 130, 246, 0.2), transparent 34%),
    linear-gradient(180deg, rgba(15, 23, 42, 0.98), rgba(15, 23, 42, 0.92));
  color: #dbeafe;
  box-shadow: 0 28px 72px rgba(15, 23, 42, 0.36);
}

.brand-panel {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 6px 20px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.16);
}

.brand-mark {
  width: 54px;
  height: 54px;
  border-radius: 18px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.96), rgba(14, 165, 233, 0.88));
  color: #fff;
  font-weight: 800;
  letter-spacing: 0.04em;
}

.brand-title {
  font-size: 18px;
  font-weight: 800;
  color: #f8fafc;
}

.brand-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: rgba(219, 234, 254, 0.7);
}

.nav-groups {
  display: flex;
  flex-direction: column;
  gap: 18px;
  flex: 1;
}

.nav-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.nav-group__label {
  padding: 0 8px;
  font-size: 12px;
  color: rgba(191, 219, 254, 0.64);
  letter-spacing: 0.08em;
}

.nav-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 14px;
  border: 1px solid transparent;
  border-radius: 18px;
  background: transparent;
  color: #dbeafe;
  cursor: pointer;
  transition: transform var(--transition-fast), background var(--transition-fast), border-color var(--transition-fast);
}

.nav-item:hover {
  transform: translateY(-1px);
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(148, 163, 184, 0.12);
}

.nav-item.is-active {
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.24), rgba(14, 165, 233, 0.18));
  border-color: rgba(96, 165, 250, 0.22);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

.nav-item__icon {
  width: 40px;
  height: 40px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.08);
  color: #bfdbfe;
}

.nav-item__copy {
  display: flex;
  flex-direction: column;
  gap: 3px;
  text-align: left;
}

.nav-item__title {
  font-size: 14px;
  font-weight: 700;
  color: #eff6ff;
}

.nav-item__desc {
  font-size: 12px;
  color: rgba(191, 219, 254, 0.7);
}

.sidebar-foot {
  padding: 16px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.sidebar-foot__title {
  font-size: 13px;
  color: rgba(191, 219, 254, 0.72);
  margin-bottom: 10px;
}

.sidebar-foot__meta {
  margin-top: 10px;
  color: rgba(219, 234, 254, 0.62);
  font-size: 12px;
}

.shell-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.shell-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 18px;
  padding: 24px 28px;
  border-radius: 30px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(255, 255, 255, 0.58);
  backdrop-filter: blur(22px);
  box-shadow: var(--shadow-sm);
}

.shell-header__eyebrow {
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.shell-header__title {
  margin: 8px 0 0;
  font-size: clamp(26px, 2.8vw, 38px);
  line-height: 1.06;
}

.shell-header__subtitle {
  margin: 10px 0 0;
  max-width: 680px;
  color: var(--app-text-faint);
  line-height: 1.7;
}

.shell-header__actions {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.surface-panel {
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.84);
  border: 1px solid rgba(148, 163, 184, 0.16);
}

.header-context__label {
  font-size: 12px;
  color: var(--app-text-faint);
}

.header-context__value {
  margin-top: 6px;
  font-size: 14px;
  font-weight: 700;
}

.user-entry {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 16px;
  background: rgba(248, 250, 252, 0.84);
  border: 1px solid rgba(148, 163, 184, 0.16);
  color: var(--app-text-soft);
  cursor: pointer;
}

.shell-content {
  min-width: 0;
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: opacity 0.24s ease, transform 0.24s ease;
}

.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

@media (max-width: 1280px) {
  .shell-layout {
    grid-template-columns: 240px minmax(0, 1fr);
  }

  .nav-item__desc {
    display: none;
  }
}

@media (max-width: 980px) {
  .shell-layout {
    grid-template-columns: 1fr;
  }

  .shell-sidebar {
    border-radius: 26px;
  }

  .shell-header {
    flex-direction: column;
  }

  .shell-header__actions {
    justify-content: flex-start;
  }
}

@media (max-width: 640px) {
  .shell-layout {
    padding: 12px;
  }

  .shell-sidebar,
  .shell-header {
    padding: 18px;
  }
}
</style>
