import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    include: ['src/**/*.spec.ts'],
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      include: [
        'src/api/**/*.ts',
        'src/router/**/*.ts',
        'src/stores/**/*.ts',
        'src/components/**/*.vue',
        'src/views/**/*.vue',
      ],
      exclude: ['src/types/**', 'src/main.ts'],
      thresholds: { lines: 90, statements: 90, branches: 85, functions: 70 },
      reporter: ['text', 'html'],
    },
  },
})
