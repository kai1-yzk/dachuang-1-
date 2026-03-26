<template>
  <div class="terminal-container">
    <el-card shadow="hover" class="terminal-card">
      <template #header>
        <div class="card-header">
          <span>AI 智能运维交互终端</span>
          <el-tag type="danger" size="small">三重安全拦截已开启</el-tag>
        </div>
      </template>
      
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
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
import { io } from 'socket.io-client'

const history = ref([
  { type: 'system', text: 'Welcome to AI Ops Terminal (Lightweight Edition).' },
  { type: 'system', text: 'Type your natural language request or command.' },
])

const currentInput = ref('')
const terminalWindow = ref(null)
const socket = ref(null)
const sessionId = ref('')
const serverId = ref(1)
const pendingCommand = ref('')

const auditLogs = ref([])

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
  connectTerminal()
})

onUnmounted(() => {
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

.mt-20 {
  margin-top: 20px;
}

.log-card {
  border-radius: 8px;
}
</style>
