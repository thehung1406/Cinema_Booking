import { defineConfig, loadEnv } from 'vite'
import process from 'node:process'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const useGateway = env.VITE_API_USE_GATEWAY !== 'false'
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      extensions: ['.js', '.jsx', '.ts', '.tsx']
    },
    server: {
      proxy: {
        '/api': {
          target: env.VITE_API_PROXY_TARGET || (useGateway ? 'http://127.0.0.1:8080' : 'http://127.0.0.1:8000'),
          changeOrigin: true,
          rewrite: useGateway ? undefined : (path) => path.replace(/^\/api(?=\/|$)/, '')
        }
      }
    }
  }
})
