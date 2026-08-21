import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Vite 配置：Vue3 插件 + 开发服务器端口
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    open: true,
    // 忽略 .tmp 目录（作为 TMP 使用），避免文件锁导致 watch 冲突
    watch: {
      ignored: ['**/.tmp/**', '**/.yarn-cache/**', '**/.npm-cache/**'],
    },
  },
})
