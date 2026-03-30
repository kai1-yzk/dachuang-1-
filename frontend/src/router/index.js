import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: {
      requiresAuth: false,
      layout: 'blank',
      title: '欢迎登录',
      subtitle: '进入 AIOps 智能运维控制台'
    }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/Register.vue'),
    meta: {
      requiresAuth: false,
      layout: 'blank',
      title: '创建账号',
      subtitle: '快速加入多租户智能运维平台'
    }
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: {
      requiresAuth: true,
      title: '全局监控总览',
      subtitle: '统一观察实时指标、故障预测、安全事件与基础设施健康'
    }
  },
  {
    path: '/metrics/trend',
    name: 'MetricTrend',
    component: () => import('../views/MetricTrend.vue'),
    meta: {
      requiresAuth: true,
      title: '指标趋势分析',
      subtitle: '按时间维度回看关键资源变化与风险走势'
    }
  },
  {
    path: '/terminal',
    name: 'Terminal',
    component: () => import('../views/Terminal.vue'),
    meta: {
      requiresAuth: true,
      title: '实时运维终端',
      subtitle: '在受控会话中执行命令，并保留全链路审计痕迹'
    }
  },
  {
    path: '/tenants',
    name: 'Tenants',
    component: () => import('../views/Tenants.vue'),
    meta: {
      requiresAuth: true,
      title: '租户治理',
      subtitle: '维护租户空间与访问上下文，保持平台隔离'
    }
  },
  {
    path: '/servers',
    name: 'Servers',
    component: () => import('../views/Servers.vue'),
    meta: {
      requiresAuth: true,
      title: '服务器管理',
      subtitle: '管理纳管服务器节点及SSH凭证'
    }
  },
  {
    path: '/assistant',
    name: 'Assistant',
    component: () => import('../views/Assistant.vue'),
    meta: {
      requiresAuth: true,
      title: '智能运维助手',
      subtitle: '先生成操作方案，再做风险确认与执行落地'
    }
  },
  {
    path: '/services',
    name: 'Services',
    component: () => import('../views/Services.vue'),
    meta: {
      requiresAuth: true,
      title: '服务治理',
      subtitle: '统一管理服务状态、自启动配置与实例健康'
    }
  },
  {
    path: '/logs',
    name: 'Logs',
    component: () => import('../views/Logs.vue'),
    meta: {
      requiresAuth: true,
      title: '日志中心',
      subtitle: '聚合审计日志与异常模式，快速定位风险操作'
    }
  },
  {
    path: '/backup',
    name: 'Backup',
    component: () => import('../views/Backup.vue'),
    meta: {
      requiresAuth: true,
      title: '备份与恢复',
      subtitle: '管理备份任务生命周期，并对恢复操作做风险控制'
    }
  },
  {
    path: '/files',
    name: 'FileManager',
    component: () => import('../views/FileManager.vue'),
    meta: {
      requiresAuth: true,
      title: '文件工作台',
      subtitle: '浏览目录、在线编辑与执行目录级别操作'
    }
  },
  {
    path: '/batch',
    name: 'BatchExec',
    component: () => import('../views/BatchExec.vue'),
    meta: {
      requiresAuth: true,
      title: '批量命令审批',
      subtitle: '集中创建、审批与审查批量执行任务'
    }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('access_token')
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if ((to.path === '/login' || to.path === '/register') && token) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
