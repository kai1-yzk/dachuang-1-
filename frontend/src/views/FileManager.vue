<template>
  <div class="file-page">
    <el-row :gutter="16">
      <el-col :span="9">
        <el-card shadow="hover">
          <template #header>
            <div class="header-line">
              <span class="title">文件浏览</span>
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
      </el-col>

      <el-col :span="15">
        <el-card shadow="hover">
          <template #header>
            <div class="header-line">
              <span class="title">在线编辑器</span>
              <el-space>
                <el-input v-model="activeFile" placeholder="文件路径" style="width: 380px" />
                <el-button :disabled="!canOperate" type="primary" @click="saveFile">保存</el-button>
              </el-space>
            </div>
          </template>
          <el-input v-model="content" type="textarea" :rows="26" resize="none" />
        </el-card>

        <el-card shadow="hover" class="mt16">
          <template #header><span class="title">目录操作</span></template>
          <el-space>
            <el-input v-model="newDir" placeholder="新目录路径" style="width: 340px" />
            <el-button :disabled="!canOperate" @click="createDir">新建目录</el-button>
          </el-space>
        </el-card>
      </el-col>
    </el-row>
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
  const res = await request.post('/files/write', {
    server_id: serverId.value,
    path: activeFile.value,
    content: content.value,
  })
  if (res.code === 200) ElMessage.success('保存成功')
}

const createDir = async () => {
  const res = await request.post('/files/mkdir', { server_id: serverId.value, path: newDir.value })
  if (res.code === 200) {
    ElMessage.success('目录创建成功')
    await loadList()
  }
}

const remove = async (row) => {
  const target = joinPath(path.value, row.name)
  const res = await request.post('/files/delete', {
    server_id: serverId.value,
    path: target,
    recursive: !!row.is_dir,
    confirm: true,
  })
  if (res.code === 200) {
    ElMessage.success('删除成功')
    await loadList()
  }
}

onMounted(async () => {
  await Promise.all([loadContext(), loadServers()])
  await loadList()
})
</script>

<style scoped>
.title {
  font-weight: 600;
}

.header-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.toolbox {
  margin-bottom: 10px;
}

.mt16 {
  margin-top: 16px;
}
</style>
