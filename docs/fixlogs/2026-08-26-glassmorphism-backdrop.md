# 修复复盘：导航栏/侧栏/底栏毛玻璃失效，看不到宇宙背景

- 日期：2026-08-26
- 作者：aceFelix
- 影响范围：前端布局（`App.vue` 模板与样式、`Graph3D.vue` 包装器样式）

## 现象

顶部导航栏、左侧面板、底部统计栏呈现为不透明纯黑面板，毛玻璃效果失效，
完全遮挡了 3D 宇宙星空背景，沉浸感丢失。

## 根因

**并非样式被改坏，而是布局设计从首版起就没真正成立**：

- 毛玻璃样式一直存在：`--bg-panel: rgba(8,12,22,0.38)` + `backdrop-filter: blur(16px)`
- 但 3D 画布只渲染在中央 `graph-area`（flex 行内），从不延伸到
  导航栏/侧栏/底栏**下方**
- `backdrop-filter` 只能模糊元素背后的内容——面板背后是页面不透明底色
  `#05070f`，模糊一个纯色等于纯色，视觉上就是"不透光的黑面板"

## 修复方案

把 3D 宇宙提升为全屏背景层，面板悬浮其上：

1. `App.vue` 模板：`Graph3D` 从 `graph-area` 移到 `app-layout` 直属首位；
   `graph-area` 保留为空占位维持 flex 布局
2. `App.vue` 样式：`:deep(.graph3d-wrapper)` 绝对定位 `inset: 0`、`z-index: 0`；
   `.app-layout` 设 `pointer-events: none` 让布局层不拦鼠标，
   `header`/`footer`/`.sidebar` 各自 `pointer-events: auto` 恢复交互
3. `Graph3D.vue`：`.graph3d-wrapper` 补 `pointer-events: auto`，
   保证画布旋转/节点点击/聚焦按钮/路径面板全部可用
4. 侧栏补 `-webkit-backdrop-filter` 前缀（Safari 兼容）

## 验证

- `npx vite build --mode development` 编译通过（exit 0）
- 人工验证清单：
  1. 刷新页面，导航栏/侧栏/底栏应呈半透明，旋转 3D 视角时可见星空在面板后流动
  2. 面板上所有按钮、搜索框、列表交互正常
  3. 中央空白处可旋转/缩放 3D 画布，节点点击/聚焦/路径功能正常

## 经验教训

`backdrop-filter` 毛玻璃成立的前提是**被模糊的内容真实位于元素背后**。
设计"悬浮面板 + 毛玻璃"时，必须确认背景画布延伸到面板区域下方
（全屏铺底或负 margin 延伸），否则模糊的只是页面底色，效果等同于纯色面板。
