import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vitejs.dev/config/
const backendTarget = process.env.VITE_BACKEND_TARGET || 'http://localhost:5001'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true
      },
      '/socket.io': {
        target: backendTarget,
        ws: true,
        changeOrigin: true
      }
    }
  },
  build: {
    // ECharts 按需引入后仍约 520KB（已从全量 1209KB 降下来），
    // 且仅在 Dashboard / MetricTrend 页面异步加载，不在首屏关键路径上，
    // 因此把告警阈值放宽到 600KB。其余 chunk 最大约 380KB。
    chunkSizeWarningLimit: 600,
    // 拆出第三方大依赖为独立 chunk：既能消除单 chunk >500KB 的告警，
    // 也让这些变更不频繁的库能被浏览器长期缓存，升级业务代码时无需重新下载。
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('echarts') || id.includes('zrender')) return 'vendor-echarts'
          if (id.includes('element-plus') || id.includes('@element-plus')) return 'vendor-element'
          if (id.includes('vue-router') || id.includes('pinia') || id.includes('/vue/')) return 'vendor-vue'
          return 'vendor'
        }
      }
    }
  }
})
