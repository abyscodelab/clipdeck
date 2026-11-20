import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

const nm = (p: string) => path.resolve(__dirname, 'node_modules', p);

export default defineConfig({
  plugins: [react()],
  resolve: {
    // The engine lives in ../template/src and is imported as-is. Make sure it shares one copy of react and remotion
    // with the site (two copies of remotion break the Player's timeline context).
    alias: {
      '@subtle': path.resolve(__dirname, '../template/src'),
      '@styles': path.resolve(__dirname, '../styles'),
      remotion: nm('remotion'),
      react: nm('react'),
      'react-dom': nm('react-dom'),
      '@remotion/layout-utils': nm('@remotion/layout-utils'),
    },
    dedupe: ['react', 'react-dom', 'remotion'],
  },
  server: {fs: {allow: [path.resolve(__dirname, '..')]}},
  build: {target: 'es2022', chunkSizeWarningLimit: 900},
});
