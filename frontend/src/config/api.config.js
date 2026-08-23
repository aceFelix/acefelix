/**
 * 后端 API 基础地址配置
 * 本地开发默认 http://127.0.0.1:8800；
 * 部署时通过 Vite 环境变量 VITE_API_BASE 覆盖（如 Cloudflare Pages + VPS 场景）：
 *   .env.local 或 Pages 构建环境变量中设置 VITE_API_BASE=https://api.example.com
 * @author aceFelix
 */
export const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8800'
