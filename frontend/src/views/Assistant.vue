<template>
  <div class="assistant-page">
    <el-row :gutter="16">
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <div class="card-title">数字运维助手</div>
          </template>

          <el-form label-width="90px">
            <el-form-item label="目标服务器">
              <el-select v-model="serverId" placeholder="可选" style="width: 100%">
                <el-option v-for="srv in servers" :key="srv.id" :label="`${srv.hostname} (${srv.ip})`" :value="srv.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="问题">
              <el-input v-model="question" type="textarea" :rows="6" placeholder="例如：nginx 不可用，如何排查并恢复？" />
            </el-form-item>
            <el-button type="primary" :loading="querying" @click="askAssistant">生成建议</el-button>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>
            <div class="header-bar">
              <span class="card-title">回答与建议</span>
              <el-tag v-if="result" :type="riskTagType(result.risk_level)">{{ result.risk_level }}</el-tag>
            </div>
          </template>

          <div v-if="result">
            <el-alert type="info" :closable="false" :title="result.answer" show-icon />

            <div class="section-title mt-16">建议列表</div>
            <el-table :data="result.suggestions || []" size="small">
              <el-table-column prop="title" label="建议" min-width="180" />
              <el-table-column prop="risk_level" label="风险" width="90" />
              <el-table-column prop="command" label="建议命令" min-width="180">
                <template #default="scope">
                  {{ scope.row.command || '-' }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="120">
                <template #default="scope">
                  <el-button
                    size="small"
                    type="warning"
                    :disabled="!scope.row.requires_approval"
                    @click="approveSuggestion(scope.row)"
                  >
                    审批
                  </el-button>
                </template>
              </el-table-column>
            </el-table>

            <div class="section-title mt-16">引用证据</div>
            <el-table :data="result.citations || []" size="small">
              <el-table-column prop="source" label="来源" width="100" />
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="text" label="内容" min-width="280" show-overflow-tooltip />
            </el-table>
          </div>

          <el-empty v-else description="输入问题后查看助手建议" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

const servers = ref([])
const serverId = ref(null)
const question = ref('')
const querying = ref(false)
const result = ref(null)

const loadServers = async () => {
  const res = await request.get('/servers/')
  if (res.code === 200) {
    servers.value = res.data || []
    if (!serverId.value && servers.value.length) {
      serverId.value = servers.value[0].id
    }
  }
}

const riskTagType = (level) => {
  if (level === 'high') return 'danger'
  if (level === 'medium') return 'warning'
  return 'success'
}

const askAssistant = async () => {
  if (!question.value.trim()) {
    ElMessage.warning('请输入问题')
    return
  }
  querying.value = true
  try {
    const res = await request.post('/assistant/query', {
      question: question.value.trim(),
      server_id: serverId.value || undefined,
    })
    if (res.code === 200) {
      result.value = res.data
    }
  } finally {
    querying.value = false
  }
}

const approveSuggestion = async (suggestion) => {
  const res = await request.post('/assistant/suggestion/approve', { suggestion })
  if (res.code === 200) {
    ElMessage.success('建议已审批并记录')
  }
}

onMounted(() => {
  loadServers()
})
</script>

<style scoped>
.mt-16 {
  margin-top: 16px;
}

.card-title {
  font-weight: 600;
}

.section-title {
  font-weight: 600;
  margin-bottom: 8px;
}

.header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
