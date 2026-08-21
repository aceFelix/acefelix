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
import { api } from '../api'

const props = defineProps({
  // 搜索高亮的实体名称
  highlightName: { type: String, default: '' },
})
const emit = defineEmits(['select-entity'])

const containerRef = ref(null)
let graphInstance = null
let ForceGraph3D = null
const entityColors = ref({})
const nodeMap = ref({}) // id -> node data
const loading = ref(true)
const loadingText = ref('正在加载 3D 引擎...')

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
function createNodeObject(node) {
  // 球体半径：优先用自定义大小，否则按 val（连接度数）自动计算
  const radius = node.size || 1.8 + (node.val || 1) * 1.4
  return new THREE.Mesh(
    new THREE.SphereGeometry(radius, 24, 24),
    new THREE.MeshBasicMaterial({ color: node.color })
  )
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
    // 点击标签等效点击节点，联动右侧详情面板
    el.addEventListener('click', () => emit('select-entity', node.id))
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

    // 构造 3d-force-graph 所需的数据格式
    const nodes = graphData.entities.map((e) => ({
      id: e.id,
      name: e.name,
      type: e.type,
      properties: e.properties,
      // 颜色优先级：实体自定义颜色 > 类型默认色
      color: e.color || entityColors.value[e.type] || '#888',
      size: e.size || null, // 自定义大小（null 时按连接数自动计算）
      val: 1, // 布局基础值
    }))

    // 根据度数/自定义大小调整节点布局权重
    const degreeMap = {}
    graphData.relations.forEach((r) => {
      degreeMap[r.source] = (degreeMap[r.source] || 0) + 1
      degreeMap[r.target] = (degreeMap[r.target] || 0) + 1
    })
    nodes.forEach((n) => {
      // 自定义大小后布局间距跟随（val 影响力导向排斥），否则按连接数
      n.val = n.size ? n.size * 0.8 : 1 + (degreeMap[n.id] || 0) * 0.5
      nodeMap.value[n.id] = n
    })

    const links = graphData.relations.map((r) => ({
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
        .nodeColor((node) => node.color)
        .nodeOpacity(1)
        .nodeVal((node) => node.val)
        .linkLabel((link) => `<span style="color:#ccc;background:rgba(0,0,0,0.7);padding:2px 6px;border-radius:3px;font-size:11px">${link.type}</span>`)
        // 连线：亮色 + 方向箭头 + 流动粒子，增强可读性
        .linkColor((link) => link.color)
        .linkOpacity(0.65)
        .linkWidth(1.2)
        .linkDirectionalArrowLength(4.5)
        .linkDirectionalArrowRelPos(0.75)
        .linkDirectionalArrowColor('#8fb3e8')
        .linkDirectionalParticles(2)
        .linkDirectionalParticleWidth(2)
        .linkDirectionalParticleColor('#9be8e0')
        .linkDirectionalParticleSpeed(0.005)
        .cooldownTicks(100)
        .onNodeClick((node) => {
          emit('select-entity', node.id)
        })
        .onNodeDragEnd((node) => {
          // 拖拽后固定节点位置
          node.fx = node.x
          node.fy = node.y
          node.fz = node.z
        })
        .width(width)
        .height(height)
      if (graphInstance.d3Force) {
        graphInstance.d3Force('charge').strength(-80)
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
 * 聚焦到指定节点（相机移动到该节点位置）
 * @param {string} nodeId - 目标节点 ID
 */
function focusNode(nodeId) {
  if (!graphInstance || !nodeMap.value[nodeId]) return
  const node = nodeMap.value[nodeId]
  if (typeof node.x === 'undefined') return
  const distance = 120
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
