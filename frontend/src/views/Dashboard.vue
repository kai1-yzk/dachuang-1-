<template>
  <div class="app-page dashboard-page">
    <section class="page-hero">
      <div class="page-hero__content">
        <div class="page-eyebrow">AIOps Overview</div>
        <h2 class="page-title">统一观察指标、异常与基础设施健康</h2>
        <p class="page-subtitle">
          将实时采集、AI 故障预测、安全拦截和 Kubernetes 运行态放进同一张信息地图，帮助你更快判断系统状态与下一步动作。
        </p>
        <div class="action-row">
          <el-button type="primary" @click="fetchDashboardData">立即刷新</el-button>
          <el-button plain @click="goMetric('cpu')">查看资源趋势</el-button>
        </div>
      </div>

      <div class="page-hero__aside">
        <div class="hero-stat">
          <div class="hero-stat__label">服务器在线率</div>
          <div class="hero-stat__value">{{ onlineCount }}/{{ totalCount || 0 }}</div>
        </div>
        <div class="hero-stat">
          <div class="hero-stat__label">AI 风险状态</div>
          <div class="hero-stat__value">{{ aiStatus.text }}</div>
        </div>
        <div class="hero-stat">
          <div class="hero-stat__label">Kubernetes</div>
          <div class="hero-stat__value">{{ k8s.available ? '已连接' : '未连接' }}</div>
        </div>
      </div>
    </section>

    <section class="metric-grid">
      <article v-for="item in summaryCards" :key="item.metricKey" class="metric-card surface-card" @click="goMetric(item.metricKey)">
        <div class="metric-card__head">
          <div>
            <div class="metric-card__title">{{ item.title }}</div>
            <div class="metric-card__value">{{ item.value }} <small>{{ item.unit }}</small></div>
          </div>
          <div :class="['metric-card__trend', item.trend >= 0 ? 'is-up' : 'is-down']">
            {{ item.trend >= 0 ? '+' : '' }}{{ item.trend }}%
          </div>
        </div>
        <el-progress :percentage="Math.min(100, Math.max(0, Number(item.value) || 0))" :show-text="false" :stroke-width="10" />
        <div class="metric-card__foot">
          <span>点击查看详细趋势</span>
          <span>{{ item.description }}</span>
        </div>
      </article>
    </section>

    <section class="grid-two">
      <el-card class="section-card chart-card">
        <template #header>
          <div class="section-head">
            <div>
              <div class="section-head__title">核心指标趋势</div>
              <div class="section-head__meta">过去 12 个采样点内 CPU、内存、磁盘与网络吞吐变化</div>
            </div>
            <div class="data-chip">实时采样</div>
          </div>
        </template>
        <div ref="chartRef" class="trend-chart"></div>
      </el-card>

      <el-card class="section-card prediction-card">
        <template #header>
          <div class="section-head">
            <div>
              <div class="section-head__title">故障预测</div>
              <div class="section-head__meta">来自模型推理的最新风险判断与处置建议</div>
            </div>
            <el-tag type="warning" round>模型推理结果</el-tag>
          </div>
        </template>

        <div v-if="prediction.alert" class="prediction-layout">
          <div class="prediction-score">
            <span class="prediction-score__label">异常分数</span>
            <span class="prediction-score__value">{{ Number(prediction.anomaly_score || 0).toFixed(3) }}</span>
            <el-tag :type="riskType(prediction.alert.risk_level)" round>{{ prediction.alert.risk_level }} 风险</el-tag>
          </div>

          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="故障类型">{{ prediction.alert.fault_type }}</el-descriptions-item>
            <el-descriptions-item label="预测提前量">{{ prediction.alert.lead_time_minutes }} 分钟</el-descriptions-item>
            <el-descriptions-item label="故障起因">{{ prediction.alert.cause }}</el-descriptions-item>
            <el-descriptions-item label="应急处置">{{ prediction.alert.emergency_solution }}</el-descriptions-item>
            <el-descriptions-item label="预防建议">{{ prediction.alert.prevention_advice }}</el-descriptions-item>
          </el-descriptions>
        </div>
        <el-empty v-else description="暂无可用预测" />
      </el-card>
    </section>

    <section class="grid-two">
      <el-card class="section-card k8s-card">
        <template #header>
          <div class="section-head">
            <div>
              <div class="section-head__title">基础设施概览</div>
              <div class="section-head__meta">Kubernetes 集群连接态、节点与工作负载快照</div>
            </div>
            <el-tag :type="k8s.available ? 'success' : 'info'" round>{{ k8s.available ? '集群在线' : '未连接' }}</el-tag>
          </div>
        </template>

        <div v-if="k8s.available" class="k8s-grid">
          <div class="k8s-item"><strong>{{ k8s.summary.nodes_ready }}</strong><span>Ready 节点</span></div>
          <div class="k8s-item"><strong>{{ k8s.summary.nodes_total }}</strong><span>节点总数</span></div>
          <div class="k8s-item"><strong>{{ k8s.summary.pods_running }}</strong><span>Running Pods</span></div>
          <div class="k8s-item"><strong>{{ k8s.summary.deployments_total }}</strong><span>Deployments</span></div>
        </div>
        <el-alert v-else type="info" :closable="false" :title="k8s.message || '未检测到 kubectl 集群上下文'" />

        <el-table v-if="k8s.available" :data="k8s.nodes || []" size="small" max-height="220" class="k8s-table">
          <el-table-column prop="name" label="节点" min-width="160" />
          <el-table-column prop="status" label="状态" width="120" />
        </el-table>
      </el-card>

      <el-card class="section-card event-card">
        <template #header>
          <div class="section-head">
            <div>
              <div class="section-head__title">安全拦截事件</div>
              <div class="section-head__meta">自动拦截与指标采集结果的最新时间线</div>
            </div>
            <el-tag type="danger" round>自动拦截启用</el-tag>
          </div>
        </template>

        <el-timeline class="event-timeline">
          <el-timeline-item
            v-for="(activity, index) in activities"
            :key="index"
            :timestamp="activity.timestamp"
            :color="activity.color || '#2563eb'"
          >
            {{ activity.content }}
          </el-timeline-item>
        </el-timeline>
      </el-card>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import request from '../utils/request'

