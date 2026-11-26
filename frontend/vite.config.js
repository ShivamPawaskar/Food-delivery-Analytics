import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
  build: {
    outDir: 'dist', emptyOutDir: true,
    rollupOptions: { output: { manualChunks(id) {
      if (!id.includes('node_modules')) return;
      if (/node_modules\/(react|react-dom|scheduler)\//.test(id)) return 'react-vendor';
      if (/node_modules\/(leaflet|react-leaflet)\//.test(id)) return 'maps-vendor';
      if (/node_modules\/(recharts|d3-)/.test(id)) return 'charts-vendor';
      if (id.includes('node_modules/lucide-react/')) return 'icons-vendor';
    } } },
  },
});
