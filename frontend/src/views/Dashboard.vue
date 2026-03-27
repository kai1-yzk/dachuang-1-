<template>
  <div class="dashboard">
    <el-row :gutter="20">
      <el-col :span="6" v-for="item in summaryCards" :key="item.metricKey">
        <el-card shadow="hover" class="data-card clickable" :body-style="{ padding: '20px' }" @click="goMetric(item.metricKey)">
          <div class="card-header">
            <span>{{ item.title }}</span>
            <el-icon :class="item.iconClass"><component :is="item.icon" /></el-icon>
          </div>
          <div class="card-value">{{ item.value }}<span class="unit">{{ item.unit }}</span></div>
          <div class="card-footer">
            <span class="trend" :class="item.trend > 0 ? 'up' : 'down'">
              {{ item.trend > 0 ? '+' : '' }}{{ item.trend }}% 较昨日
            </span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="mt-20">
      <el-col :span="16">
        <el-card shadow="hover" class="chart-card">
          <template #header>
            <div class="card-header-title">
              <span>AI 故障预测与报警详情</span>
              <el-tag :type="aiStatus.type" size="small">{{ aiStatus.text }}</el-tag>
            </div>
          </template>
          <el-descriptions v-if="prediction.alert" :column="2" border size="small" class="predict-box">
            <el-descriptions-item label="故障类型">{{ prediction.alert.fault_type }}</el-descriptions-item>
            <el-descriptions-item label="风险等级">
              <el-tag :type="riskType(prediction.alert.risk_level)">{{ prediction.alert.risk_level }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="预测提前量">{{ prediction.alert.lead_time_minutes }} 分钟</el-descriptions-item>
            <el-descriptions-item label="异常分数">{{ Number(prediction.anomaly_score || 0).toFixed(3) }}</el-descriptions-item>
            <el-descriptions-item label="故障起因" :span="2">{{ prediction.alert.cause }}</el-descriptions-item>
            <el-descriptions-item label="紧急解决方法" :span="2">{{ prediction.alert.emergency_solution }}</el-descriptions-item>
            <el-descriptions-item label="预防建议" :span="2">{{ prediction.alert.prevention_advice }}</el-descriptions-item>
          </el-descriptions>
          <el-empty v-else description="暂无预测结果" />
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card shadow="hover" class="log-card">
          <template #header>
            <div class="card-header-title">
              <span>AI 安全拦截事件</span>
              <el-tag size="small" type="danger">自动拦截开启</el-tag>
            </div>
          </template>
          <el-timeline>
            <el-timeline-item
              v-for="(activity, index) in activities"
              :key="index"
              :type="activity.type"
              :color="activity.color"
              :size="activity.size"
              :timestamp="activity.timestamp"
            >
              {{ activity.content }}
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
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
let timer = null

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
    const [metricsRes, securityRes] = await Promise.all([
      request.get('/metrics/dashboard', {
        params: {
          collect_now: 0,
          points: 12,
        }
      }),
      request.get('/audit/security-overview', {
        params: { limit: 300 }
      })
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
.mt-20 {
  margin-top: 20px;
}

.data-card {
  border-radius: 8px;
}

.clickable {
  cursor: pointer;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #909399;
  font-size: 14px;
}

.card-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
  margin: 10px 0;
}

.unit {
  font-size: 14px;
  font-weight: normal;
  margin-left: 4px;
  color: #909399;
}

.card-footer {
  font-size: 13px;
}

.trend.up { color: #f56c6c; }
.trend.down { color: #67c23a; }

.icon-blue { color: #409eff; font-size: 20px; }
.icon-green { color: #67c23a; font-size: 20px; }
.icon-purple { color: #b37feb; font-size: 20px; }
.icon-orange { color: #e6a23c; font-size: 20px; }

.chart-card, .log-card {
  border-radius: 8px;
  height: 400px;
}

.predict-box {
  margin-top: 6px;
}

.card-header-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: bold;
}

</style>
