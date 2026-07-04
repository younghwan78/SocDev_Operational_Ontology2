/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // 56 PoC dev 서버(8000/5173)와 포트 충돌을 피하려면 VITE_API_TARGET으로 백엔드를 지정한다.
    proxy: {
      "/api": process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
  },
});
