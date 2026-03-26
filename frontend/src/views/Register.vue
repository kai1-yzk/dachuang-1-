<template>
  <AuthLayout
    title="创建账号"
    subtitle="填写信息以开始使用"
   
  >
    <el-form :model="regForm" :rules="rules" ref="regFormRef" @keyup.enter="handleRegister">
      <el-form-item prop="username">
        <el-input v-model="regForm.username" placeholder="用户名" prefix-icon="User" />
      </el-form-item>
      <el-form-item prop="email">
        <el-input v-model="regForm.email" placeholder="邮箱地址" prefix-icon="Message" />
      </el-form-item>
      <el-form-item prop="password">
        <el-input v-model="regForm.password" type="password" placeholder="密码 (至少8位,含大小写数字和特殊字符)" prefix-icon="Lock" show-password />
      </el-form-item>
      <el-form-item prop="confirmPassword">
        <el-input v-model="regForm.confirmPassword" type="password" placeholder="确认密码" prefix-icon="Lock" show-password />
      </el-form-item>

      <el-form-item>
        <el-button type="primary" class="submit-btn" :loading="loading" @click="handleRegister">
          注 册
        </el-button>
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="footer-links">
        <span>已有账号？</span>
        <el-link type="primary" @click="$router.push('/login')">立即登录</el-link>
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
const regFormRef = ref(null)
const loading = ref(false)

const regForm = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: ''
})

const validatePass2 = (rule, value, callback) => {
  if (value === '') {
    callback(new Error('请再次输入密码'))
  } else if (value !== regForm.password) {
    callback(new Error('两次输入密码不一致!'))
  } else {
    callback()
  }
}

const validatePassComplex = (rule, value, callback) => {
  const reg = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*(),.?":{}|<>])[A-Za-z\d!@#$%^&*(),.?":{}|<>]{8,}$/
  if (!reg.test(value)) {
    callback(new Error('密码需至少8位，包含大小写字母、数字和特殊字符'))
  } else {
    callback()
  }
}

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱地址', trigger: ['blur', 'change'] }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { validator: validatePassComplex, trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, validator: validatePass2, trigger: 'blur' }
  ]
}

const handleRegister = async () => {
  if (!regFormRef.value) return
  await regFormRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        const res = await request.post('/auth/register', {
          username: regForm.username,
          email: regForm.email,
          password: regForm.password
        })
        if (res.code === 200) {
          ElMessage.success('注册成功，请登录')
          router.push('/login')
        }
      } catch (error) {
        // handled by interceptor
      } finally {
        loading.value = false
      }
    }
  })
}
</script>

<style scoped>
.submit-btn {
  width: 100%;
  margin-top: 10px;
}
.footer-links {
  text-align: center;
  font-size: 14px;
  color: #606266;
}
</style>
