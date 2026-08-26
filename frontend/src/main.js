import { createApp } from 'vue'
import App from './App.vue'
import './style.css'
import { graphConfig } from './config/graph.config'

// 面板毛玻璃透明度：从配置注入 CSS 变量（改 ui.panelOpacity 后刷新页面生效）
document.documentElement.style.setProperty('--panel-alpha', String(graphConfig.ui.panelOpacity))

createApp(App).mount('#app')
