/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Frontend calls /api/* (the shape a real ingress would route on:
      // /api/* -> backend, everything else -> static frontend). The
      // backend's own routes aren't prefixed with /api -- it doesn't need
      // to know about that routing convention -- so the prefix is stripped
      // here, same job an ingress rewrite rule would do in a real
      // deployment. Confirmed live: without this, every API call 404s.
      '/api': {
        target: 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/tests/setup.ts'],
    globals: true,
  },
})
