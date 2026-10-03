import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Em desenvolvimento, /api vai para o servidor local (python edt.py painel --sem-janela).
const servidor = process.env.EDT_API ?? "http://127.0.0.1:8791";

export default defineConfig({
  plugins: [react()],
  server: { port: 5174, strictPort: true, proxy: { "/api": { target: servidor, changeOrigin: true } } },
  build: { chunkSizeWarningLimit: 800 },
});
