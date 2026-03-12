import { defineConfig } from "vite";

export default defineConfig({
  server: {
    proxy: {
      // Proxy any request to /lti-proxy/* → laketahoeinfo.org
      "/lti-proxy": {
        target: "https://www.laketahoeinfo.org",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/lti-proxy/, ""),
      },
    },
  },
});
