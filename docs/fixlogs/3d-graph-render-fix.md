# 3D 知识图谱渲染空白修复复盘

## 1. 问题现象

- **场景**：`acefelix` 知识图谱原型搭建完成后，前端页面正常加载（实体面板、统计栏、后端 API 均正常），但**中央 3D 可视化区域完全空白**
- **具体表现**：
  - 页面无 `<canvas>` 元素
  - `.graph3d-container` 容器存在且有尺寸（619×494），但内部无任何子元素
  - 浏览器控制台**无任何报错**（无 TypeError / WebGL 错误），属于"静默失败"
- **影响范围**：3D 知识图谱核心功能不可用，只能使用左侧列表管理数据

## 2. 排查过程

| 阶段 | 假设/判断 | 实际操作 | 结论 |
|---|---|---|---|
| 1 | 可能是容器高度为 0，Three.js 无法初始化 | 用浏览器工具测量 `.graph3d-container` 尺寸 | clientWidth=619、clientHeight=494，尺寸正常，**假设排除** |
| 2 | 可能是 3d-force-graph 动态导入卡住 | 检查控制台 [Graph3D] 日志 | `3d-force-graph loaded`、`instance created: true` 均有输出，导入正常 |
| 3 | 可能是 WebGL 环境/GPU 不支持 | 浏览器执行 `canvas.getContext('webgl2')` | 返回 OK，WebGL 支持正常，**假设排除** |
| 4 | **Kapsule 初始化被跳过（根因）** | 对照实验：动态 import 后分别执行 `new FG3D(div)` / `FG3D()(div)` / `FG3D(div)` | `new` 和 `()(dom)` 均创建 canvas；直接 `FG3D(div)` 无 canvas，与源码分析完全一致 |

### 关键转折点

通过阅读 3d-force-graph 底层依赖 **kapsule** 的源码（[kapsule.js:675](file:///e:/2.MyProjects/MyAgentChat/J.A.R.V.I.S/acefelix/frontend/node_modules/kapsule/dist/kapsule.js#L675)）发现：

```js
// kapsule.js 核心逻辑
if (classMode && nodeElement && comp(nodeElement)) { ... init ... }
```

即**只有 `new ForceGraph3D(dom)` 或 `ForceGraph3D()(dom)` 两种调用方式才会触发初始化**（创建 WebGLRenderer 并把 canvas 挂载到 DOM）。直接 `ForceGraph3D(dom)` 调用时 `classMode=false`，初始化被短路跳过。

## 3. 根因分析

- **真正原因**：3d-force-graph 基于 Kapsule 封装。Kapsule 内部通过 `new` 关键字或"先无参创建、再传 DOM 调用"两种方式区分初始化模式。原代码使用 `ForceGraph3D(dom)` 直接调用，Kapsule 判定为非初始化模式，导致：
  - 实例对象被创建（所以 `instance created: true` 日志正常输出）
  - 但 **WebGLRenderer 和 canvas 从未创建**（所以页面空白且无报错）
- **为什么之前的实现会出错**：对 Kapsule 库的调用约定不了解，误以为"函数式调用 + 传 DOM"等价于"new 实例化"
- **涉及模块**：`3d-force-graph` → `kapsule`（底层封装库）

## 4. 修复方案

**修改文件**：[Graph3D.vue](file:///e:/2.MyProjects/MyAgentChat/J.A.R.V.I.S/acefelix/frontend/src/components/Graph3D.vue)

**修改内容**：初始化方式从函数式调用改为 `new` 实例化，并添加注释说明

```js
// 修复前（Kapsule 初始化被跳过，canvas 不创建）
graphInstance = ForceGraph3D(containerRef.value)

// 修复后（触发 Kapsule 初始化）
graphInstance = new ForceGraph3D(containerRef.value)
```

**为什么有效**：`new ForceGraph3D(dom)` 是 Kapsule 的类模式调用，会正确触发 `comp(nodeElement)` 初始化流程，创建 WebGLRenderer 并将 canvas 挂载到容器。

## 5. 验证结果

- **修复后验证**：
  - 页面 `<canvas>` 元素数量：0 → 1（594×679 WebGL 画布）
  - `.graph3d-container` 子元素：0 → 1（scene-container）
  - 控制台日志：`[Graph3D] init size: {width: 432, height: 494, nodeCount: 25, linkCount: 40}`、`instance created: true`，无任何错误
  - 3D 场景操作提示 "Left-click: rotate, Mouse-wheel/middle-click: zoom, Right-click: pan" 正常显示
- **人工测试**：浏览器打开页面，确认 3D 力导向图渲染（25 节点、40 边），节点着色、交互正常
- **编译验证**：`npx vite build --mode development` 编译通过
- **回归检查**：实体面板 25 个实体、统计栏 "25 实体 40 关系" 均正常，无回归问题

## 6. 涉及文件

| 文件 | 改动说明 |
|---|---|
| `frontend/src/components/Graph3D.vue` | 修复 ForceGraph3D 初始化方式（函数调用 → new 实例化） |
| `frontend/vite.config.js` | 添加 watch.ignored 排除 .tmp/.yarn-cache/.npm-cache，避免沙箱临时文件锁导致 Vite 崩溃 |
| `frontend/src/App.vue` | graph-area 增加 min-width: 0，优化弹性布局 |

## 7. 经验总结

- **Kapsule 封装的库（3d-force-graph、react-force-graph 等）必须用 `new` 或 `()(dom)` 调用方式**，直接传 DOM 调用不会触发初始化，且不会报任何错误，极难排查
- **排查"空白但不报错"问题的有效方法**：
  1. 先检查 DOM：容器是否渲染、是否有 canvas、是否有子元素
  2. 再查控制台：区分"代码没执行"和"执行了但静默失败"
  3. 读底层依赖源码，理解库的调用约定
  4. 做对照实验验证假设（分别用不同调用方式测试）
- **可固化为规则**：使用 Kapsule 系图形库时，初始化必须遵循官方 README 的调用方式（`new` 或 `ForceGraph3D()(dom)`）
