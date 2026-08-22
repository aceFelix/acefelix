<!--
  3D 知识图谱可视化组件
  基于 3d-force-graph 库实现力导向 3D 图，支持节点着色、悬浮标签、点击选中。
  节点文字标签使用 HTML 覆盖层渲染（CSS2D 方式）：
  - 恒定屏幕大小，不随相机缩放而变小，始终清晰
  - 位于 canvas 之上，不会被球体遮挡
  @author aceFelix
-->
<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as THREE from 'three'
import { forceCollide } from 'd3-force-3d'
import { api } from '../api'
import { graphConfig } from '../config/graph.config'

const props = defineProps({
  // 搜索高亮的实体名称
  highlightName: { type: String, default: '' },
})
const emit = defineEmits(['select-entity'])

const containerRef = ref(null)
let graphInstance = null
let ForceGraph3D = null
// 仅在数据加载/刷新后的引擎冷却完成时自动适配相机一次；
// 用户拖拽节点引发的重新加热不触发，避免视角被强制拉回
let needAutoFit = true
const entityColors = ref({})
const relationLabels = ref({}) // 关系类型代码 -> 中文标签（路径面板显示用）
const nodeMap = ref({}) // id -> node data
const loading = ref(true)
const loadingText = ref('正在加载 3D 引擎...')

// ---------- 图查询交互状态 ----------
const mode = ref(null) // null | 'focus' | 'path'
const hlNodes = ref(new Set()) // 高亮节点 id 集合（空 = 无高亮）
const hlLinks = ref(new Set()) // 高亮关系 id 集合（路径模式用）
const pathPick = ref(null) // 路径选择状态 { stage: 'start' | 'end', startId }
const pathResult = ref(null) // 路径查询结果（面板显示）
const pathHint = ref('') // 路径模式操作提示

// 节点 HTML 标签层相关
let labelLayer = null // 覆盖在 canvas 上的标签容器
const labelEls = new Map() // nodeId -> { el: HTMLDivElement, node: object }
let rafId = null // rAF 循环句柄
const projVec = new THREE.Vector3() // 投影复用向量，避免每帧创建对象

/**
 * 构造节点 3D 对象（仅球体，文字标签由 HTML 覆盖层渲染）
 * @param {object} node - 节点数据
 * @returns {THREE.Mesh} 球体 Mesh
 */
/**
 * 计算节点视觉半径（球体 + 碰撞检测共用）
 * 仅按连接度数自动计算，受 maxRadius 上限约束
 */
function nodeRadius(node) {
  const { baseRadius, radiusPerDegree, maxRadius } = graphConfig.node
  return Math.min(maxRadius, baseRadius + (node.degree || 0) * radiusPerDegree)
}

function createNodeObject(node) {
  // 高亮激活时，非高亮节点用暗色球体（视觉淡化）
  const dimmed = hlNodes.value.size > 0 && !hlNodes.value.has(node.id)
  return new THREE.Mesh(
    new THREE.SphereGeometry(nodeRadius(node), 24, 24),
    new THREE.MeshBasicMaterial({ color: dimmed ? '#28303f' : node.color })
  )
}

/**
 * 淡化色：高亮激活时非路径/邻域的元素统一压暗
 */
const DIM_COLOR = '#1c222d'

/**
 * 节点颜色 accessor：高亮集合内的节点保持原色，其余暗色
 */
function nodeColorFn(node) {
  if (hlNodes.value.size > 0 && !hlNodes.value.has(node.id)) return DIM_COLOR
  return node.color
}

/**
 * 连线颜色 accessor：
 * - 路径模式：关系 id 在高亮集合内才亮（精确到边）
 * - 聚焦模式：两端都在节点集合内才亮
 */
function linkColorFn(link) {
  if (hlNodes.value.size === 0) return link.color
  if (hlLinks.value.size > 0) {
    return hlLinks.value.has(link.id) ? link.color : DIM_COLOR
  }
  const s = typeof link.source === 'object' ? link.source.id : link.source
  const t = typeof link.target === 'object' ? link.target.id : link.target
  return hlNodes.value.has(s) && hlNodes.value.has(t) ? link.color : DIM_COLOR
}

/**
 * 高亮状态变化后强制重绘节点/连线颜色
 */
function refreshHighlight() {
  if (!graphInstance) return
  graphInstance.nodeColor(nodeColorFn)
  graphInstance.linkColor(linkColorFn)
  graphInstance.nodeThreeObject((node) => createNodeObject(node))
}

