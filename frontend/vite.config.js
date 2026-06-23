import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const host = process.env.VITE_DEV_SERVER_HOST || '0.0.0.0';
const port = Number.parseInt(process.env.VITE_DEV_SERVER_PORT || process.env.PORT || '5173', 10);

export default defineConfig({
  plugins: [react()],
  server: {
    host,
    port
  }
});
