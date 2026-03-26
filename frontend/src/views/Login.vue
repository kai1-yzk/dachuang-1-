<template>
  <AuthLayout
    title="欢迎回来"
    subtitle="登录你的账号以继续访问"
    visual-title="轻量化 AI 运维防护系统"
    visual-subtitle="以更低成本获得更强的安全与可观测性。"
  >
    <el-form :model="loginForm" :rules="rules" ref="loginFormRef" @keyup.enter="handleLogin">
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
.extra-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.submit-btn {
  width: 100%;
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
