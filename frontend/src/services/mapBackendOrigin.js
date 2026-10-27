export function normalizeBackendPageOrigin(value) {
  const raw = String(value ?? '')
  if (/[\x00-\x1f\x7f-\x9f\\]/.test(raw)) throw new Error('后端规划页面来源不能包含控制字符或反斜杠')
  const input = raw.trim()
  if (!input) return ''
  try {
    const authority = input.match(/^https?:\/\/([^/?#]+)/i)?.[1]
    const url = new URL(input)
    if (!authority || authority.endsWith(':') || authority.includes('@') || url.username || url.password ||
        !['http:', 'https:'].includes(url.protocol) || !url.hostname || url.port === '0') throw new Error()
    return url.origin
  } catch {
    throw new Error('后端规划页面来源无效，请输入不含账号密码的 HTTP/HTTPS 地址')
  }
}
