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
    path: '/uuid=:uuid/app',
    name: 'main',
    component: () => import('@/views/MainView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/uuid=:uuid/multi',
    name: 'multi',
    component: () => import('@/views/MultiAccountView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/app',
    name: 'main-legacy',
    component: () => import('@/views/MainView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/multi',
    name: 'multi-legacy',
    component: () => import('@/views/MultiAccountView.vue'),
    meta: { requiresAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

router.beforeEach((to, from, next) => {
  const auth = useAuthStore()
  const savedSession = sessionStorage.getItem('session_uuid')

  if (to.params?.uuid) {
    auth.sessionUUID = String(to.params.uuid)
  }

  if (to.name === 'main-legacy' || to.name === 'multi-legacy') {
    const sessionId = auth.sessionUUID || savedSession
    if (sessionId) {
      next({
        name: to.name === 'main-legacy' ? 'main' : 'multi',
        params: { uuid: sessionId },
      })
    } else {
      next({ name: 'login' })
    }
    return
  }

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
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
