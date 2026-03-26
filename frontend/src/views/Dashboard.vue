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
              <span>服务器资源预测趋势 (LSTM)</span>
              <el-tag :type="aiStatus.type" size="small">{{ aiStatus.text }}</el-tag>
            </div>
          </template>
          <div ref="lineChartRef" class="chart-container"></div>
        </el-card>
      </el-col>

      <!-- 异常检测日志 -->
      <el-col :span="8">
        <el-card shadow="hover" class="log-card">
          <template #header>
            <div class="card-header-title">
              <span>异常检测事件 (Isolation Forest)</span>
              <el-button type="primary" link>查看全部</el-button>
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

const summaryCards = ref([
  { title: 'CPU 负载', value: '45.2', unit: '%', icon: 'Cpu', iconClass: 'icon-blue', trend: 2.1 },
  { title: '内存使用', value: '62.8', unit: '%', icon: 'Odometer', iconClass: 'icon-green', trend: -1.5 },
  { title: '磁盘 IOPS', value: '312', unit: '次/s', icon: 'PieChart', iconClass: 'icon-purple', trend: 5.4 },
  { title: '网络入/出', value: '1.2', unit: 'MB/s', icon: 'Connection', iconClass: 'icon-orange', trend: 0.8 },
])

const aiStatus = ref({ type: 'success', text: '系统平稳' })

const activities = ref([
  { content: '检测到 CPU 瞬时飙升', timestamp: '10分钟前', type: 'warning', size: 'large' },
  { content: 'SSH 登录失败 (IP: 192.168.1.100)', timestamp: '1小时前', type: 'danger', color: '#f56c6c' },
  { content: '自动拦截未知高危进程', timestamp: '2小时前', type: 'success' },
  { content: '内存清理优化执行完毕', timestamp: '5小时前', type: 'info' }
])

const lineChartRef = ref(null)
let chartInstance = null

const initChart = () => {
  if (!lineChartRef.value) return
  chartInstance = echarts.init(lineChartRef.value)
  
  const option = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['实际负载', 'AI 预测负载'] },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: ['10:00', '10:05', '10:10', '10:15', '10:20', '10:25', '10:30']
    },
    yAxis: { type: 'value', max: 100 },
    series: [
      {
        name: '实际负载',
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
        name: 'AI 预测负载',
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
  window.addEventListener('resize', resizeHandler)
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeHandler)
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
