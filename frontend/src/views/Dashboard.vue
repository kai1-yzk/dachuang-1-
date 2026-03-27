<template>
  <div class="bt-dashboard">
    <div class="screen-head">
      <div>
        <h2>监控大屏</h2>
        <p>数据源为实时采集的服务器指标、审计日志和 Kubernetes 集群状态</p>
      </div>
      <el-space>
        <el-tag :type="onlineTagType">在线 {{ onlineCount }}/{{ totalCount }}</el-tag>
        <el-button @click="fetchDashboardData">立即刷新</el-button>
      </el-space>
    </div>

    <el-row :gutter="14">
      <el-col :span="6" v-for="item in summaryCards" :key="item.metricKey">
        <el-card class="metric-card" shadow="hover" @click="goMetric(item.metricKey)">
          <div class="metric-title">{{ item.title }}</div>
          <div class="metric-value">{{ item.value }} <small>{{ item.unit }}</small></div>
          <el-progress :percentage="Math.min(100, Math.max(0, Number(item.value) || 0))" :show-text="false" :stroke-width="8" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="14" class="mt-14">
      <el-col :span="14">
        <el-card class="block-card" shadow="hover">
          <template #header>
            <div class="card-head"><span>故障预测</span><el-tag type="warning">模型推理结果</el-tag></div>
          </template>
          <el-descriptions v-if="prediction.alert" :column="2" border size="small">
            <el-descriptions-item label="故障类型">{{ prediction.alert.fault_type }}</el-descriptions-item>
            <el-descriptions-item label="风险等级"><el-tag :type="riskType(prediction.alert.risk_level)">{{ prediction.alert.risk_level }}</el-tag></el-descriptions-item>
            <el-descriptions-item label="预测提前量">{{ prediction.alert.lead_time_minutes }} 分钟</el-descriptions-item>
            <el-descriptions-item label="异常分数">{{ Number(prediction.anomaly_score || 0).toFixed(3) }}</el-descriptions-item>
            <el-descriptions-item label="故障起因" :span="2">{{ prediction.alert.cause }}</el-descriptions-item>
            <el-descriptions-item label="应急处置" :span="2">{{ prediction.alert.emergency_solution }}</el-descriptions-item>
            <el-descriptions-item label="预防建议" :span="2">{{ prediction.alert.prevention_advice }}</el-descriptions-item>
          </el-descriptions>
          <el-empty v-else description="暂无可用预测" />
        </el-card>
      </el-col>

      <el-col :span="10">
        <el-card class="block-card" shadow="hover">
          <template #header>
            <div class="card-head"><span>Kubernetes 概览</span><el-tag :type="k8s.available ? 'success' : 'info'">{{ k8s.available ? '已连接' : '未连接' }}</el-tag></div>
          </template>
          <div v-if="k8s.available" class="k8s-grid">
            <div class="k8s-item"><b>{{ k8s.summary.nodes_ready }}</b><span>Ready 节点</span></div>
            <div class="k8s-item"><b>{{ k8s.summary.nodes_total }}</b><span>节点总数</span></div>
            <div class="k8s-item"><b>{{ k8s.summary.pods_running }}</b><span>Running Pods</span></div>
            <div class="k8s-item"><b>{{ k8s.summary.deployments_total }}</b><span>Deployments</span></div>
          </div>
          <el-alert v-else type="info" :closable="false" :title="k8s.message || '未检测到 kubectl 集群上下文'" />
          <el-table v-if="k8s.available" :data="k8s.nodes || []" size="small" max-height="200" style="margin-top: 10px">
            <el-table-column prop="name" label="节点" min-width="140" />
            <el-table-column prop="status" label="状态" width="120" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="14" class="mt-14">
      <el-col :span="24">
        <el-card class="block-card" shadow="hover">
          <template #header>
            <div class="card-head"><span>安全拦截事件</span><el-tag type="danger">自动拦截启用</el-tag></div>
          </template>
          <el-timeline>
            <el-timeline-item v-for="(activity, index) in activities" :key="index" :timestamp="activity.timestamp" :color="activity.color || '#f56c6c'">
              {{ activity.content }}
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import request from '../utils/request'

const router = useRouter()

const summaryCards = ref([
  { metricKey: 'cpu', title: 'CPU 负载', value: '0.0', unit: '%', icon: 'Cpu', iconClass: 'icon-blue', trend: 0 },
  { metricKey: 'memory', title: '内存使用', value: '0.0', unit: '%', icon: 'Odometer', iconClass: 'icon-green', trend: 0 },
  { metricKey: 'disk', title: '磁盘使用', value: '0.0', unit: '%', icon: 'PieChart', iconClass: 'icon-purple', trend: 0 },
  { metricKey: 'network', title: '网络吞吐', value: '0.0', unit: 'MB', icon: 'Connection', iconClass: 'icon-orange', trend: 0 },
])

const aiStatus = ref({ type: 'success', text: '系统平稳' })
const prediction = ref({})
const activities = ref([])
const k8s = ref({ available: false, summary: {}, nodes: [] })
let timer = null

