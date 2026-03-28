<template>
  <div class="app-page">
    <section class="page-hero">
      <div class="page-hero__content">
        <div class="page-eyebrow">File Workspace</div>
        <h2 class="page-title">浏览目录、在线编辑并执行文件级操作</h2>
        <p class="page-subtitle">为高频配置修改场景提供一站式工作台，减少在 SSH 与编辑器之间切换的负担。</p>
      </div>
      <div class="page-hero__aside">
        <div class="hero-stat">
          <div class="hero-stat__label">当前目录</div>
          <div class="hero-stat__value">{{ path }}</div>
        </div>
      </div>
    </section>

    <div class="page-grid page-grid--sidebar file-layout">
      <el-card class="section-card">
          <template #header>
            <div class="section-head">
              <div>
                <div class="section-head__title">文件浏览</div>
                <div class="section-head__meta">切换服务器与路径，浏览目录结构</div>
              </div>
              <el-button size="small" @click="loadList">刷新</el-button>
            </div>
          </template>
          <el-form :inline="true" class="toolbox">
            <el-form-item>
              <el-select v-model="serverId" placeholder="服务器" style="width: 220px" @change="loadList">
                <el-option v-for="s in servers" :key="s.id" :label="`${s.hostname} (${s.ip})`" :value="s.id" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-input v-model="path" placeholder="目录路径" style="width: 280px" />
            </el-form-item>
          </el-form>

          <el-table :data="items" size="small" max-height="520" @row-click="openRow">
            <el-table-column prop="name" label="名称" min-width="170" show-overflow-tooltip />
            <el-table-column label="类型" width="80">
              <template #default="scope">{{ scope.row.is_dir ? '目录' : '文件' }}</template>
            </el-table-column>
            <el-table-column prop="size" label="大小" width="90" />
            <el-table-column label="删除" width="90">
              <template #default="scope">
                <el-button size="small" type="danger" :disabled="!canOperate" @click.stop="remove(scope.row)">删</el-button>
              </template>
            </el-table-column>
          </el-table>
      </el-card>

      <div class="stack-card">
        <el-card class="section-card">
          <template #header>
            <div class="section-head">
              <div>
                <div class="section-head__title">在线编辑器</div>
                <div class="section-head__meta">读取并修改目标服务器上的文件内容</div>
              </div>
              <el-space>
                <el-input v-model="activeFile" placeholder="文件路径" style="width: 380px" />
                <el-button :disabled="!canOperate" type="primary" @click="saveFile">保存</el-button>
              </el-space>
            </div>
          </template>
          <el-input v-model="content" type="textarea" :rows="26" resize="none" />
        </el-card>

        <el-card class="section-card">
          <template #header><span class="section-head__title">目录操作</span></template>
          <el-space>
            <el-input v-model="newDir" placeholder="新目录路径" style="width: 340px" />
            <el-button :disabled="!canOperate" @click="createDir">新建目录</el-button>
          </el-space>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

const role = ref('operator')
const servers = ref([])
const serverId = ref(undefined)
const path = ref('/etc')
const items = ref([])
const content = ref('')
const activeFile = ref('')
const newDir = ref('')

const canOperate = computed(() => ['tenant_admin', 'platform_admin', 'superadmin'].includes(role.value))

const joinPath = (base, name) => {
  if (base.endsWith('/')) return `${base}${name}`
  return `${base}/${name}`
}

const loadContext = async () => {
  const res = await request.get('/tenants/context')
  if (res.code === 200) role.value = res.data?.role || 'operator'
}

const loadServers = async () => {
  const res = await request.get('/servers/')
  if (res.code === 200) {
    servers.value = res.data || []
    if (!serverId.value && servers.value.length) serverId.value = servers.value[0].id
  }
}

const loadList = async () => {
  if (!serverId.value) return
  const res = await request.get('/files/list', { params: { server_id: serverId.value, path: path.value } })
  if (res.code === 200) {
    items.value = res.data?.items || []
  }
}

const openRow = async (row) => {
  if (row.is_dir) {
    path.value = joinPath(path.value, row.name)
    await loadList()
    return
  }
  const filePath = joinPath(path.value, row.name)
  const res = await request.get('/files/read', { params: { server_id: serverId.value, path: filePath } })
  if (res.code === 200 && res.data?.ok) {
    activeFile.value = filePath
    content.value = res.data.content || ''
  }
}

const saveFile = async () => {
  if (!activeFile.value) {
    ElMessage.warning('请选择文件')
    return
  }
  try {
    const res = await request.post('/files/write', {
      server_id: serverId.value,
      path: activeFile.value,
      content: content.value,
    })
    if (res.code === 200) ElMessage.success('保存成功')
    else ElMessage.error(res.message || '保存失败')
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '保存失败')
  }
}

const createDir = async () => {
  if (!newDir.value) {
    ElMessage.warning('请输入目录路径')
    return
  }
  try {
    const res = await request.post('/files/mkdir', { server_id: serverId.value, path: newDir.value })
    if (res.code === 200) {
      ElMessage.success('目录创建成功')
      await loadList()
    } else {
      ElMessage.error(res.message || '目录创建失败')
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '目录创建失败')
  }
}

const remove = async (row) => {
  const target = joinPath(path.value, row.name)
  try {
    const res = await request.post('/files/delete', {
      server_id: serverId.value,
      path: target,
      recursive: !!row.is_dir,
      confirm: true,
    })
    if (res.code === 200) {
      ElMessage.success('删除成功')
      await loadList()
    } else {
      ElMessage.error(res.message || '删除失败')
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '删除失败')
  }
}

onMounted(async () => {
  await Promise.all([loadContext(), loadServers()])
  await loadList()
})
</script>

<style scoped>
.toolbox {
  margin-bottom: 10px;
}

.file-layout {
  grid-template-columns: minmax(320px, 0.9fr) minmax(0, 1.2fr);
}
</style>