/**
 * 清空高亮，恢复全图
 */
function resetHighlight() {
  hlNodes.value = new Set()
  hlLinks.value = new Set()
  pathResult.value = null
  pathPick.value = null
  pathHint.value = ''
  mode.value = null
  refreshHighlight()
}

/**
 * 切换交互模式（聚焦 / 路径）
 */
function toggleMode(m) {
  if (mode.value === m) {
    resetHighlight()
    return
  }
  // 切换前先清一次旧高亮
  hlNodes.value = new Set()
  hlLinks.value = new Set()
  pathResult.value = null
  pathHint.value = ''
  refreshHighlight()
  mode.value = m
  if (m === 'path') {
    pathPick.value = { stage: 'start' }
    pathHint.value = '请点击起点实体'
  }
}

/**
 * 聚焦模式：以 node 为中心，本地 BFS 计算两跳邻域并高亮
 */
function focusNeighborhood(node) {
  // BFS 两跳（无向视角：既看入边也看出边）
  const adjacency = {}
  const links = graphInstance.graphData().links
  links.forEach((l) => {
    const s = typeof l.source === 'object' ? l.source.id : l.source
    const t = typeof l.target === 'object' ? l.target.id : l.target
    ;(adjacency[s] = adjacency[s] || []).push(t)
    ;(adjacency[t] = adjacency[t] || []).push(s)
  })
  const visited = new Set([node.id])
  let frontier = [node.id]
  for (let i = 0; i < 2; i++) {
    const next = []
    frontier.forEach((id) => {
      ;(adjacency[id] || []).forEach((nb) => {
        if (!visited.has(nb)) {
          visited.add(nb)
          next.push(nb)
        }
      })
    })
    frontier = next
  }
  hlNodes.value = visited
  hlLinks.value = new Set() // 聚焦模式按端点判断，无需边集合
  refreshHighlight()
}

/**
 * 路径模式：选起点 -> 选终点 -> 调后端查询并高亮
 */
async function handlePathPick(node) {
  if (!pathPick.value || pathPick.value.stage === 'start') {
    pathPick.value = { stage: 'end', startId: node.id }
    pathHint.value = `起点: ${node.name}，请点击终点实体`
    return
  }
  if (pathPick.value.startId === node.id) {
    pathHint.value = '终点不能与起点相同，请重新点击'
    return
  }
  // 执行查询
  const startId = pathPick.value.startId
  pathHint.value = '查询中...'
  try {
    const res = await api.getPaths(startId, node.id, 3, 10)
    const nodes = new Set()
    const links = new Set()
    res.paths.forEach((p) => {
      p.nodes.forEach((id) => nodes.add(id))
      p.relations.forEach((id) => links.add(id))
    })
    hlNodes.value = nodes
    hlLinks.value = links
    pathResult.value = res
    pathHint.value = ''
    mode.value = null // 查询完成退出选择模式，保留高亮
    refreshHighlight()
    if (!res.paths.length) {
      pathHint.value = '两实体之间 3 跳内无路径'
    }
  } catch (err) {
    pathHint.value = '查询失败: ' + err.message
  }
}

/**
 * 路径文本：甲 -掌握技能-> 乙 -使用工具-> 丙
 */
function pathText(p) {
  return p.node_names
    .map((name, i) => {
      if (i >= p.relation_types.length) return name
      const label = relationLabels.value[p.relation_types[i]] || p.relation_types[i]
      return `${name} <span class="seg">-${label}-></span>`
    })
    .join(' ')
}

/**
 * 图内点击节点分流：按当前模式走不同交互
 */
function onGraphNodeClick(node) {
  if (mode.value === 'focus') {
    focusNeighborhood(node)
    return
  }
  if (mode.value === 'path') {
    handlePathPick(node)
    return
  }
  // 默认交互：打开详情 + 直接高亮该节点两跳邻域（无需先激活模式）
  focusNeighborhood(node)
  emit('select-entity', node.id)
}

/**
 * 创建节点 HTML 标签覆盖层
 * 每个节点生成一个绝对定位的 div，通过 rAF 每帧投影更新位置
 * @param {Array<object>} nodes - 节点数据数组
 */
