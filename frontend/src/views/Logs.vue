<template>
  <div class="app-page">
    <section class="page-hero">
      <div class="page-hero__content">
        <div class="page-eyebrow">Audit & Search</div>
        <h2 class="page-title">搜索审计日志，并快速识别异常模式</h2>
        <p class="page-subtitle">把命令日志、风险级别和异常聚类放进同一视图，帮助你更快定位危险操作与高频问题。</p>
      </div>
      <div class="page-hero__aside">
        <div class="hero-stat">
          <div class="hero-stat__label">日志条目</div>
          <div class="hero-stat__value">{{ table.total }}</div>
        </div>
        <div class="hero-stat">
          <div class="hero-stat__label">异常模式</div>
          <div class="hero-stat__value">{{ clusters.length }}</div>
        </div>
      </div>
    </section>

    <div class="page-grid page-grid--sidebar logs-layout">
      <el-card class="section-card">
          <template #header>
            <div class="section-head">
              <div>
                <div class="section-head__title">日志中心</div>
                <div class="section-head__meta">支持关键词、风险级别和服务器维度筛选</div>
              </div>
            </div>
          </template>
          <el-form :inline="true" class="filter-row query-form">
            <el-form-item label="关键词">
              <el-input v-model="query.keyword" placeholder="命令/详情" clearable />
            </el-form-item>
            <el-form-item label="风险级别">
              <el-select v-model="query.level" placeholder="全部" clearable style="width: 120px">
                <el-option label="LOW" value="LOW" />
                <el-option label="MEDIUM" value="MEDIUM" />
                <el-option label="HIGH" value="HIGH" />
              </el-select>
            </el-form-item>
            <el-form-item label="服务器">
              <el-select v-model="query.serverId" placeholder="全部" clearable style="width: 220px">
                <el-option v-for="s in servers" :key="s.id" :label="`${s.hostname} (${s.ip})`" :value="s.id" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="search">查询</el-button>
            </el-form-item>
          </el-form>

          <el-table :data="table.items" v-loading="loading" size="small">
            <el-table-column prop="created_at" label="时间" width="180" />
            <el-table-column prop="username" label="用户" width="110" />
            <el-table-column prop="server_id" label="服务器" width="90" />
            <el-table-column prop="command_parsed" label="命令" min-width="260" show-overflow-tooltip />
            <el-table-column prop="risk_level" label="风险" width="90">
              <template #default="scope">
                <el-tag :type="riskType(scope.row.risk_level)">{{ scope.row.risk_level }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="result" label="结果" width="100" />
            <el-table-column prop="detail" label="详情" min-width="200" show-overflow-tooltip />
          </el-table>

          <div class="pager">
            <el-pagination
              background
              layout="prev, pager, next, total"
              :total="table.total"
              :page-size="query.pageSize"
              :current-page="query.page"
              @current-change="onPageChange"
            />
          </div>
      </el-card>

      <el-card class="section-card">
          <template #header>
            <div class="section-head">
              <div>
                <div class="section-head__title">异常模式聚类</div>
                <div class="section-head__meta">帮助你从重复风险中提炼操作模式</div>
              </div>
            </div>
          </template>
          <el-table :data="clusters" size="small" max-height="560">
            <el-table-column prop="pattern" label="模式" min-width="90" />
            <el-table-column prop="risk_level" label="风险" width="90" />
            <el-table-column prop="result" label="结果" width="90" />
            <el-table-column prop="count" label="数量" width="70" />
          </el-table>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import request from '../utils/request'

const servers = ref([])
const clusters = ref([])
const loading = ref(false)
const table = reactive({ total: 0, items: [] })

const query = reactive({
  keyword: '',
  level: '',
  serverId: undefined,
  page: 1,
  pageSize: 20,
})

const riskType = (riskLevel) => {
  if (riskLevel === 'HIGH') return 'danger'
  if (riskLevel === 'MEDIUM') return 'warning'
  return 'success'
}

const loadServers = async () => {
  const res = await request.get('/servers/')
  if (res.code === 200) servers.value = res.data || []
}

const loadClusters = async () => {
  const res = await request.get('/logs/anomaly-clusters', { params: { limit: 400 } })
  if (res.code === 200) clusters.value = res.data || []
}

const search = async () => {
  loading.value = true
  try {
    const res = await request.get('/logs/search', {
      params: {
        keyword: query.keyword,
        level: query.level,
        server_id: query.serverId,
        page: query.page,
        page_size: query.pageSize,
      },
    })
    if (res.code === 200) {
      table.total = res.data?.total || 0
      table.items = res.data?.items || []
    }
  } finally {
    loading.value = false
  }
}

const onPageChange = async (p) => {
  query.page = p
  await search()
}

onMounted(async () => {
  await Promise.all([loadServers(), loadClusters()])
  await search()
})
</script>

<style scoped>
.query-form {
  margin-bottom: 8px;
}

.pager {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}

.logs-layout {
  grid-template-columns: minmax(0, 1.6fr) minmax(320px, 0.9fr);
}
</style>
