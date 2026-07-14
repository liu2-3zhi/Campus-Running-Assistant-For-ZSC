import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    proxy: {
      '/api': 'http://localhost:5000',
      '/auth': 'http://localhost:5000',
      '/health': 'http://localhost:5000',
      '/socket.io': {
        target: 'http://localhost:5000',
        ws: true,
      },
      '/editor.md': 'http://localhost:5000',
      '/cache': 'http://localhost:5000',
      '/theme': 'http://localhost:5000',
      '/favicon.ico': 'http://localhost:5000',
      '/manifest.json': 'http://localhost:5000',
    },
  },
  build: {
    outDir: resolve(__dirname, '..', 'dist'),
    emptyOutDir: true,
  },
})
