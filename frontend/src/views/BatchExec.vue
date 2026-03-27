<template>
  <div class="batch-page">
    <el-row :gutter="16">
      <el-col :span="9">
        <el-card shadow="hover">
          <template #header><span class="title">创建批量命令</span></template>
          <el-form label-width="90px">
            <el-form-item label="目标服务器">
              <el-select v-model="selectedServers" multiple collapse-tags placeholder="选择服务器" style="width: 100%">
                <el-option v-for="s in servers" :key="s.id" :label="`${s.hostname} (${s.ip})`" :value="s.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="命令">
              <el-input v-model="command" type="textarea" :rows="4" placeholder="例如: systemctl status nginx" />
            </el-form-item>
            <el-button type="primary" :disabled="!canOperate" @click="createJob">提交审批</el-button>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="15">
        <el-card shadow="hover">
          <template #header>
            <div class="header-line">
              <span class="title">批量任务列表</span>
              <el-button size="small" @click="loadJobs">刷新</el-button>
            </div>
          </template>
          <el-table :data="jobs" size="small" v-loading="loading">
            <el-table-column prop="id" label="任务ID" width="90" />
            <el-table-column prop="command_text" label="命令" min-width="220" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="130">
              <template #default="scope">
                <el-tag :type="statusType(scope.row.status)">{{ scope.row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="170" />
            <el-table-column label="审批" width="170">
              <template #default="scope">
                <el-space>
                  <el-button
                    size="small"
                    type="success"
                    :disabled="!canOperate || scope.row.status !== 'pending_approval'"
                    @click="approve(scope.row.id, true)"
                  >通过</el-button>
                  <el-button
                    size="small"
                    type="danger"
                    :disabled="!canOperate || scope.row.status !== 'pending_approval'"
                    @click="approve(scope.row.id, false)"
                  >拒绝</el-button>
                </el-space>
              </template>
            </el-table-column>
            <el-table-column label="结果" width="90">
              <template #default="scope">
                <el-button size="small" @click="viewResults(scope.row.id)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="showResults" width="760px" title="任务执行结果">
      <el-table :data="results" size="small" max-height="460">
        <el-table-column prop="server_id" label="服务器" width="90" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column prop="result_json" label="结果JSON" min-width="420" show-overflow-tooltip />
        <el-table-column prop="created_at" label="时间" width="160" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

const role = ref('operator')
const servers = ref([])
const selectedServers = ref([])
const command = ref('')
const jobs = ref([])
const results = ref([])
const loading = ref(false)
const showResults = ref(false)

const canOperate = computed(() => ['tenant_admin', 'platform_admin', 'superadmin'].includes(role.value))

const statusType = (status) => {
  if (status === 'success') return 'success'
  if (status === 'pending_approval' || status === 'running') return 'warning'
  if (status === 'failed' || status === 'rejected') return 'danger'
  return 'info'
}

const loadContext = async () => {
  const res = await request.get('/tenants/context')
  if (res.code === 200) role.value = res.data?.role || 'operator'
}

const loadServers = async () => {
  const res = await request.get('/servers/')
  if (res.code === 200) servers.value = res.data || []
}

const loadJobs = async () => {
  loading.value = true
  try {
    const res = await request.get('/batch/jobs', { params: { limit: 200 } })
    if (res.code === 200) jobs.value = res.data || []
  } finally {
    loading.value = false
  }
}

const createJob = async () => {
  const res = await request.post('/batch/jobs', {
    command: command.value,
    server_ids: selectedServers.value,
  })
  if (res.code === 200) {
    ElMessage.success('任务已创建，等待审批')
    command.value = ''
    selectedServers.value = []
    await loadJobs()
  }
}

const approve = async (jobId, agree) => {
  const res = await request.post(`/batch/jobs/${jobId}/approve`, { approve: agree })
  if (res.code === 200) {
    ElMessage.success(agree ? '审批通过并开始执行' : '任务已拒绝')
    await loadJobs()
  }
}

const viewResults = async (jobId) => {
  const res = await request.get(`/batch/jobs/${jobId}/results`)
  if (res.code === 200) {
    results.value = res.data || []
    showResults.value = true
  }
}

onMounted(async () => {
  await Promise.all([loadContext(), loadServers()])
  await loadJobs()
})
</script>

<style scoped>
.title {
  font-weight: 600;
}

.header-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
