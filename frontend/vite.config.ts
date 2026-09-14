import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5191,
    strictPort: true,
    proxy: {
      '/api': { target: process.env.VITE_FRIDAY_API_ORIGIN ?? 'http://127.0.0.1:8765', changeOrigin: true },
    },
  },
});
