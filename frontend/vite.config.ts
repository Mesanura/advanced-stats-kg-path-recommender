import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  build: {
    chunkSizeWarningLimit: 1100,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('echarts')) return 'echarts'
          if (id.includes('element-plus') || id.includes('@element-plus')) return 'element-plus'
          if (id.includes('axios')) return 'http-client'
        },
      },
    },
  },
})
