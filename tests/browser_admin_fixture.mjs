import { readFile } from 'node:fs/promises'
import { extname, join } from 'node:path'

const pageRoute = /^\/frontend\/(?:$|(?:multi\/)?uuid=[0-9a-f-]{36}$)/i
const contentTypes = { '.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html' }

export async function readAdminFixtureAsset(path, { root, dist }) {
  let file
  if (path === '/scripts/map-request-proxy.js') file = join(root, 'scripts', 'map-request-proxy.js')
  else if (/^\/frontend\/assets\/[a-z0-9_.-]+$/i.test(path)) file = join(dist, 'assets', path.split('/').at(-1))
  else if (pageRoute.test(path)) file = join(dist, 'index.html')
  else return { status: 404, contentType: 'text/plain', body: 'Not found' }
  try {
    return { status: 200, contentType: contentTypes[extname(file)] || 'application/octet-stream', body: await readFile(file) }
  } catch (error) {
    if (error.code === 'ENOENT') return { status: 404, contentType: 'text/plain', body: 'Not found' }
    throw error
  }
}