function setupLabelLayer(nodes) {
  // 首次初始化：创建标签容器（覆盖在 3D canvas 之上）
  if (!labelLayer) {
    labelLayer = document.createElement('div')
    labelLayer.className = 'graph-label-layer'
    containerRef.value.appendChild(labelLayer)
  }

  // 清理旧标签
  labelEls.forEach(({ el }) => el.remove())
  labelEls.clear()

  // 为每个节点创建标签
  nodes.forEach((node) => {
    const el = document.createElement('div')
    el.className = 'graph-label'
    el.textContent = node.name
    el.style.borderColor = node.color
    // 点击标签等效点击节点：开详情 + 高亮两跳邻域
    el.addEventListener('click', () => onGraphNodeClick(node))
    labelLayer.appendChild(el)
    labelEls.set(node.id, { el, node })
  })

  // 启动投影更新循环（只启动一次）
  if (!rafId) {
    rafId = requestAnimationFrame(updateLabels)
  }
}

/**
 * 每帧将节点 3D 坐标投影为屏幕坐标，更新标签位置
 * 相机背后的节点标签隐藏；标签恒定屏幕大小且不被球体遮挡
 */
function updateLabels() {
  const camera = graphInstance?.camera()
  const graphW = graphInstance?.width() || 0
  const graphH = graphInstance?.height() || 0

  if (camera && graphW && graphH) {
    labelEls.forEach(({ el, node }) => {
      // 力导向布局未就绪时节点无坐标，暂时隐藏
      if (typeof node.x === 'undefined') {
        el.style.visibility = 'hidden'
        return
      }
      // 3D 坐标 -> 相机空间（NDC 坐标）
      projVec.set(node.x, node.y, node.z)
      projVec.project(camera)
      // 相机背后的节点（NDC z > 1）隐藏，避免反向显示
      if (projVec.z > 1) {
        el.style.visibility = 'hidden'
        return
      }
      // NDC -> 屏幕像素坐标，标签定位在节点正上方
      const x = (projVec.x * 0.5 + 0.5) * graphW
      const y = (-projVec.y * 0.5 + 0.5) * graphH
      el.style.visibility = 'visible'
      // 高亮激活时，非高亮节点的标签淡化
      el.style.opacity =
        hlNodes.value.size > 0 && !hlNodes.value.has(node.id) ? '0.15' : '1'
      el.style.transform = `translate(${x}px, ${y}px) translate(-50%, calc(-100% - 14px))`
    })
  }
  rafId = requestAnimationFrame(updateLabels)
}

/**
 * 加载图谱数据并渲染 3D 图
 */
