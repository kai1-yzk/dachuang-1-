<template>
  <div class="app-page">
    <section class="page-hero">
      <div class="page-hero__content">
        <div class="page-eyebrow">Backup & Restore</div>
        <h2 class="page-title">用受控流程管理备份任务与恢复动作</h2>
        <p class="page-subtitle">把备份创建、恢复确认和任务跟踪放进同一页面，降低恢复场景下的信息切换成本。</p>
      </div>
      <div class="page-hero__aside">
        <div class="hero-stat">
          <div class="hero-stat__label">任务总数</div>
          <div class="hero-stat__value">{{ jobs.length }}</div>
        </div>
      </div>
    </section>

    <div class="page-grid page-grid--sidebar">
      <div class="stack-card">
        <el-card class="section-card">
          <template #header><div class="section-head__title">创建备份</div></template>
          <el-form label-width="100px">
            <el-form-item label="目标服务器">
              <el-select v-model="form.serverId" placeholder="请选择">
                <el-option v-for="s in servers" :key="s.id" :label="`${s.hostname} (${s.ip})`" :value="s.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="备份类型">
              <el-radio-group v-model="form.backupType">
                <el-radio label="config">配置</el-radio>
                <el-radio label="database">数据库</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="远端目录">
              <el-input v-model="form.targetPath" />
            </el-form-item>
            <el-button type="primary" :disabled="!canOperate" :loading="creating" @click="createJob">立即备份</el-button>
          </el-form>
        </el-card>

        <el-card class="section-card">
          <template #header><div class="section-head__title">恢复备份</div></template>
          <el-form label-width="100px">
            <el-form-item label="产物ID">
              <el-input-number v-model="restore.artifactId" :min="1" style="width: 100%" />
            </el-form-item>
            <el-form-item>
              <el-checkbox v-model="restore.confirm">我已确认恢复风险</el-checkbox>
            </el-form-item>
            <el-button type="danger" :disabled="!canOperate" @click="doRestore">执行恢复</el-button>
          </el-form>
        </el-card>
      </div>

      <el-card class="section-card">
          <template #header>
            <div class="section-head">
              <div>
                <div class="section-head__title">备份任务列表</div>
                <div class="section-head__meta">查看任务状态、目标目录和更新时间</div>
              </div>
              <el-button size="small" @click="loadJobs">刷新</el-button>
            </div>
          </template>
          <el-table :data="jobs" size="small" v-loading="loading">
            <el-table-column prop="id" label="任务ID" width="90" />
            <el-table-column prop="server_id" label="服务器" width="90" />
            <el-table-column prop="backup_type" label="类型" width="120" />
            <el-table-column prop="target_path" label="目标目录" min-width="160" />
            <el-table-column prop="status" label="状态" width="110">
              <template #default="scope">
                <el-tag :type="statusType(scope.row.status)">{{ scope.row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="updated_at" label="更新时间" width="180" />
          </el-table>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

const role = ref('operator')
const servers = ref([])
const jobs = ref([])
const loading = ref(false)
const creating = ref(false)

const form = reactive({
  serverId: undefined,
  backupType: 'config',
  targetPath: '/tmp/aiops_backup',
})

const restore = reactive({
  artifactId: undefined,
  confirm: false,
})

const canOperate = computed(() => ['tenant_admin', 'platform_admin', 'superadmin'].includes(role.value))

const statusType = (status) => {
  if (status === 'success') return 'success'
  if (status === 'running') return 'warning'
  if (status === 'failed') return 'danger'
  return 'info'
}

const loadContext = async () => {
  const res = await request.get('/tenants/context')
  if (res.code === 200) role.value = res.data?.role || 'operator'
}

const loadServers = async () => {
  const res = await request.get('/servers/')
  if (res.code === 200) {
    servers.value = res.data || []
    if (!form.serverId && servers.value.length) form.serverId = servers.value[0].id
  }
}

const loadJobs = async () => {
  loading.value = true
  try {
    const res = await request.get('/backup/jobs', { params: { limit: 100 } })
    if (res.code === 200) jobs.value = res.data || []
  } finally {
    loading.value = false
  }
}

const createJob = async () => {
  if (!form.serverId) {
    ElMessage.warning('请先接入并选择服务器')
    return
  }
  creating.value = true
  try {
    const res = await request.post('/backup/jobs', {
      server_id: form.serverId,
      backup_type: form.backupType,
      target_path: form.targetPath,
    })
    if (res.code === 200) {
      ElMessage.success('备份任务已执行')
      await loadJobs()
    } else {
      ElMessage.error(res.message || '备份任务执行失败')
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '备份任务执行失败')
  } finally {
    creating.value = false
  }
}

const doRestore = async () => {
  try {
    const res = await request.post('/backup/restore', {
      artifact_id: restore.artifactId,
      confirm: restore.confirm,
    })
    if (res.code === 200) {
      ElMessage.success('恢复任务已提交')
    } else {
      ElMessage.error(res.message || '恢复任务提交失败')
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '恢复任务提交失败')
  }
}

onMounted(async () => {
  await Promise.all([loadContext(), loadServers()])
  await loadJobs()
})
</script>

<style scoped>
.stack-card {
  gap: 18px;
}
</style>
