<template>
  <div class="app-page">
    <section class="page-hero">
      <div class="page-hero__content">
        <div class="page-eyebrow">Service Operations</div>
        <h2 class="page-title">用一套工作流管理服务状态与服务器接入</h2>
        <p class="page-subtitle">
          将服务器接入、服务状态巡检、自启动切换和实例操作整合进一个操作平面，让高频运维动作更清晰、更可控。
        </p>
      </div>
      <div class="page-hero__aside">
        <div class="hero-stat">
          <div class="hero-stat__label">已接入服务器</div>
          <div class="hero-stat__value">{{ servers.length }}</div>
        </div>
        <div class="hero-stat">
          <div class="hero-stat__label">当前服务数</div>
          <div class="hero-stat__value">{{ services.length }}</div>
        </div>
      </div>
    </section>

    <section class="page-grid page-grid--sidebar">
      <div class="stack-card">
        <el-card class="section-card">
          <template #header>
            <div class="section-head">
              <div>
                <div class="section-head__title">服务器接入</div>
                <div class="section-head__meta">用于服务管理、备份恢复、文件编辑和批量执行</div>
              </div>
              <el-tag type="info" round>基础设施入口</el-tag>
            </div>
          </template>

          <el-form class="stack-form" @submit.prevent>
            <el-form-item label="IP 地址">
              <el-input v-model="newServer.ip" placeholder="例如 10.0.0.8" />
            </el-form-item>
            <el-form-item label="SSH 端口">
              <el-input-number v-model="newServer.port" :min="1" :max="65535" style="width: 100%" />
            </el-form-item>
            <el-form-item label="SSH 用户">
              <el-input v-model="newServer.ssh_username" placeholder="root / ubuntu" />
            </el-form-item>
            <el-form-item label="SSH 密码">
              <el-input v-model="newServer.ssh_password" type="password" show-password placeholder="输入 SSH 密码" />
            </el-form-item>
            <el-button type="primary" :loading="savingServer" @click="createServer">接入服务器</el-button>
          </el-form>
        </el-card>

        <el-card class="section-card">
          <template #header>
            <div class="section-head">
              <div>
                <div class="section-head__title">当前工作上下文</div>
                <div class="section-head__meta">先选择目标服务器，再加载服务状态</div>
              </div>
            </div>
          </template>

          <div class="stack-card compact">
            <el-select v-model="serverId" placeholder="选择服务器" @change="loadServices">
              <el-option v-for="s in servers" :key="s.id" :label="`${s.hostname} (${s.ip})`" :value="s.id" />
            </el-select>
            <el-button plain @click="loadServices">刷新状态</el-button>
          </div>
        </el-card>
      </div>

      <el-card class="section-card">
        <template #header>
          <div class="section-head">
            <div>
              <div class="section-head__title">服务管理</div>
              <div class="section-head__meta">支持 nginx、mysql、redis、docker、ssh、cron 等常见系统服务</div>
            </div>
            <el-tag type="info" round>操作平面</el-tag>
          </div>
        </template>

        <el-table :data="services" v-loading="loading" size="small">
          <el-table-column prop="service_name" label="服务名" min-width="120" />
          <el-table-column prop="status" label="当前状态" width="120">
            <template #default="scope">
            <el-tag :type="scope.row.status === 'active' ? 'success' : 'danger'">{{ scope.row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="autostart" label="自启状态" width="130">
          <template #default="scope">
            <el-tag :type="scope.row.autostart === 'enabled' ? 'success' : 'warning'">{{ scope.row.autostart }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="health" label="健康度" width="110">
          <template #default="scope">
            <el-tag :type="scope.row.health === 'healthy' ? 'success' : 'danger'">{{ scope.row.health }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="360">
          <template #default="scope">
            <el-space>
              <el-button size="small" :disabled="!canOperate" @click="control(scope.row.service_name, 'start')">启动</el-button>
              <el-button size="small" :disabled="!canOperate" @click="control(scope.row.service_name, 'restart')">重启</el-button>
              <el-button size="small" type="danger" :disabled="!canOperate" @click="control(scope.row.service_name, 'stop')">停止</el-button>
              <el-switch
                :disabled="!canOperate"
                :model-value="scope.row.autostart === 'enabled'"
                @change="(val) => setAutostart(scope.row.service_name, val)"
              />
            </el-space>
          </template>
          </el-table-column>
        </el-table>
      </el-card>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

const servers = ref([])
const serverId = ref(null)
const services = ref([])
const loading = ref(false)
const role = ref('operator')
const savingServer = ref(false)
const newServer = ref({ ip: '', port: 22, ssh_username: '', ssh_password: '' })

const canOperate = computed(() => ['tenant_admin', 'platform_admin', 'superadmin'].includes(role.value))

const loadContext = async () => {
  const res = await request.get('/tenants/context')
  if (res.code === 200) role.value = res.data?.role || 'operator'
}

const loadServers = async () => {
  const res = await request.get('/servers/')
  if (res.code === 200) {
    servers.value = res.data || []
    if (!serverId.value && servers.value.length) {
      serverId.value = servers.value[0].id
    }
  }
}

const loadServices = async () => {
  if (!serverId.value) return
  loading.value = true
  try {
    const res = await request.get('/services/list', { params: { server_id: serverId.value } })
    if (res.code === 200) services.value = res.data || []
    else ElMessage.error(res.message || '加载服务状态失败')
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '加载服务状态失败')
  } finally {
    loading.value = false
  }
}

const control = async (serviceName, action) => {
  try {
    const res = await request.post('/services/control', {
      server_id: serverId.value,
      service_name: serviceName,
      action,
    })
    if (res.code === 200) {
      ElMessage.success(`${serviceName} ${action} 成功`)
      await loadServices()
    } else {
      ElMessage.error(res.message || `${serviceName} ${action} 失败`)
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || `${serviceName} ${action} 失败`)
  }
}

const setAutostart = async (serviceName, enabled) => {
  try {
    const res = await request.post('/services/autostart', {
      server_id: serverId.value,
      service_name: serviceName,
      enabled,
    })
    if (res.code === 200) {
      ElMessage.success(`${serviceName} 自启已${enabled ? '开启' : '关闭'}`)
      await loadServices()
    } else {
      ElMessage.error(res.message || '修改自启失败')
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '修改自启失败')
  }
}

const createServer = async () => {
  if (!newServer.value.ip || !newServer.value.ssh_username || !newServer.value.ssh_password) {
    ElMessage.warning('请填写 IP、SSH 用户与密码')
    return
  }
  savingServer.value = true
  try {
    const res = await request.post('/servers/', {
      hostname: newServer.value.ip,
      ip: newServer.value.ip,
      port: newServer.value.port,
      auth_type: 'password',
      ssh_username: newServer.value.ssh_username,
      ssh_password: newServer.value.ssh_password,
      connect_timeout: 15,
    })
    if (res.code === 200) {
      const sid = res.data?.server_id
      if (sid) {
        await request.post(`/servers/${sid}/ssh-test`)
      }
      ElMessage.success('服务器接入成功')
      newServer.value = { ip: '', port: 22, ssh_username: '', ssh_password: '' }
      await loadServers()
      await loadServices()
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '服务器接入失败')
  } finally {
    savingServer.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadContext(), loadServers()])
  await loadServices()
})
</script>

<style scoped>
.stack-form :deep(.el-form-item) {
  margin-bottom: 18px;
}

.stack-card.compact {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

@media (max-width: 768px) {
  .action-row {
    justify-content: flex-start;
  }
}
</style>
