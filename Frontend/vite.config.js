import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    extensions: ['.js', '.jsx', '.ts', '.tsx']
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  },
  define: {
    'process.env': {
      JWT_SECRET: '64f291e4bdcc0288fb7d105c090f8e3d8fb7241c3e536b14c5fcf048e895bc84296dfa5a3a9aa3aa6ee0542c9bb0622b3d97a586b9c537e88e3d3306e087d9f4',
      JWT_EXPIRATION_TIME: '1d'
    }
  }
})