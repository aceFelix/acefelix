# website 属性被误判为图片属性修复复盘

## 1. 问题现象

- **场景**：编辑实体时，在属性 JSON 中添加 `"website": "https://www.deepseek.com"`
- **具体表现**：
  1. 编辑弹窗的「图片属性」区把 `website` 列成了图片缩略图
  2. 右侧详情面板把该值渲染成 `<img>`（加载失败的破图）而非网站链接
- **影响范围**：所有值为普通网站链接的属性（`website`、`homepage`、`url` 等）

## 2. 排查过程

| 阶段 | 排查点 | 结论 |
|---|---|---|
| 1 | 图片属性识别逻辑 | `EntityPanel.vue` / `App.vue` 各有一份 `isImageUrl(value)`，只判断值是否为 http URL 或 `/uploads/` 路径 |
| 2 | 判定依据 | **只看值、不看键名**——任何 `https://` 开头的值都被当成图片 |

## 3. 根因分析

- **真正原因**：`isImageUrl` 的判定条件过于宽泛（`/^https?:\/\//` 即图片），
  没有利用属性键名的语义信息，导致 `website`/`homepage` 这类普通链接被误判。
- **为什么两份代码同时出错**：编辑弹窗与详情面板各自复制了一份相同逻辑，坏规则被复制了两遍。
- **涉及模块**：`frontend/src/App.vue`、`frontend/src/components/EntityPanel.vue`

## 4. 修复方案

**新增文件**：[frontend/src/utils/property.js](file:///e:/2.MyProjects/MyAgentChat/J.A.R.V.I.S/acefelix/frontend/src/utils/property.js)

识别规则收口为公共工具，按"键名语义 + URL 特征"两层判定：

```js
// isImageProp(key, value) 满足其一即图片：
// 1. /uploads/ 目录（本系统上传的必然是图片）
// 2. 键名以 image/img/icon/avatar/logo/photo/pic/cover/thumb/banner 开头 且值为 http 链接
// 3. URL 以图片扩展名结尾（.png/.jpg/.webp... 兜底）
```

配套 `isWebUrl(key, value)`：非图片的 http 链接，详情面板渲染为可点击 `<a>`。

| 文件 | 改动 |
|---|---|
| `frontend/src/utils/property.js` | 新增 `isImageProp` / `isWebUrl` |
| `frontend/src/components/EntityPanel.vue` | `imagePropsList` 改用 `isImageProp(key, value)`，删除本地 `isImageUrl` |
| `frontend/src/App.vue` | 详情面板三分支渲染：图片 → `<img>`；网站链接 → `<a>`；其余 → 文本 |

**为什么有效**：`website` 键名不匹配图片语义、值也无图片扩展名，两个条件都不命中，
归类为普通网站链接，编辑弹窗不再把它收进「图片属性」，详情面板渲染为可点击链接。

## 5. 验证结果

- **单元测试**：`node` 直接驱动纯函数，8 个用例全过（`website` 域名链接、
  `image`/`avatar` 外链、`/uploads/` 路径、中文属性值、图片扩展名兜底等）
- **编译验证**：`npx vite build --mode development` 通过
- **手工验证**：编辑实体添加 `website` 属性 → 「图片属性」区不再出现该项；
  详情面板中 `website` 显示为可点击链接

## 6. 经验总结

- **值类型判定要联合键名语义**：URL 是"图片"还是"链接"单看值无法区分，
  键名是最强的语义信号，扩展名/目录只做兜底。
- **重复逻辑必然重复出错**：同一判定在两个组件各写一遍，修复时也容易漏一处；
  判定规则应第一时间收口到 `utils/` 公共模块。
- **纯函数优先**：识别逻辑写成无依赖的纯函数，脱离框架也能用 node 直接跑用例验证。
