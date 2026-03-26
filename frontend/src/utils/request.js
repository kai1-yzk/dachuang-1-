import axios from 'axios'
import router from '../router'
import { ElMessage } from 'element-plus'

const service = axios.create({
  baseURL: '/api',
  timeout: 10000
})

let isRefreshing = false
let requests = []

service.interceptors.request.use(
  config => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

service.interceptors.response.use(
  response => response.data,
  async error => {
    const { config, response } = error
    if (response && response.status === 401) {
      if (!isRefreshing) {
        isRefreshing = true
        try {
          const refreshToken = localStorage.getItem('refresh_token')
          if (!refreshToken) {
            throw new Error('No refresh token')
          }
          const res = await axios.post('/api/auth/refresh', { refresh_token: refreshToken })
          if (res.data.code === 200) {
            const newToken = res.data.data.access_token
            localStorage.setItem('access_token', newToken)
            config.headers['Authorization'] = `Bearer ${newToken}`
            
            // 重试队列中的请求
            requests.forEach(cb => cb(newToken))
            requests = []
            return service(config)
          }
        } catch (err) {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          router.push('/login')
          ElMessage.error('登录状态已过期，请重新登录')
          return Promise.reject(err)
        } finally {
          isRefreshing = false
        }
      } else {
        // 正在刷新时，将请求加入队列
        return new Promise((resolve) => {
          requests.push((token) => {
            config.headers['Authorization'] = `Bearer ${token}`
            resolve(service(config))
          })
        })
      }
    } else if (response && response.status === 429) {
      ElMessage.error('请求过于频繁，请稍后再试')
    } else {
      ElMessage.error(response?.data?.message || '请求失败')
    }
    return Promise.reject(error)
  }
)

export default service