async function loadGraph() {
  try {
    // 动态导入 3d-force-graph，避免阻塞组件挂载
    if (!ForceGraph3D) {
      loadingText.value = '正在加载 3D 引擎...'
      const module = await import('3d-force-graph')
      ForceGraph3D = module.default
      console.log('[Graph3D] 3d-force-graph loaded')
    }

    loading.value = true
    loadingText.value = '正在加载图谱数据...'
    const [meta, graphData] = await Promise.all([api.getMeta(), api.getGraph()])
    entityColors.value = meta.entity_colors
    relationLabels.value = meta.relation_type_labels || {}
    // 数据刷新：允许下一次引擎冷却后自动适配一次相机
    needAutoFit = true

    // 构造 3d-force-graph 所需的数据格式
    const nodes = graphData.entities.map((e) => ({
      id: e.id,
      name: e.name,
      type: e.type,
      properties: e.properties,
      // 颜色优先级：实体自定义颜色 > 类型默认色
      color: e.color || entityColors.value[e.type] || '#888',
      val: 1, // 布局基础值
    }))

    // 根据度数/自定义大小调整节点布局权重
    const degreeMap = {}
    graphData.relations.forEach((r) => {
      degreeMap[r.source] = (degreeMap[r.source] || 0) + 1
      degreeMap[r.target] = (degreeMap[r.target] || 0) + 1
    })
    nodes.forEach((n) => {
      const degree = degreeMap[n.id] || 0
      n.degree = degree
      // val 只影响力导向的排斥/质量，不直接决定视觉半径；上限避免中心节点过强
      const { valPerDegree, maxVal } = graphConfig.node
      n.val = Math.min(maxVal, 1 + degree * valPerDegree)
      nodeMap.value[n.id] = n
    })

    const links = graphData.relations.map((r) => ({
      id: r.id,
      source: r.source,
      target: r.target,
      type: r.type,
      color: '#6b86b5',
    }))

    await nextTick()

    // 确保容器尺寸有效
    let width = containerRef.value?.clientWidth || 0
    let height = containerRef.value?.clientHeight || 0
    if (!width) {
      width = containerRef.value?.parentElement?.clientWidth || window.innerWidth
    }
    if (!height) {
      height = containerRef.value?.parentElement?.clientHeight || window.innerHeight
    }
    console.log('[Graph3D] init size:', { width, height, nodeCount: nodes.length, linkCount: links.length })

    // 渲染或更新图
    if (graphInstance) {
      graphInstance.width(width).height(height).graphData({ nodes, links })
    } else {
      // 使用 3d-force-graph 的标准链式初始化方式
      // 注意：必须使用 new 或 ForceGraph3D()(dom) 触发 Kapsule 初始化，
      // 直接 ForceGraph3D(dom) 调用会跳过 init，导致 canvas 不创建
      graphInstance = new ForceGraph3D(containerRef.value)
        .backgroundColor('#0a0a0f')
        .graphData({ nodes, links })
        .nodeLabel((node) => {
          const propsStr = node.properties && Object.keys(node.properties).length
            ? `<br/><span style="color:#aaa;font-size:11px">${Object.entries(node.properties).map(([k, v]) => `${k}: ${v}`).join('<br/>')}</span>`
            : ''
          return `<div style="background:rgba(20,20,31,0.95);padding:8px 12px;border-radius:6px;border:1px solid rgba(255,255,255,0.1)">
            <b style="color:${node.color}">${node.name}</b>
            <span style="color:#888;font-size:11px;margin-left:6px">[${node.type}]</span>
            ${propsStr}
          </div>`
        })
        // 自定义节点 3D 对象：实心球体（文字由 HTML 覆盖层渲染）
        .nodeThreeObject((node) => createNodeObject(node))
        .nodeColor(nodeColorFn)
        .nodeOpacity(1)
        .nodeVal((node) => node.val)
        .linkLabel((link) => `<span style="color:#ccc;background:rgba(0,0,0,0.7);padding:2px 6px;border-radius:3px;font-size:11px">${link.type}</span>`)
        // 连线：亮色 + 方向箭头 + 流动粒子，增强可读性
        .linkColor(linkColorFn)
        .linkOpacity(0.65)
        .linkWidth(1.2)
        .linkDirectionalArrowLength(4.5)
        .linkDirectionalArrowRelPos(0.75)
        .linkDirectionalArrowColor('#8fb3e8')
        .linkDirectionalParticles(2)
        .linkDirectionalParticleWidth(2)
        .linkDirectionalParticleColor('#9be8e0')
        .linkDirectionalParticleSpeed(0.005)
        // 让力导向充分展开：更多冷却轮数 + 更慢 alpha 衰减
        .cooldownTicks(graphConfig.force.cooldownTicks)
        .d3AlphaDecay(graphConfig.force.alphaDecay)
        .onNodeClick((node) => {
          onGraphNodeClick(node)
        })
        .onBackgroundClick(() => {
          // 点空白只取消未完成的路径选择，不清高亮——
          // 清高亮统一走「重置」按钮，避免旋转视角时误触清空
          if (mode.value === 'path') {
            pathPick.value = { stage: 'start' }
            pathHint.value = '已取消，请点击起点实体'
          }
        })
        .onNodeDragEnd((node) => {
          // 拖拽后固定节点位置
          node.fx = node.x
          node.fy = node.y
          node.fz = node.z
        })
        // 引擎停止后自动把相机拉远到能装下全图（仅首次加载/数据刷新时）
        .onEngineStop(() => {
          if (needAutoFit) {
            needAutoFit = false
            autoFitCamera()
          }
        })
        .width(width)
        .height(height)
        // 初始相机退后，给布局留出空间
        .cameraPosition(
          { x: 0, y: 0, z: graphConfig.camera.initialZ },
          { x: 0, y: 0, z: 0 },
          0
        )
      if (graphInstance.d3Force) {
        // 加大斥力、拉长连线，节点自然散开
        graphInstance.d3Force('charge').strength(graphConfig.force.chargeStrength)
        const linkForce = graphInstance.d3Force('link')
        if (linkForce && linkForce.distance) {
          linkForce.distance(graphConfig.force.linkDistance)
        }
        // 硬碰撞：球体半径 + 标签边距，防止镶嵌重叠
        graphInstance.d3Force(
          'collide',
          forceCollide((n) => nodeRadius(n) + graphConfig.force.collidePadding)
        )
      }
      console.log('[Graph3D] instance created:', !!graphInstance)
    }

    // 重建 HTML 标签层（初始化或数据刷新时都会同步节点）
    setupLabelLayer(nodes)
    loading.value = false
  } catch (err) {
    loading.value = false
    console.error('加载图谱失败:', err)
    loadingText.value = '加载失败: ' + err.message
  }
}

