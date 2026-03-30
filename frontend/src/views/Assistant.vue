<template>
  <div class="app-page">
    <section class="page-hero">
      <div class="page-hero__content">
        <div class="page-eyebrow">Ops Assistant</div>
        <h2 class="page-title">先生成执行方案，再让人确认并安全落地</h2>
        <p class="page-subtitle">把命令规划、风险说明、二次确认和执行回显串成闭环，帮助你更放心地使用智能助手。</p>
      </div>
      <div class="page-hero__aside">
        <div class="hero-stat">
          <div class="hero-stat__label">目标服务器</div>
          <div class="hero-stat__value">{{ serverId || '--' }}</div>
        </div>
      </div>
    </section>

    <div class="page-grid page-grid--sidebar">
      <el-card class="section-card">
          <template #header>
            <div class="section-head__title">智能助手运维操作</div>
          </template>

          <el-form label-width="90px">
            <el-form-item label="目标服务器">
              <el-select v-model="serverId" placeholder="可选" style="width: 100%">
                <el-option v-for="srv in servers" :key="srv.id" :label="`${srv.hostname} (${srv.ip})`" :value="srv.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="运维需求">
              <el-input
                v-model="commandText"
                type="textarea"
                :rows="6"
                placeholder="可用自然语言描述意图，或直接写命令。例如：查看磁盘占用 / df -h"
              />
            </el-form-item>
            <el-button type="primary" :loading="planning" @click="buildPlan">生成执行方案</el-button>
          </el-form>
        </el-card>

      <el-card class="section-card">
          <template #header>
            <div class="section-head">
              <div>
                <div class="section-head__title">执行方案与确认</div>
                <div class="section-head__meta">先理解风险，再决定是否执行</div>
              </div>
              <el-tag v-if="plan" :type="riskTagType(plan.risk.level)">{{ plan.risk.level }}</el-tag>
            </div>
          </template>

          <div v-if="plan">
            <el-alert
              v-if="plan.ai_source === 'fallback'"
              type="warning"
              :closable="false"
              title="当前未配置大模型 API 密钥（DEEPSEEK_API_KEY 或 AI_API_KEY），以下为本地模板方案；配置密钥后可由 AI 生成命令与步骤。"
              show-icon
              class="mb-16"
            />
            <el-alert type="info" :closable="false" :title="plan.ask" show-icon />

            <div v-if="plan.solution?.resolved_command" class="section-title mt-16">解析后的执行命令</div>
            <el-input
              v-if="plan.solution?.resolved_command"
              :model-value="plan.solution.resolved_command"
              type="textarea"
              :rows="2"
              readonly
              class="mb-16"
            />

            <div class="section-title mt-16">解决方法（执行步骤）</div>
            <el-steps direction="vertical" :active="plan.solution.steps.length">
              <el-step v-for="(step, idx) in plan.solution.steps" :key="idx" :title="step" />
            </el-steps>

            <div class="section-title mt-16">预期效果</div>
            <el-alert type="success" :closable="false" :title="plan.solution.expected_effect" />

            <div class="section-title mt-16">风险说明</div>
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="风险等级">{{ plan.risk.level }}</el-descriptions-item>
              <el-descriptions-item label="风险分值">{{ Number(plan.risk.score || 0).toFixed(2) }}</el-descriptions-item>
              <el-descriptions-item label="风险后果">{{ plan.risk.risk_consequence }}</el-descriptions-item>
            </el-descriptions>

            <div class="mt-16 action-row">
              <el-button type="primary" :loading="executing" @click="executeWithConsent">同意并执行</el-button>
              <el-button @click="resetPlan">取消</el-button>
            </div>

            <div class="section-title mt-16">执行结果回显</div>
            <el-input v-model="executionOutput" type="textarea" :rows="10" readonly />
          </div>

          <el-empty v-else description="输入命令并生成方案后，确认是否执行" />
        </el-card>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../utils/request'

const servers = ref([])
const serverId = ref(null)
const commandText = ref('')
const planning = ref(false)
const executing = ref(false)
const plan = ref(null)
const executionOutput = ref('')

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
  const l = String(level || '').toLowerCase()
  if (l === 'high') return 'danger'
  if (l === 'medium') return 'warning'
  return 'success'
}

const buildPlan = async () => {
  if (!commandText.value.trim()) {
    ElMessage.warning('请输入操作命令')
    return
  }
  if (!serverId.value) {
    ElMessage.warning('请选择目标服务器')
    return
  }
  planning.value = true
  try {
    const res = await request.post('/assistant/ops-plan', {
      command: commandText.value.trim(),
      server_id: serverId.value,
    })
    if (res.code === 200) {
      plan.value = res.data
      executionOutput.value = ''
    } else {
      ElMessage.error(res.message || '生成方案失败')
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '生成方案失败')
  } finally {
    planning.value = false
  }
}

const executeWithConsent = async () => {
  if (!plan.value?.execution_token) return

  let highRiskConfirmed = false
  if (plan.value?.risk?.is_high_risk) {
    try {
      await ElMessageBox.confirm(
        `极高风险操作，可能后果：${plan.value.risk.risk_consequence}。是否继续执行？`,
        '二次确认',
        { type: 'error', confirmButtonText: '确认执行', cancelButtonText: '取消' }
      )
      highRiskConfirmed = true
    } catch {
      return
    }
  }

  executing.value = true
  try {
    const res = await request.post('/assistant/ops-execute', {
      execution_token: plan.value.execution_token,
      consent: true,
      high_risk_confirmed: highRiskConfirmed,
    })
    if (res.code === 200) {
      const data = res.data || {}
      executionOutput.value = `exit_status=${data.exit_status}\n\n[stdout]\n${data.stdout || ''}\n\n[stderr]\n${data.stderr || ''}`
      ElMessage.success('命令执行完成')
    } else {
      executionOutput.value = res.message || '执行失败'
      ElMessage.error(res.message || '执行失败')
    }
  } catch (e) {
    executionOutput.value = e?.response?.data?.message || '执行失败'
    ElMessage.error(e?.response?.data?.message || '执行失败')
  } finally {
    executing.value = false
  }
}

const resetPlan = () => {
  plan.value = null
  executionOutput.value = ''
}

onMounted(() => {
  loadServers()
})
</script>

<style scoped>
.section-title {
  font-weight: 600;
  margin-bottom: 8px;
}

.action-row {
  display: flex;
  gap: 10px;
}

.mt-16 {
  margin-top: 16px;
}

.mb-16 {
  margin-bottom: 16px;
}
</style>
