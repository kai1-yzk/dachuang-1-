<template>
  <div class="metric-trend-page">
    <el-card shadow="hover">
      <template #header>
        <div class="header-row">
          <span>{{ metricLabel }} 时间折线图</span>
          <el-button size="small" @click="fetchTrend">刷新</el-button>
        </div>
      </template>

      <el-row :gutter="12" class="mb-12">
        <el-col :span="6">
          <el-select v-model="period" style="width: 100%" @change="onPeriodChange">
            <el-option label="近1小时" value="1h" />
            <el-option label="近6小时" value="6h" />
            <el-option label="近24小时" value="24h" />
            <el-option label="自定义时间范围" value="custom" />
          </el-select>
        </el-col>
        <el-col :span="10" v-if="period === 'custom'">
          <el-date-picker
            v-model="range"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            style="width: 100%"
          />
        </el-col>
        <el-col :span="6">
          <el-select v-model="serverId" clearable placeholder="全部服务器" style="width: 100%" @change="fetchTrend">
            <el-option v-for="srv in servers" :key="srv.id" :label="`${srv.hostname} (${srv.ip})`" :value="srv.id" />
          </el-select>
        </el-col>
        <el-col :span="2">
          <el-button type="primary" style="width: 100%" @click="fetchTrend">查询</el-button>
        </el-col>
      </el-row>

      <div ref="chartRef" class="chart"></div>
      <div class="hint">数据来源：服务器实时采集原始数据（server_metrics）</div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import echarts from '../utils/echarts'
import request from '../utils/request'

const route = useRoute()
const metric = ref(route.query.metric || 'cpu')
const period = ref('1h')
const range = ref([])
const serverId = ref(null)
const servers = ref([])
const chartRef = ref(null)
let chart = null

const metricLabel = computed(() => {
  const map = {
    cpu: 'CPU负载',
    memory: '内存使用',
    disk: '磁盘使用',
    network: '网络吞吐'
  }
  return map[metric.value] || 'CPU负载'
})

const loadServers = async () => {
  const res = await request.get('/servers/')
  if (res.code === 200) {
    servers.value = res.data || []
  }
}

const drawChart = (points) => {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: points.map(x => x.time) },
    yAxis: { type: 'value' },
    series: [
      {
        name: metricLabel.value,
        type: 'line',
        smooth: true,
        data: points.map(x => Number(x.value || 0)),
      }
    ]
  })
}

const fetchTrend = async () => {
  const params = {
    metric: metric.value,
    period: period.value,
  }
  if (serverId.value) params.server_id = serverId.value
  if (period.value === 'custom' && range.value?.length === 2) {
    params.start_time = new Date(range.value[0]).toISOString().slice(0, 19).replace('T', ' ')
    params.end_time = new Date(range.value[1]).toISOString().slice(0, 19).replace('T', ' ')
  }
  const res = await request.get('/metrics/trend', { params })
  if (res.code === 200) {
    drawChart(res.data?.points || [])
  }
}

const onPeriodChange = () => {
  if (period.value !== 'custom') {
    range.value = []
    fetchTrend()
  }
}

const onResize = () => {
  if (chart) chart.resize()
}

onMounted(async () => {
  await loadServers()
  await fetchTrend()
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  if (chart) chart.dispose()
})
</script>

<style scoped>
.mb-12 {
  margin-bottom: 12px;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart {
  width: 100%;
  height: 430px;
}

.hint {
  margin-top: 10px;
  color: #909399;
  font-size: 12px;
}
</style>
