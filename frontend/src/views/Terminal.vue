<template>
  <div class="app-page">
    <section class="page-hero">
      <div class="page-hero__content">
        <div class="page-eyebrow">Secure Terminal</div>
        <h2 class="page-title">在受控会话里执行命令，并持续留下审计痕迹</h2>
        <p class="page-subtitle">
          终端执行、安全校验、MFA 二次确认和审计留痕放在同一条链路里，既保留效率，也降低高危误操作风险。
        </p>
      </div>
      <div class="page-hero__aside">
        <div class="hero-stat">
          <div class="hero-stat__label">目标服务器</div>
          <div class="hero-stat__value">{{ serverId || '--' }}</div>
        </div>
        <div class="hero-stat">
          <div class="hero-stat__label">审计记录</div>
          <div class="hero-stat__value">{{ auditLogs.length }}</div>
        </div>
      </div>
    </section>

    <section class="page-grid page-grid--sidebar">
      <el-card class="section-card">
        <template #header>
          <div class="section-head">
            <div>
              <div class="section-head__title">运维终端</div>
              <div class="section-head__meta">SSH 实时执行与命令审计联动</div>
            </div>
          </div>
        </template>

        <div class="stack-card compact">
          <el-select v-model="serverId" class="server-select" placeholder="选择服务器" @change="reconnectTerminal">
            <el-option v-for="srv in servers" :key="srv.id" :label="`${srv.hostname} (${srv.ip}:${srv.port})`" :value="srv.id" />
          </el-select>
          <div class="action-row">
            <el-button plain @click="fetchServers">刷新列表</el-button>
            <el-button type="primary" @click="reconnectTerminal">重连终端</el-button>
          </div>
          <div class="status-list">
            <div class="status-item">
              <span>会话 ID</span>
              <strong>{{ sessionId || '尚未建立' }}</strong>
            </div>
            <div class="status-item">
              <span>命令缓冲</span>
              <strong>{{ pendingCommand || '等待输入' }}</strong>
            </div>
          </div>
        </div>
      </el-card>

      <div class="stack-card">
        <el-card class="console-card">
          <template #header>
            <div class="section-head">
              <div>
                <div class="section-head__title">实时终端输出</div>
                <div class="section-head__meta">当前会话输出、系统提示与拦截结果</div>
              </div>
            </div>
          </template>

          <div class="terminal-window" ref="terminalWindow">
            <div class="output-line" v-for="(line, index) in history" :key="index">
              <span class="prompt" v-if="line.type === 'input'">root@ops:$</span>
              <span :class="['content', line.type]">{{ line.text }}</span>
            </div>
          </div>

          <div class="input-area">
            <span class="prompt">root@ops:$</span>
            <input
              v-model="currentInput"
              @keyup.enter="handleCommand"
              class="cmd-input"
              placeholder="输入命令，例如: systemctl status nginx"
              autofocus
            />
          </div>
        </el-card>

        <el-card class="section-card">
          <template #header>
            <div class="section-head">
              <div>
                <div class="section-head__title">终端审计记录</div>
                <div class="section-head__meta">展示原始输入、解析命令和放行 / 拦截结果</div>
              </div>
            </div>
          </template>
          <el-table :data="auditLogs" size="small" style="width: 100%">
        <el-table-column prop="time" label="执行时间" width="180" />
        <el-table-column prop="raw" label="输入命令" min-width="220" show-overflow-tooltip />
        <el-table-column prop="parsed" label="执行命令" min-width="220" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.status === 'Pass' ? 'success' : 'danger'">{{ scope.row.status === 'Pass' ? '放行' : '拦截' }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
        </el-card>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
import { io } from 'socket.io-client'
import request from '../utils/request'

const history = ref([
  { type: 'system', text: '终端初始化完成，正在连接目标服务器...' },
])
const currentInput = ref('')
const terminalWindow = ref(null)
const socket = ref(null)
const sessionId = ref('')
const serverId = ref(null)
const pendingCommand = ref('')
const servers = ref([])
const auditLogs = ref([])