const router = useRouter()
const chartRef = ref(null)
let chartInstance = null

const summaryCards = ref([
  { metricKey: 'cpu', title: 'CPU 负载', value: '0.0', unit: '%', trend: 0, description: '关注热点进程和波峰波谷' },
  { metricKey: 'memory', title: '内存使用', value: '0.0', unit: '%', trend: 0, description: '识别高占用与泄漏风险' },
  { metricKey: 'disk', title: '磁盘使用', value: '0.0', unit: '%', trend: 0, description: '检测容量瓶颈与写入压力' },
  { metricKey: 'network', title: '网络吞吐', value: '0.0', unit: 'MB', trend: 0, description: '发现异常带宽抖动与尖峰' },
])

const aiStatus = ref({ type: 'success', text: '系统平稳' })
const prediction = ref({})
const activities = ref([])
const k8s = ref({ available: false, summary: {}, nodes: [] })
const trendSeries = ref([])
let timer = null

const onlineCount = ref(0)
const totalCount = ref(0)

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

const normalizeTrend = (trend = []) => trend.map((item, index) => ({
  label: item.time || item.timestamp || item.created_at || `${index + 1}`,
  cpu: Number(item.cpu ?? item.metrics?.cpu ?? 0),
  memory: Number(item.memory ?? item.metrics?.memory ?? 0),
  disk: Number(item.disk ?? item.metrics?.disk ?? 0),
  network: Number(item.network ?? item.metrics?.network ?? 0),
}))

const renderChart = () => {
  if (!chartRef.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }

  const labels = trendSeries.value.map(item => item.label)
  const palette = ['#2563eb', '#0ea5e9', '#10b981', '#f59e0b']

  chartInstance.setOption({
    color: palette,
    tooltip: { trigger: 'axis' },
    legend: {
      top: 0,
      textStyle: { color: '#64748b' },
    },
    grid: {
      left: 8,
      right: 8,
      top: 48,
      bottom: 10,
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: labels,
      axisLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.3)' } },
      axisLabel: { color: '#64748b' },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.16)' } },
      axisLabel: { color: '#64748b' },
    },
    series: [
      { name: 'CPU', type: 'line', smooth: true, symbol: 'none', areaStyle: { opacity: 0.08 }, data: trendSeries.value.map(item => item.cpu) },
      { name: '内存', type: 'line', smooth: true, symbol: 'none', areaStyle: { opacity: 0.08 }, data: trendSeries.value.map(item => item.memory) },
      { name: '磁盘', type: 'line', smooth: true, symbol: 'none', areaStyle: { opacity: 0.08 }, data: trendSeries.value.map(item => item.disk) },
      { name: '网络', type: 'line', smooth: true, symbol: 'none', areaStyle: { opacity: 0.08 }, data: trendSeries.value.map(item => item.network) },
    ],
  })
}

const applyDashboardData = (data) => {
  const summary = data?.summary || {}
  trendSeries.value = normalizeTrend(data?.trend || [])

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

watch(trendSeries, async () => {
  await nextTick()
  renderChart()
}, { deep: true })

onMounted(() => {
  fetchDashboardData()
  timer = setInterval(fetchDashboardData, 5000)
  window.addEventListener('resize', renderChart)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  window.removeEventListener('resize', renderChart)
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>

<style scoped>
.metric-card {
  cursor: pointer;
  padding: 22px;
  border-radius: 24px;
  transition: transform var(--transition-fast), box-shadow var(--transition-fast);
}

.metric-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
}

.metric-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.metric-card__title {
  color: #64748b;
  font-size: 13px;
}

.metric-card__value {
  margin: 10px 0 18px;
  font-size: 32px;
  font-weight: 700;
  color: #0f172a;
}

.metric-card__value small {
  font-size: 13px;
  color: #64748b;
}

.metric-card__trend {
  padding: 8px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.metric-card__trend.is-up {
  color: #047857;
  background: rgba(16, 185, 129, 0.12);
}

.metric-card__trend.is-down {
  color: #b91c1c;
  background: rgba(239, 68, 68, 0.12);
}

.metric-card__foot {
  margin-top: 14px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: #64748b;
  font-size: 12px;
}

.trend-chart {
  height: 320px;
}

.prediction-layout {
  display: grid;
  gap: 18px;
}

.prediction-score {
  padding: 18px;
  border-radius: 22px;
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(37, 99, 235, 0.08));
  border: 1px solid rgba(245, 158, 11, 0.18);
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.prediction-score__label {
  color: #92400e;
  font-size: 13px;
}

.prediction-score__value {
  font-size: 28px;
  font-weight: 800;
  color: #0f172a;
}

.k8s-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

.k8s-item {
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 20px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: rgba(248, 250, 252, 0.7);
}

.k8s-item strong {
  color: #1d4ed8;
  font-size: 24px;
}

.k8s-item span {
  color: #64748b;
  font-size: 13px;
}

.k8s-table {
  margin-top: 16px;
}

.event-timeline {
  padding-top: 6px;
}

@media (max-width: 768px) {
  .metric-card__head,
  .metric-card__foot {
    flex-direction: column;
  }

  .k8s-grid {
    grid-template-columns: 1fr;
  }
}
</style>
