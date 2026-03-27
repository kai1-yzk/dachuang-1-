<template>
  <div class="panel-page">
    <el-card shadow="never" class="toolbar-card">
      <div class="toolbar">
        <el-select v-model="serverId" placeholder="选择服务器" style="width: 260px" @change="loadServices">
          <el-option v-for="s in servers" :key="s.id" :label="`${s.hostname} (${s.ip})`" :value="s.id" />
        </el-select>
        <el-button @click="loadServices">刷新状态</el-button>
      </div>
    </el-card>

    <el-card shadow="hover" class="mt16">
      <template #header>
        <div class="header-row">
          <span>服务管理</span>
          <el-tag type="info">支持 nginx/mysql/redis/docker/ssh/cron</el-tag>
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
  } finally {
    loading.value = false
  }
}

const control = async (serviceName, action) => {
  const res = await request.post('/services/control', {
    server_id: serverId.value,
    service_name: serviceName,
    action,
  })
  if (res.code === 200) {
    ElMessage.success(`${serviceName} ${action} 成功`)
    await loadServices()
  }
}

const setAutostart = async (serviceName, enabled) => {
  const res = await request.post('/services/autostart', {
    server_id: serverId.value,
    service_name: serviceName,
    enabled,
  })
  if (res.code === 200) {
    ElMessage.success(`${serviceName} 自启已${enabled ? '开启' : '关闭'}`)
    await loadServices()
  }
}

onMounted(async () => {
  await Promise.all([loadContext(), loadServers()])
  await loadServices()
})
</script>

<style scoped>
.panel-page {
  display: flex;
  flex-direction: column;
}

.toolbar-card {
  border-radius: 10px;
}

.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.mt16 {
  margin-top: 16px;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}
</style>
