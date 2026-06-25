import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const useHttps = process.env.VITE_HTTPS === "1" || process.env.npm_lifecycle_event === "dev:https";
const apiTarget = process.env.VITE_API_TARGET || "http://vkrinvent:5500";
const certFile = fileURLToPath(new URL("../.certs/vkr-dev.crt", import.meta.url));
const keyFile = fileURLToPath(new URL("../.certs/vkr-dev.key", import.meta.url));

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    allowedHosts: ["vkrinvent", "localhost", "127.0.0.1", "192.168.157.249"],
    https: useHttps
      ? {
          cert: fs.readFileSync(certFile),
          key: fs.readFileSync(keyFile),
        }
      : undefined,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
        secure: false,
      },
    },
  },
  preview: {
    host: "0.0.0.0",
    allowedHosts: ["vkrinvent", "localhost", "127.0.0.1", "192.168.157.249"],
  },
});
