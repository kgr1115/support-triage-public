import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev proxy: forward API calls to the FastAPI backend on :8000.
// In production both would be served same-origin so this is dev-only.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/triage': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
