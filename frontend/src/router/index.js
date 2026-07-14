import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
  },
  {
    path: '/uuid=:uuid',
    name: 'session',
    component: () => import('@/views/LoginView.vue'),
    props: true,
  },
  {
    path: '/app',
    name: 'main',
    component: () => import('@/views/MainView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/multi',
    name: 'multi',
    component: () => import('@/views/MultiAccountView.vue'),
    meta: { requiresAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const auth = useAuthStore()

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    const savedSession = sessionStorage.getItem('session_uuid')
    if (savedSession) {
      auth.sessionUUID = savedSession
      auth.isAuthenticated = true
      next()
    } else {
      next({ name: 'login' })
    }
  } else {
    next()
  }
})

export default router
