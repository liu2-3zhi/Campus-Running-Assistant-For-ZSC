import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Swal from 'sweetalert2'
import App from './App.vue'
import router from './router'
import './assets/style.css'

window.__RUNNING_UI_BASE__ = import.meta.env.BASE_URL
window.Swal = Swal

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.mount('#app')
