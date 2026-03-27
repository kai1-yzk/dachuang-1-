<template>
  <div class="dashboard">
    <el-row :gutter="20">
      <!-- 核心指标卡片 -->
      <el-col :span="6" v-for="item in summaryCards" :key="item.title">
        <el-card shadow="hover" class="data-card" :body-style="{ padding: '20px' }">
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
      <!-- AI 分析状态 -->
      <el-col :span="16">
        <el-card shadow="hover" class="chart-card">
          <template #header>
            <div class="card-header-title">
              <span>AI 时序预测与实时负载趋势</span>
              <el-tag :type="aiStatus.type" size="small">{{ aiStatus.text }}</el-tag>
            </div>
          </template>
          <div ref="lineChartRef" class="chart-container"></div>
        </el-card>
      </el-col>

      <!-- 安全拦截事件 -->
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
import * as echarts from 'echarts'
import request from '../utils/request'

const summaryCards = ref([
  { title: 'CPU 负载', value: '0.0', unit: '%', icon: 'Cpu', iconClass: 'icon-blue', trend: 0 },
  { title: '内存使用', value: '0.0', unit: '%', icon: 'Odometer', iconClass: 'icon-green', trend: 0 },
  { title: '磁盘使用', value: '0.0', unit: '%', icon: 'PieChart', iconClass: 'icon-purple', trend: 0 },
  { title: '网络吞吐', value: '0.0', unit: 'MB', icon: 'Connection', iconClass: 'icon-orange', trend: 0 },
  { title: '恶意 IP 拦截', value: '0', unit: '个', icon: 'Lock', iconClass: 'icon-red', trend: 0 },
  { title: '异常请求拦截', value: '0', unit: '次', icon: 'Warning', iconClass: 'icon-red', trend: 0 },
])

const aiStatus = ref({ type: 'success', text: '系统平稳' })

const activities = ref([])

const lineChartRef = ref(null)
let chartInstance = null
let timer = null

const forecastByTrend = (series) => {
  if (!series.length) return []
  if (series.length === 1) return [series[0]]
  const alpha = 0.45
  const result = [series[0]]
  for (let i = 1; i < series.length; i += 1) {
    const prev = Number(result[i - 1] || 0)
    const curr = Number(series[i] || 0)
    result.push(Number((alpha * curr + (1 - alpha) * prev).toFixed(2)))
  }
  return result
}

const safeTrend = (next, prev) => {
  if (!prev || prev === 0) return 0
  return Number((((next - prev) / prev) * 100).toFixed(1))
}

const applyDashboardData = (data) => {
  const summary = data?.summary || {}
  const trend = data?.trend || []

  const prevCpu = Number(summaryCards.value[0].value || 0)
  const prevMem = Number(summaryCards.value[1].value || 0)
  const prevDisk = Number(summaryCards.value[2].value || 0)
  const prevNet = Number(summaryCards.value[3].value || 0)
  const prevBlockedIp = Number(summaryCards.value[4].value || 0)
  const prevAbnormalBlocked = Number(summaryCards.value[5].value || 0)

  const cpu = Number(summary.cpu || 0)
  const memory = Number(summary.memory || 0)
  const disk = Number(summary.disk || 0)
  const network = Number(summary.network || 0)

  const security = data?.security || {}
  const blockedIpCount = Number(security.blocked_ip_count || 0)
  const blockedRequestCount = Number(security.blocked_request_count || 0)
  const abnormalRequestCount = Number(security.abnormal_request_count || 0)

  summaryCards.value = [
    { ...summaryCards.value[0], value: cpu.toFixed(1), trend: safeTrend(cpu, prevCpu) },
    { ...summaryCards.value[1], value: memory.toFixed(1), trend: safeTrend(memory, prevMem) },
    { ...summaryCards.value[2], value: disk.toFixed(1), trend: safeTrend(disk, prevDisk) },
    { ...summaryCards.value[3], value: network.toFixed(1), trend: safeTrend(network, prevNet) },
    { ...summaryCards.value[4], value: String(blockedIpCount), trend: safeTrend(blockedIpCount, prevBlockedIp) },
    {
      ...summaryCards.value[5],
      value: String(blockedRequestCount),
      trend: safeTrend(blockedRequestCount, prevAbnormalBlocked),
      unit: `次 / 高风险 ${abnormalRequestCount}`,
    },
  ]

  const totalServers = data?.servers?.total || 0
  const onlineServers = data?.servers?.online || 0
  aiStatus.value = onlineServers === totalServers && totalServers > 0
    ? { type: 'success', text: `在线 ${onlineServers}/${totalServers}` }
    : { type: 'warning', text: `在线 ${onlineServers}/${totalServers} · 风险自动拦截中` }

  if (chartInstance) {
    const cpuSeries = trend.map(x => Number(x.cpu || 0))
    const aiForecastSeries = forecastByTrend(cpuSeries)
    chartInstance.setOption({
      xAxis: { data: trend.map(x => x.time) },
      series: [
        { name: '实时 CPU 负载', data: cpuSeries },
        { name: 'AI 预测负载(短时)', data: aiForecastSeries },
      ],
    })
  }

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
          collect_now: 1,
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
    }
  } catch (e) {
    aiStatus.value = { type: 'danger', text: '采集失败' }
  }
}

const initChart = () => {
  if (!lineChartRef.value) return
  chartInstance = echarts.init(lineChartRef.value)
  
  const option = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['实时 CPU 负载', 'AI 预测负载(短时)'] },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: ['10:00', '10:05', '10:10', '10:15', '10:20', '10:25', '10:30']
    },
    yAxis: { type: 'value', max: 100 },
    series: [
      {
        name: '实时 CPU 负载',
        type: 'line',
        smooth: true,
        itemStyle: { color: '#409eff' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(64,158,255,0.3)' },
            { offset: 1, color: 'rgba(64,158,255,0.1)' }
          ])
        },
        data: [35, 40, 42, 38, 45, 47, 45]
      },
      {
        name: 'AI 预测负载(短时)',
        type: 'line',
        smooth: true,
        lineStyle: { type: 'dashed' },
        itemStyle: { color: '#e6a23c' },
        data: [36, 41, 40, 39, 46, 49, 48]
      }
    ]
  }
  chartInstance.setOption(option)
}

const resizeHandler = () => {
  if (chartInstance) chartInstance.resize()
}

onMounted(() => {
  initChart()
  fetchDashboardData()
  timer = setInterval(fetchDashboardData, 15000)
  window.addEventListener('resize', resizeHandler)
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeHandler)
  if (timer) clearInterval(timer)
  if (chartInstance) chartInstance.dispose()
})
</script>

<style scoped>
.mt-20 {
  margin-top: 20px;
}

.data-card {
  border-radius: 8px;
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
.icon-red { color: #f56c6c; font-size: 20px; }

.chart-card, .log-card {
  border-radius: 8px;
  height: 400px;
}

.card-header-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: bold;
}

.chart-container {
  height: 320px;
  width: 100%;
}
</style>
