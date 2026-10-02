import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
// @ts-expect-error Server-only JavaScript is excluded from the browser type graph.
import { localOwnerBridge } from './server/local-owner.mjs';

const bridge = localOwnerBridge();
export default defineConfig({
  plugins: [react(), ...(bridge ? [bridge.plugin] : [])],
  server: {
    host: '127.0.0.1',
    port: 5191,
    strictPort: true,
    proxy: {
      '/api': { target: process.env.VITE_FRIDAY_API_ORIGIN ?? 'http://127.0.0.1:8765', changeOrigin: true, ...(bridge ? { configure: bridge.configure } : {}) },
      '/health': { target: process.env.VITE_FRIDAY_API_ORIGIN ?? 'http://127.0.0.1:8765', changeOrigin: true },
    },
  },
});