/**
 * 根据节点包围盒自动调整相机距离，使全图完整可见
 * 默认相机 fov 约 60°，distance = 包围盒对角线 / (2*tan(fov/2)) * margin
 */
function autoFitCamera() {
  if (!graphInstance) return
  const nodes = graphInstance.graphData().nodes
  if (!nodes.length) return

  const xs = nodes.map((n) => n.x || 0)
  const ys = nodes.map((n) => n.y || 0)
  const zs = nodes.map((n) => n.z || 0)
  const min = { x: Math.min(...xs), y: Math.min(...ys), z: Math.min(...zs) }
  const max = { x: Math.max(...xs), y: Math.max(...ys), z: Math.max(...zs) }
  const center = {
    x: (min.x + max.x) / 2,
    y: (min.y + max.y) / 2,
    z: (min.z + max.z) / 2,
  }
  const diagonal = Math.sqrt(
    Math.pow(max.x - min.x, 2) +
    Math.pow(max.y - min.y, 2) +
    Math.pow(max.z - min.z, 2)
  )
  // 预留边距；最小距离防止空图怼脸，给标签留出呼吸空间
  const { fitMargin, minFitDistance } = graphConfig.camera
  const distance = Math.max(minFitDistance, diagonal / (2 * Math.tan(Math.PI / 6)) * fitMargin)

  graphInstance.cameraPosition(
    { x: center.x, y: center.y, z: center.z + distance },
    center,
    1200
  )
}

/**
 * 聚焦到指定节点（相机移动到该节点位置）
 * @param {string} nodeId - 目标节点 ID
 */
function focusNode(nodeId) {
  if (!graphInstance || !nodeMap.value[nodeId]) return
  const node = nodeMap.value[nodeId]
  if (typeof node.x === 'undefined') return
  const distance = graphConfig.camera.focusDistance
  const lookAt = { x: node.x, y: node.y, z: node.z }
  const cameraPos = { x: node.x, y: node.y, z: node.z + distance }
  graphInstance.cameraPosition(cameraPos, lookAt, 1000)
}

// 搜索高亮
watch(() => props.highlightName, (name) => {
  if (!graphInstance || !name) return
  const match = Object.values(nodeMap.value).find((n) =>
    n.name.toLowerCase().includes(name.toLowerCase())
  )
  if (match) {
    focusNode(match.id)
  }
})

onMounted(() => {
  console.log('[Graph3D] onMounted')
  loadGraph()
  // 窗口大小变化时自适应
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  // 停止标签投影循环并清理标签层
  if (rafId) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
  labelEls.clear()
  labelLayer?.remove()
  labelLayer = null
  if (graphInstance) {
    graphInstance._destructor()
    graphInstance = null
  }
})

function handleResize() {
  if (graphInstance && containerRef.value) {
    graphInstance.width(containerRef.value.clientWidth)
    graphInstance.height(containerRef.value.clientHeight)
  }
}

// 暴露方法供父组件调用
defineExpose({ loadGraph, focusNode })
</script>

