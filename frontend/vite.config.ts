import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  build: {
    // three + @react-three/fiber + drei form one ~1.3 MB vendor graph that cannot be split further without lazy loading the scene.
    chunkSizeWarningLimit: 1500,
  },
})
