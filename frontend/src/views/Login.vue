<template>
  <AuthLayout
    title="欢迎回来"
    subtitle="进入统一的 AIOps 控制台，继续你的监控、安全与自动化工作流。"
    visual-title="让观测、风险拦截与执行协同发生"
    visual-subtitle="从实时指标到安全审计，再到终端与批量执行，所有关键操作在一个界面里完成闭环。"
  >
    <div class="auth-intro">
      <div class="auth-pill">安全登录</div>
      <div class="auth-hint">建议使用具备租户权限的账号进入控制台，以获得完整操作能力。</div>
    </div>

    <el-form :model="loginForm" :rules="rules" ref="loginFormRef" class="auth-form" @keyup.enter="handleLogin">
      <el-form-item prop="username">
        <el-input v-model="loginForm.username" placeholder="用户名" prefix-icon="User" />
      </el-form-item>
      <el-form-item prop="password">
        <el-input v-model="loginForm.password" type="password" placeholder="密码" prefix-icon="Lock" show-password />
      </el-form-item>

      <div class="extra-actions">
        <el-checkbox v-model="loginForm.remember">记住我</el-checkbox>
        <el-link type="primary" :underline="false">忘记密码？</el-link>
      </div>

      <el-form-item>
        <el-button type="primary" class="submit-btn" :loading="loading" @click="handleLogin">
          登 录
        </el-button>
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="footer-links">
        <span>还没有账号？</span>
        <el-link type="primary" @click="$router.push('/register')">立即注册</el-link>
      </div>

      <el-divider class="divider">其他登录方式</el-divider>
      <div class="third-party">
        <el-button circle><el-icon><Platform /></el-icon></el-button>
        <el-button circle><el-icon><Position /></el-icon></el-button>
      </div>
    </template>
  </AuthLayout>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '../utils/request'
import AuthLayout from '../components/auth/AuthLayout.vue'

const router = useRouter()
const loginFormRef = ref(null)
const loading = ref(false)

const loginForm = reactive({
  username: '',
  password: '',
  remember: false
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const handleLogin = async () => {
  if (!loginFormRef.value) return
  await loginFormRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        const res = await request.post('/auth/login', {
          username: loginForm.username,
          password: loginForm.password
        })
        if (res.code === 200) {
          ElMessage.success('登录成功')
          localStorage.setItem('access_token', res.data.access_token)
          localStorage.setItem('refresh_token', res.data.refresh_token)
          router.push('/dashboard')
        }
      } catch (error) {
        // error handled by interceptor
      } finally {
        loading.value = false
      }
    }
  })
}
</script>

<style scoped>
.auth-intro {
  margin-bottom: 18px;
}

.auth-pill {
  display: inline-flex;
  padding: 7px 11px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.1);
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
}

.auth-hint {
  margin-top: 10px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
}

.auth-form :deep(.el-form-item) {
  margin-bottom: 18px;
}

.extra-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.submit-btn {
  width: 100%;
  min-height: 46px;
}
.footer-links {
  text-align: center;
  font-size: 14px;
  color: #606266;
}
.divider {
  margin: 16px 0;
}
.third-party {
  display: flex;
  justify-content: center;
  gap: 15px;
}
</style>