<template>
  <div class="graph3d-wrapper">
    <div ref="containerRef" class="graph3d-container"></div>

    <!-- 图查询工具条 -->
    <div class="graph-toolbar">
      <button
        class="tool-btn"
        :class="{ active: mode === 'focus' || (hlNodes.size > 0 && !pathResult) }"
        title="开启后单击节点，高亮其两跳邻域"
        @click="toggleMode('focus')"
      >聚焦</button>
      <button
        class="tool-btn"
        :class="{ active: mode === 'path' }"
        title="依次点击两个实体，查询它们之间的关联路径"
        @click="toggleMode('path')"
      >路径</button>
      <button
        v-if="mode || hlNodes.size > 0"
        class="tool-btn"
        title="清空高亮，恢复全图"
        @click="resetHighlight"
      >重置</button>
    </div>

    <!-- 路径模式操作提示 -->
    <div v-if="pathHint" class="path-hint">{{ pathHint }}</div>

    <!-- 路径查询结果面板 -->
    <div v-if="pathResult && pathResult.paths.length" class="path-panel">
      <div class="path-panel-header">
        <span>关联路径（{{ pathResult.paths.length }} 条）</span>
        <button class="path-close" @click="resetHighlight">✕</button>
      </div>
      <div
        v-for="(p, i) in pathResult.paths"
        :key="i"
        class="path-line"
        :class="{ best: i === 0 }"
      >
        <span class="path-len">{{ p.length }}跳</span>
        <span class="path-text" v-html="pathText(p)"></span>
      </div>
    </div>

    <div v-if="loading" class="loading-overlay">
      <div class="loading-spinner"></div>
      <div class="loading-text">{{ loadingText }}</div>
    </div>
  </div>
</template>

<style scoped>
.graph3d-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
}
.graph3d-container {
  width: 100%;
  height: 100%;
}
/* 节点文字标签覆盖层：位于 canvas 之上，恒定屏幕大小 */
:deep(.graph-label-layer) {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  pointer-events: none;
  z-index: 5;
}
:deep(.graph-label) {
  position: absolute;
  top: 0;
  left: 0;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.4;
  color: #fff;
  background: rgba(10, 10, 15, 0.82);
  border: 1px solid;
  border-radius: 4px;
  white-space: nowrap;
  pointer-events: auto;
  cursor: pointer;
  transform: translate(-50%, calc(-100% - 14px));
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.45);
  transition: background 0.15s;
}
:deep(.graph-label:hover) {
  background: rgba(30, 30, 48, 0.95);
}

/* 图查询工具条 */
.graph-toolbar {
  position: absolute;
  top: 12px;
  left: 12px;
  display: flex;
  gap: 6px;
  z-index: 10;
}
.tool-btn {
  padding: 5px 14px;
  font-size: 12px;
  color: var(--text-secondary, #aab4c4);
  background: rgba(20, 24, 33, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  cursor: pointer;
  backdrop-filter: blur(4px);
  transition: all 0.15s;
}
.tool-btn:hover {
  color: #fff;
  border-color: rgba(255, 255, 255, 0.3);
}
.tool-btn.active {
  color: #0d1117;
  background: var(--accent, #4ecdc4);
  border-color: var(--accent, #4ecdc4);
  font-weight: 600;
}

/* 路径模式提示 */
.path-hint {
  position: absolute;
  top: 52px;
  left: 12px;
  padding: 6px 12px;
  font-size: 12px;
  color: var(--accent, #4ecdc4);
  background: rgba(20, 24, 33, 0.9);
  border: 1px solid rgba(78, 205, 196, 0.35);
  border-radius: 6px;
  z-index: 10;
  backdrop-filter: blur(4px);
}

/* 路径结果面板 */
.path-panel {
  position: absolute;
  top: 84px;
  left: 12px;
  width: 380px;
  max-width: calc(100% - 24px);
  max-height: 45%;
  overflow-y: auto;
  background: rgba(18, 22, 30, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 10px 12px;
  z-index: 10;
  backdrop-filter: blur(6px);
}
.path-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary, #e8edf4);
  margin-bottom: 8px;
}
.path-close {
  border: none;
  background: transparent;
  color: var(--text-secondary, #889);
  cursor: pointer;
  font-size: 13px;
  padding: 0 4px;
}
.path-close:hover {
  color: #fff;
}
.path-line {
  display: flex;
  gap: 8px;
  padding: 5px 6px;
  font-size: 11px;
  line-height: 1.6;
  border-radius: 4px;
  color: var(--text-secondary, #aab4c4);
}
.path-line.best {
  background: rgba(78, 205, 196, 0.08);
  color: var(--text-primary, #e8edf4);
}
.path-len {
  flex-shrink: 0;
  color: var(--accent, #4ecdc4);
  font-weight: 600;
}
.path-text :deep(.seg) {
  color: #6b86b5;
  padding: 0 2px;
}
.loading-overlay {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: var(--text-secondary);
  pointer-events: none;
  z-index: 10;
}
.loading-spinner {
  width: 32px;
  height: 32px;
  border: 2px solid rgba(78, 205, 196, 0.2);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
.loading-text {
  font-size: 13px;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
