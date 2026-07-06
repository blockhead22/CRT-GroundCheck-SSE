import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
    plugins: [react()],
    base: './',
    server: {
        allowedHosts: ['aether.nickblock.dev'],
        host: '127.0.0.1',
        port: 5175,
    },
    test: {
        environment: 'jsdom',
        setupFiles: './src/test/setup.ts',
        css: true,
    },
});
