import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/parametric': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/dashboard-data': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/weather-risk': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/weather': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/pay-weekly-premium': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/create-claim': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/auto-trigger': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/profile': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/payment-history': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/onboarding': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/signup': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/login': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/admin': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:5000', changeOrigin: true },
    },
  },
})
