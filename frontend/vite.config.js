import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The backend runs on :8000. Proxying keeps the dashboard on one origin.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
