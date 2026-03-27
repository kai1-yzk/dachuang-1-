<template>
  <div class="terminal-container">
    <el-card shadow="hover" class="terminal-card">
      <template #header>
        <div class="card-header">
          <span>AI 智能运维交互终端</span>
          <el-tag type="danger" size="small">三重安全拦截已开启</el-tag>
        </div>
      </template>

      <div class="toolbar-area">
        <el-select v-model="serverId" size="small" class="server-select" placeholder="选择服务器" @change="reconnectTerminal">
          <el-option v-for="srv in servers" :key="srv.id" :label="`${srv.hostname} (${srv.ip}:${srv.port})`" :value="srv.id" />
        </el-select>
        <el-button size="small" @click="fetchServers">刷新</el-button>
        <el-button type="primary" size="small" @click="reconnectTerminal">连接服务器</el-button>
        <el-button type="success" size="small" @click="showAddServerDialog = true">新增SSH服务器</el-button>
      </div>
      
      <div class="terminal-window" ref="terminalWindow">
        <div class="output-line" v-for="(line, index) in history" :key="index">
          <span class="prompt" v-if="line.type === 'input'">[admin@ai-ops] $</span>
          <span :class="['content', line.type]">{{ line.text }}</span>
        </div>
      </div>

      <div class="input-area">
        <span class="prompt">[admin@ai-ops] $</span>
        <input 
          v-model="currentInput" 
          @keyup.enter="handleCommand"
          class="cmd-input"
          placeholder="请输入运维自然语言或系统指令 (例如: 检查系统网络状态)..."
          autofocus
        />
      </div>
    </el-card>

    <el-card shadow="hover" class="mt-20 log-card">
      <template #header>
        <div class="card-header">
          <span>AI 命令安全审计日志 (RBAC)</span>
        </div>
      </template>
      <el-table :data="auditLogs" style="width: 100%" size="small">
        <el-table-column prop="time" label="执行时间" width="180" />
        <el-table-column prop="user" label="操作人" width="100" />
        <el-table-column prop="raw" label="原始意图/命令" />
        <el-table-column prop="parsed" label="AI解析命令" />
        <el-table-column prop="status" label="拦截状态" width="120">
          <template #default="scope">
            <el-tag :type="scope.row.status === 'Pass' ? 'success' : 'danger'">
              {{ scope.row.status === 'Pass' ? '已放行' : '已拦截' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showAddServerDialog" title="接入 SSH 服务器" width="520px">
      <el-form :model="newServer" label-width="110px">
        <el-form-item label="名称">
          <el-input v-model="newServer.hostname" placeholder="例如 prod-web-1" />
        </el-form-item>
        <el-form-item label="IP 地址">
          <el-input v-model="newServer.ip" placeholder="例如 192.168.1.10" />
        </el-form-item>
        <el-form-item label="端口">
          <el-input-number v-model="newServer.port" :min="1" :max="65535" style="width: 100%" />
        </el-form-item>
        <el-form-item label="SSH 用户">
          <el-input v-model="newServer.ssh_username" placeholder="例如 root" />
        </el-form-item>
        <el-form-item label="SSH 密码">
          <el-input v-model="newServer.ssh_password" type="password" show-password placeholder="请输入密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddServerDialog = false">取消</el-button>
        <el-button type="primary" :loading="addingServer" @click="submitAddServer">保存并测试连接</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { io } from 'socket.io-client'
import request from '../utils/request'

const history = ref([
  { type: 'system', text: 'Welcome to AI Ops Terminal (Lightweight Edition).' },
  { type: 'system', text: 'Type your natural language request or command.' },
])

const currentInput = ref('')
const terminalWindow = ref(null)
const socket = ref(null)
const sessionId = ref('')
const serverId = ref(null)
const pendingCommand = ref('')
const servers = ref([])
const showAddServerDialog = ref(false)
const addingServer = ref(false)

const newServer = ref({
  hostname: '',
  ip: '',
  port: 22,
  ssh_username: '',
  ssh_password: '',
})

const auditLogs = ref([])
let refreshTimer = null
const SERVER_CACHE_KEY = 'terminal_server_list_cache'

const loadServerCache = () => {
  try {
    const raw = localStorage.getItem(SERVER_CACHE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

const saveServerCache = (items) => {
  try {
    localStorage.setItem(SERVER_CACHE_KEY, JSON.stringify(items || []))
  } catch {
    // ignore cache write errors
  }
}

const fetchServers = async () => {
  try {
    const res = await request.get('/servers/')
    if (res.code === 200) {
      const nextServers = res.data || []
      if (nextServers.length) {
        servers.value = nextServers
        saveServerCache(nextServers)
      } else if (!servers.value.length) {
        const cached = loadServerCache()
        servers.value = cached
      }

      if (!servers.value.length) {
        serverId.value = null
        history.value.push({ type: 'system', text: '尚未接入服务器，请先新增 SSH 服务器。' })
        return
      }
      if (!serverId.value || !servers.value.find(s => s.id === serverId.value)) {
        serverId.value = servers.value[0].id
      }
    }
  } catch (e) {
    if (!servers.value.length) {
      const cached = loadServerCache()
      if (cached.length) {
        servers.value = cached
      }
    }
    history.value.push({ type: 'system', text: '加载服务器列表失败，已使用本地缓存。' })
  }
}

const getSocketBaseURL = () => {
  const { protocol, host } = window.location
  return `${protocol}//${host}`
}

const connectTerminal = () => {
  const token = localStorage.getItem('access_token')
  if (!token) {
    history.value.push({ type: 'system', text: '未检测到登录 Token，请重新登录。' })
    return
  }
  if (!serverId.value) {
    history.value.push({ type: 'system', text: '请先选择服务器。' })
    return
  }

  socket.value = io(getSocketBaseURL(), {
    transports: ['websocket'],
    timeout: 10000,
  })

  socket.value.on('connect', () => {
    history.value.push({ type: 'system', text: 'WebSocket connected.' })
    socket.value.emit('terminal_connect', {
      token,
      server_id: serverId.value,
    })
  })

  socket.value.on('terminal_ready', payload => {
    sessionId.value = payload.session_id
    history.value.push({ type: 'system', text: `Session ready: ${payload.session_id}` })
    scrollToBottom()
  })

  socket.value.on('terminal_output', payload => {
    history.value.push({ type: payload.type === 'blocked' ? 'system' : 'output', text: payload.text })
    if (payload.audit) {
      auditLogs.value.unshift({
        time: new Date().toLocaleString(),
        user: 'current_user',
        raw: pendingCommand.value,
        parsed: payload.audit.parsed_command,
        status: payload.audit.allowed ? 'Pass' : 'Blocked',
      })
    }
    scrollToBottom()
  })

  socket.value.on('mfa_required', payload => {
    history.value.push({ type: 'system', text: payload.message })
    const code = window.prompt(`请输入一次性短码（演示短码: ${payload.demo_code}）`)
    if (code) {
      socket.value.emit('mfa_confirm', {
        session_id: sessionId.value,
        code,
      })
    }
  })

  socket.value.on('mfa_result', payload => {
    history.value.push({ type: 'system', text: payload.message })
    scrollToBottom()
  })

  socket.value.on('terminal_timeout', payload => {
    history.value.push({ type: 'system', text: payload.message || '会话超时' })
    sessionId.value = ''
  })

  socket.value.on('terminal_error', payload => {
    history.value.push({ type: 'system', text: `Error: ${payload.message}` })
  })
}

const reconnectTerminal = () => {
  if (!serverId.value) {
    history.value.push({ type: 'system', text: '请先选择服务器。' })
    return
  }
  if (socket.value && sessionId.value) {
    socket.value.emit('terminal_disconnect', { session_id: sessionId.value })
  }
  sessionId.value = ''
  if (socket.value) {
    socket.value.disconnect()
    socket.value = null
  }
  history.value.push({ type: 'system', text: `正在连接 server_id=${serverId.value}...` })
  connectTerminal()
}

const submitAddServer = async () => {
  if (!newServer.value.ip || !newServer.value.ssh_username || !newServer.value.ssh_password) {
    ElMessage.error('请填写 ip、SSH 用户、SSH 密码')
    return
  }

  addingServer.value = true
  try {
    const res = await request.post('/servers/', {
      hostname: newServer.value.hostname,
      ip: newServer.value.ip,
      port: newServer.value.port,
      auth_type: 'password',
      ssh_username: newServer.value.ssh_username,
      ssh_password: newServer.value.ssh_password,
      connect_timeout: 15,
    })

    if (res.code !== 200) {
      ElMessage.error(res.message || '保存服务器失败')
      return
    }

    const createdServerId = res.data.server_id
    const testRes = await request.post(`/servers/${createdServerId}/ssh-test`)
    if (testRes.code === 200) {
      ElMessage.success('服务器接入成功，SSH 连接测试通过')
    } else {
      ElMessage.warning(testRes.message || '服务器已保存，但连接测试未通过')
    }

    showAddServerDialog.value = false
    newServer.value = { hostname: '', ip: '', port: 22, ssh_username: '', ssh_password: '' }
    await fetchServers()
    serverId.value = createdServerId
    reconnectTerminal()
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '接入服务器失败')
  } finally {
    addingServer.value = false
  }
}

const handleCommand = async () => {
  if (!currentInput.value.trim()) return
  if (!socket.value || !sessionId.value) {
    history.value.push({ type: 'system', text: '终端尚未就绪，请稍后重试。' })
    return
  }
  
  const cmd = currentInput.value.trim()
  pendingCommand.value = cmd
  history.value.push({ type: 'input', text: cmd })

  socket.value.emit('terminal_command', {
    session_id: sessionId.value,
    input: cmd,
    server_id: serverId.value,
  })
  
  currentInput.value = ''
  scrollToBottom()
}

const scrollToBottom = () => {
  nextTick(() => {
    if (terminalWindow.value) {
      terminalWindow.value.scrollTop = terminalWindow.value.scrollHeight
    }
  })
}

onMounted(() => {
  const cached = loadServerCache()
  if (cached.length) {
    servers.value = cached
    if (!serverId.value) {
      serverId.value = cached[0].id
    }
  }

  fetchServers().then(() => {
    connectTerminal()
  })

  refreshTimer = setInterval(() => {
    fetchServers()
  }, 15000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
  if (socket.value && sessionId.value) {
    socket.value.emit('terminal_disconnect', { session_id: sessionId.value })
    socket.value.disconnect()
  }
})
</script>

<style scoped>
.terminal-container {
  height: 100%;
}

.terminal-card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: bold;
}

.toolbar-area {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.terminal-window {
  background-color: #1e1e1e;
  color: #d4d4d4;
  height: 300px;
  overflow-y: auto;
  padding: 15px;
  font-family: 'Consolas', 'Courier New', monospace;
  border-radius: 4px;
}

.output-line {
  margin-bottom: 5px;
  line-height: 1.5;
  white-space: pre-wrap;
}

.prompt {
  color: #67c23a;
  margin-right: 10px;
}

.content.system {
  color: #e6a23c;
}

.content.output {
  color: #a9b7c6;
}

.input-area {
  display: flex;
  align-items: center;
  background-color: #1e1e1e;
  padding: 10px 15px;
  margin-top: 2px;
  border-radius: 4px;
}

.cmd-input {
  flex: 1;
  background: transparent;
  border: none;
  color: #fff;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 14px;
  outline: none;
}

.server-select {
  width: 300px;
}

.mt-20 {
  margin-top: 20px;
}

.log-card {
  border-radius: 8px;
}
</style>
