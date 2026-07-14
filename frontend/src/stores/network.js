import { defineStore } from 'pinia'
import { ref } from 'vue'
import { checkServerHealth } from '@/services/api'
import { disableReconnection, enableReconnection } from '@/services/socket'
import Swal from 'sweetalert2'

const DIALOG_AUTO_RETRY_MAX = 5
const DIALOG_AUTO_RETRY_INTERVAL_MS = 8000

export const useNetworkStore = defineStore('network', () => {
  const isInErrorState = ref(false)
  const retryInProgress = ref(false)
  let autoRetryCount = 0
  let autoRetryTimer = null

  function enterErrorState() {
    if (isInErrorState.value) return
    isInErrorState.value = true
    console.info('[网络] 进入网络错误状态')
    disableReconnection()
  }

  function exitErrorState() {
    if (!isInErrorState.value) return
    isInErrorState.value = false
    console.info('[网络] 退出网络错误状态，恢复连接')
    stopAutoRetry()
    autoRetryCount = 0
    setTimeout(() => enableReconnection(), 1000)
  }

  function stopAutoRetry() {
    if (autoRetryTimer) {
      clearInterval(autoRetryTimer)
      autoRetryTimer = null
    }
  }

  function startAutoRetry() {
    stopAutoRetry()
    if (autoRetryCount >= DIALOG_AUTO_RETRY_MAX) return

    autoRetryTimer = setInterval(async () => {
      autoRetryCount++
      console.info(`[网络] 后台自动重试 ${autoRetryCount}/${DIALOG_AUTO_RETRY_MAX}`)
      const alive = await checkServerHealth()
      if (alive) {
        console.info('[网络] 后台自动重试成功')
        Swal.close()
        exitErrorState()
        return
      }
      if (autoRetryCount >= DIALOG_AUTO_RETRY_MAX) {
        stopAutoRetry()
      }
    }, DIALOG_AUTO_RETRY_INTERVAL_MS)
  }

  async function showErrorDialog() {
    stopAutoRetry()
    const remaining = DIALOG_AUTO_RETRY_MAX - autoRetryCount
    const autoHint = remaining > 0
      ? `<p style="font-size:12px;color:#999;margin-top:12px;">将在后台每 ${DIALOG_AUTO_RETRY_INTERVAL_MS / 1000} 秒自动探测，剩余 ${remaining} 次</p>`
      : `<p style="font-size:12px;color:#e67e22;margin-top:12px;">自动重试已用尽，请手动点击重试</p>`

    const troubleshoot = `
      <div style="text-align:left;font-size:13px;margin-top:12px;padding:10px;background:#f9f9f9;border-radius:6px;border:1px solid #eee;">
        <p style="font-weight:600;margin-bottom:6px;">排查建议：</p>
        <ol style="margin:0;padding-left:18px;line-height:1.8;">
          <li>检查本地网络是否正常（尝试访问其他网站）</li>
          <li>若使用校园网，尝试切换至移动数据</li>
          <li>部分省份运营商可能存在 DNS 污染，尝试刷新 DNS 缓存：<br><code style="font-size:11px;background:#eee;padding:1px 4px;border-radius:3px;">ipconfig /flushdns</code></li>
          <li>更换 DNS 为 <code style="font-size:11px;">223.5.5.5</code> 或 <code style="font-size:11px;">8.8.8.8</code></li>
          <li>确认服务器地址与端口是否正确</li>
        </ol>
      </div>`

    const result = await Swal.fire({
      title: '网络错误',
      html: '无法连接到服务器，请检查网络连接或稍后重试。' + troubleshoot + autoHint,
      icon: 'error',
      confirmButtonText: '重试连接',
      allowOutsideClick: false,
      allowEscapeKey: false,
      didOpen: () => { if (remaining > 0) startAutoRetry() },
    })

    if (!result.isConfirmed) return
    stopAutoRetry()
    const alive = await checkServerHealth()
    if (alive) {
      exitErrorState()
    } else {
      showErrorDialog()
    }
  }

  return {
    isInErrorState, retryInProgress,
    enterErrorState, exitErrorState, showErrorDialog,
  }
})
