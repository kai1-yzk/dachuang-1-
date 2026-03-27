<template>
  <div class="servers-page">
    <el-row :gutter="16">
      <el-col :span="9">
        <el-card shadow="hover">
          <template #header>
            <div class="card-title">新增服务器</div>
          </template>
          <el-form :model="form" label-width="100px">
            <el-form-item label="服务器IP">
              <el-input v-model="form.ip" />
            </el-form-item>
            <el-form-item label="端口">
              <el-input-number v-model="form.port" :min="1" :max="65535" style="width: 100%" />
            </el-form-item>
            <el-form-item label="登录账号">
              <el-input v-model="form.ssh_username" />
            </el-form-item>
            <el-form-item label="登录密码">
              <el-input v-model="form.ssh_password" type="password" show-password />
            </el-form-item>
            <el-button type="primary" :loading="saving" :disabled="!isAdmin" @click="createServer">新增并接入</el-button>
            <div class="tip">仅服务器管理员可新增/删除，密码后端加密存储。</div>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="15">
        <el-card shadow="hover">
          <template #header>
            <div class="header-row">
              <span class="card-title">服务器列表</span>
              <el-button size="small" @click="loadServers">刷新</el-button>
            </div>
          </template>

          <el-table :data="servers" size="small">
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="hostname" label="主机名" min-width="140" />
            <el-table-column prop="ip" label="IP" width="140" />
            <el-table-column prop="port" label="端口" width="80" />
            <el-table-column prop="status" label="状态" width="100" />
            <el-table-column label="操作" width="120">
              <template #default="scope">
                <el-button
                  type="danger"
                  size="small"
                  :disabled="!isAdmin"
                  @click="deleteServer(scope.row)"
                >删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

const servers = ref([])
const saving = ref(false)
const tenantContext = ref(null)
const form = ref({
  hostname: '',
  ip: '',
  port: 22,
  ssh_username: '',
  ssh_password: '',
})

const isAdmin = computed(() => {
  const role = tenantContext.value?.role || 'operator'
  return ['tenant_admin', 'platform_admin', 'superadmin'].includes(role)
})

const loadContext = async () => {
  const res = await request.get('/tenants/context')
  if (res.code === 200) {
    tenantContext.value = res.data || {}
  }
}

const loadServers = async () => {
  const res = await request.get('/servers/')
  if (res.code === 200) {
    servers.value = res.data || []
  }
}

const createServer = async () => {
  if (!isAdmin.value) {
    ElMessage.error('仅管理员可新增服务器')
    return
  }
  if (!form.value.ip || !form.value.ssh_username || !form.value.ssh_password) {
    ElMessage.warning('请完整填写服务器信息')
    return
  }

  saving.value = true
  try {
    const res = await request.post('/servers/', {
      hostname: form.value.hostname || form.value.ip,
      ip: form.value.ip,
      port: form.value.port,
      auth_type: 'password',
      ssh_username: form.value.ssh_username,
      ssh_password: form.value.ssh_password,
      connect_timeout: 15,
    })
    if (res.code === 200) {
      ElMessage.success('服务器新增成功')
      form.value = { hostname: '', ip: '', port: 22, ssh_username: '', ssh_password: '' }
      await loadServers()
    }
  } finally {
    saving.value = false
  }
}

const deleteServer = async (row) => {
  if (!isAdmin.value) {
    ElMessage.error('仅管理员可删除服务器')
    return
  }

  try {
    await ElMessageBox.confirm('是否确认删除该服务器？删除后将无法监控该服务器数据。', '删除确认', {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  const res = await request.delete(`/servers/${row.id}`, { data: { confirm: true } })
  if (res.code === 200) {
    ElMessage.success('删除成功')
    await loadServers()
  }
}

onMounted(async () => {
  await Promise.all([loadContext(), loadServers()])
})
</script>

<style scoped>
.tip {
  margin-top: 8px;
  color: #909399;
  font-size: 12px;
}

.card-title {
  font-weight: 600;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