const onlineCount = ref(0)
const totalCount = ref(0)

const onlineTagType = computed(() => (totalCount.value > 0 && onlineCount.value === totalCount.value ? 'success' : 'warning'))

const safeTrend = (next, prev) => {
  if (!prev || prev === 0) return 0
  return Number((((next - prev) / prev) * 100).toFixed(1))
}

const riskType = (riskLevel) => {
  if (riskLevel === '高') return 'danger'
  if (riskLevel === '中') return 'warning'
  return 'success'
}

const goMetric = (metric) => {
  router.push({ path: '/metrics/trend', query: { metric } })
}

const applyDashboardData = (data) => {
  const summary = data?.summary || {}
  const trend = data?.trend || []

  const prevCpu = Number(summaryCards.value[0].value || 0)
  const prevMem = Number(summaryCards.value[1].value || 0)
  const prevDisk = Number(summaryCards.value[2].value || 0)
  const prevNet = Number(summaryCards.value[3].value || 0)
  const cpu = Number(summary.cpu || 0)
  const memory = Number(summary.memory || 0)
  const disk = Number(summary.disk || 0)
  const network = Number(summary.network || 0)

  summaryCards.value = [
    { ...summaryCards.value[0], value: cpu.toFixed(1), trend: safeTrend(cpu, prevCpu) },
    { ...summaryCards.value[1], value: memory.toFixed(1), trend: safeTrend(memory, prevMem) },
    { ...summaryCards.value[2], value: disk.toFixed(1), trend: safeTrend(disk, prevDisk) },
    { ...summaryCards.value[3], value: network.toFixed(1), trend: safeTrend(network, prevNet) },
  ]

  const totalServers = data?.servers?.total || 0
  const onlineServers = data?.servers?.online || 0
  totalCount.value = totalServers
  onlineCount.value = onlineServers
  aiStatus.value = onlineServers === totalServers && totalServers > 0
    ? { type: 'success', text: `在线 ${onlineServers}/${totalServers}` }
    : { type: 'warning', text: `在线 ${onlineServers}/${totalServers} · 风险自动拦截中` }

  const security = data?.security || {}
  const blockedEvents = security?.recent_blocked_events || []
  if (blockedEvents.length) {
    activities.value = blockedEvents.map(item => ({
      content: `已拦截: ${item.action || 'unknown-action'} / ${item.result || 'blocked'} / ${item.detail || 'risk detected'}`,
      timestamp: item.time || '刚刚',
      type: 'danger',
      color: '#f56c6c',
    }))
    return
  }

  const collectResults = data?.collect_result || []
  activities.value = collectResults.slice(0, 8).map(item => {
    if (item.ok) {
      return {
        content: `采集成功: 服务器 ${item.server_id} CPU=${Number(item?.metrics?.cpu || 0).toFixed(1)}%`,
        timestamp: '刚刚',
        type: 'success',
      }
    }
    return {
      content: `采集失败: 服务器 ${item.server_id} ${item.error || 'unknown error'}`,
      timestamp: '刚刚',
      type: 'danger',
      color: '#f56c6c',
    }
  })
}

const fetchDashboardData = async () => {
  try {
    const [metricsRes, securityRes, k8sRes] = await Promise.all([
      request.get('/metrics/dashboard', {
        params: {
          collect_now: 0,
          points: 12,
        }
      }),
      request.get('/audit/security-overview', {
        params: { limit: 300 }
      }),
      request.get('/metrics/k8s-overview')
    ])

    if (metricsRes.code === 200) {
      applyDashboardData({
        ...metricsRes.data,
        security: securityRes?.code === 200 ? securityRes.data : {},
      })

      const firstServer = metricsRes?.data?.servers?.items?.[0]
      if (firstServer?.id) {
        const predictRes = await request.get(`/ai/predict-alert/${firstServer.id}`)
        if (predictRes.code === 200) {
          prediction.value = predictRes.data || {}
        }
      }
    }

    if (k8sRes?.code === 200) {
      k8s.value = k8sRes.data || { available: false, summary: {}, nodes: [] }
    }
  } catch (e) {
    aiStatus.value = { type: 'danger', text: '采集失败' }
  }
}

onMounted(() => {
  fetchDashboardData()
  timer = setInterval(fetchDashboardData, 5000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.screen-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.screen-head h2 {
  margin: 0;
}

.screen-head p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 12px;
}

.metric-card {
  cursor: pointer;
  border-radius: 10px;
}

.metric-title {
  color: #64748b;
  font-size: 13px;
}

.metric-value {
  margin: 8px 0 12px;
  font-size: 28px;
  font-weight: 700;
  color: #0f172a;
}

.metric-value small {
  font-size: 13px;
  color: #64748b;
}

.block-card {
  border-radius: 12px;
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}

.k8s-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.k8s-item {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.k8s-item b {
  color: #1d4ed8;
  font-size: 20px;
}

.k8s-item span {
  color: #64748b;
  font-size: 12px;
}

.mt-14 {
  margin-top: 14px;
}
</style>
