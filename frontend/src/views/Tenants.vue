<template>
  <div class="app-page">
    <section class="page-hero">
      <div class="page-hero__content">
        <div class="page-eyebrow">Tenant Governance</div>
        <h2 class="page-title">管理多租户空间，并保持权限上下文清晰可见</h2>
        <p class="page-subtitle">租户视角决定了功能边界和操作范围，这里用统一视图管理租户空间与当前上下文。</p>
      </div>
      <div class="page-hero__aside">
        <div class="hero-stat">
          <div class="hero-stat__label">租户数量</div>
          <div class="hero-stat__value">{{ tenants.length }}</div>
        </div>
      </div>
    </section>

    <div class="page-grid page-grid--sidebar">
      <div class="stack-card">
        <el-card class="section-card">
          <template #header>
            <div class="section-head__title">新建租户</div>
          </template>
          <el-form :model="form" label-width="80px">
            <el-form-item label="名称">
              <el-input v-model="form.name" placeholder="例如 team-alpha" />
            </el-form-item>
            <el-button type="primary" :loading="creating" @click="createTenant">创建租户</el-button>
          </el-form>
        </el-card>

        <el-card class="section-card">
          <template #header>
            <div class="section-head__title">当前上下文</div>
          </template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="tenant_id">{{ context.tenant_id ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="role">{{ context.role ?? '-' }}</el-descriptions-item>
          </el-descriptions>
          <el-button class="mt-12" size="small" @click="loadContext">刷新上下文</el-button>
        </el-card>
      </div>

      <el-card class="section-card">
          <template #header>
            <div class="section-head">
              <div>
                <div class="section-head__title">租户列表</div>
                <div class="section-head__meta">展示租户状态与创建时间</div>
              </div>
              <el-button size="small" @click="loadTenants">刷新</el-button>
            </div>
          </template>

          <el-table :data="tenants" size="small" style="width: 100%">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="name" label="租户名" min-width="180" />
            <el-table-column prop="status" label="状态" width="120" />
            <el-table-column prop="created_at" label="创建时间" min-width="180" />
          </el-table>
        </el-card>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

const tenants = ref([])
const creating = ref(false)
const context = ref({})
const form = ref({ name: '' })

const loadTenants = async () => {
  const res = await request.get('/tenants/')
  if (res.code === 200) {
    tenants.value = res.data || []
  }
}

const loadContext = async () => {
  const res = await request.get('/tenants/context')
  if (res.code === 200) {
    context.value = res.data || {}
  }
}

const createTenant = async () => {
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入租户名称')
    return
  }
  creating.value = true
  try {
    const res = await request.post('/tenants/', { name: form.value.name.trim() })
    if (res.code === 200) {
      ElMessage.success('租户创建成功')
      form.value.name = ''
      await loadTenants()
    }
  } finally {
    creating.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadTenants(), loadContext()])
})
</script>

<style scoped>
.mt-12 {
  margin-top: 12px;
}
</style>