const fetchServers = async () => {
  const res = await request.get('/servers/')
  if (res.code === 200) {
    servers.value = res.data || []
    if (!serverId.value && servers.value.length) serverId.value = servers.value[0].id
  }
}

const connectTerminal = () => {
  const token = localStorage.getItem('access_token')
  if (!token || !serverId.value) return

  socket.value = io(window.location.origin, {
    transports: ['websocket'],
    timeout: 10000,
  })

  socket.value.on('connect', () => {
    socket.value.emit('terminal_connect', { token, server_id: serverId.value })
  })

  socket.value.on('terminal_ready', payload => {
    sessionId.value = payload.session_id
    history.value.push({ type: 'system', text: `会话已建立: ${payload.session_id}` })
    scrollToBottom()
  })

  socket.value.on('terminal_output', payload => {
    history.value.push({ type: payload.type === 'blocked' ? 'system' : 'output', text: payload.text })
    if (payload.audit) {
      auditLogs.value.unshift({
        time: new Date().toLocaleString(),
        raw: pendingCommand.value,
        parsed: payload.audit.parsed_command,
        status: payload.audit.allowed ? 'Pass' : 'Blocked',
      })
    }
    scrollToBottom()
  })

  socket.value.on('mfa_required', payload => {
    history.value.push({ type: 'system', text: payload.message || '检测到高危命令，需二次确认。' })
    const code = window.prompt(`请输入一次性短码（演示码: ${payload.demo_code}）`)
    if (code) {
      socket.value.emit('mfa_confirm', { session_id: sessionId.value, code })
    }
  })

  socket.value.on('mfa_result', payload => {
    history.value.push({ type: 'system', text: payload.message || '短码验证完成。' })
    scrollToBottom()
  })

  socket.value.on('terminal_error', payload => {
    history.value.push({ type: 'system', text: `错误: ${payload.message}` })
    scrollToBottom()
  })
}

const reconnectTerminal = () => {
  if (socket.value && sessionId.value) {
    socket.value.emit('terminal_disconnect', { session_id: sessionId.value })
    socket.value.disconnect()
  }
  sessionId.value = ''
  history.value.push({ type: 'system', text: `正在连接服务器 ID=${serverId.value}...` })
  connectTerminal()
}

const handleCommand = () => {
  if (!currentInput.value.trim()) return
  if (!socket.value || !sessionId.value) {
    history.value.push({ type: 'system', text: '终端尚未就绪，请先建立会话。' })
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

onMounted(async () => {
  await fetchServers()
  if (serverId.value) connectTerminal()
})

onUnmounted(() => {
  if (socket.value && sessionId.value) {
    socket.value.emit('terminal_disconnect', { session_id: sessionId.value })
    socket.value.disconnect()
  }
})
</script>

<style scoped>
.server-select {
  width: 100%;
}

.status-list {
  display: grid;
  gap: 12px;
}

.status-item {
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.82);
  border: 1px solid rgba(148, 163, 184, 0.16);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.status-item span {
  font-size: 12px;
  color: #64748b;
}

.status-item strong {
  font-size: 14px;
  color: #0f172a;
}

.terminal-window {
  background:
    radial-gradient(circle at top right, rgba(14, 165, 233, 0.12), transparent 24%),
    #09111f;
  color: #d5dfef;
  height: 390px;
  overflow-y: auto;
  padding: 18px;
  font-family: Consolas, 'Courier New', monospace;
  border-radius: 20px;
  border: 1px solid rgba(51, 65, 85, 0.72);
}

.output-line {
  margin-bottom: 5px;
  line-height: 1.45;
  white-space: pre-wrap;
}

.prompt {
  color: #34d399;
  margin-right: 8px;
}

.content.system {
  color: #f59e0b;
}

.content.output {
  color: #cbd5e1;
}

.input-area {
  display: flex;
  align-items: center;
  background: #09111f;
  border-radius: 18px;
  margin-top: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(51, 65, 85, 0.72);
}

.cmd-input {
  flex: 1;
  background: transparent;
  border: none;
  color: #f8fafc;
  font-family: Consolas, 'Courier New', monospace;
  font-size: 14px;
  outline: none;
  min-width: 0;
}
</style>
