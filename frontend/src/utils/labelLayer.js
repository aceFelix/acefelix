/**
 * 节点 HTML 标签覆盖层
 * 每个节点一个绝对定位的 div，通过 rAF 每帧把 3D 坐标投影为屏幕坐标更新位置；
 * 恒定屏幕大小、位于 canvas 之上不被球体遮挡。
 * 从 Graph3D.vue 拆出，组件侧通过 opts 注入相机/高亮/点击回调，
 * 标签层本身不依赖组件状态；rAF 循环同时驱动 onFrame 回调（行星自转等）。
 * @author aceFelix
 */
import * as THREE from 'three'

/**
 * 创建标签覆盖层
 * @param {Function} getContainer - 返回标签层挂载容器（组件的 wrapper DOM）
 * @param {object} opts - 回调配置：
 *   - onClick(node): 标签点击（等效点击节点）
 *   - getCamera(): 返回 THREE.Camera（图实例未就绪时返回空）
 *   - getViewport(): 返回 { width, height } 画布尺寸
 *   - isDimmed(nodeId): 高亮激活时该节点标签是否淡化
 *   - onFrame(): 每帧附加动作（如行星自转推进）
 * @returns {{ update(nodes: Array<object>): void, dispose(): void }}
 */
export function createLabelLayer(getContainer, opts) {
  let layerEl = null // 覆盖在 canvas 上的标签容器
  const labelEls = new Map() // nodeId -> { el, node }
  let rafId = null // rAF 循环句柄
  const projVec = new THREE.Vector3() // 投影复用向量，避免每帧创建对象

  /**
   * 每帧将节点 3D 坐标投影为屏幕坐标，更新标签位置
   * 相机背后的节点标签隐藏；标签恒定屏幕大小且不被球体遮挡
   */
  function tick() {
    // 附加逐帧动作（行星自转等），不额外开 rAF
    opts.onFrame?.()

    const camera = opts.getCamera()
    const { width: graphW, height: graphH } = opts.getViewport()
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
        el.style.opacity = opts.isDimmed(node.id) ? '0.15' : '1'
        el.style.transform = `translate(${x}px, ${y}px) translate(-50%, calc(-100% - 14px))`
      })
    }
    rafId = requestAnimationFrame(tick)
  }

  /**
   * 按最新节点集合重建标签（初始化或数据刷新时调用）
   * @param {Array<object>} nodes - 节点数据数组
   */
  function update(nodes) {
    // 首次初始化：创建标签容器（覆盖在 3D canvas 之上）
    if (!layerEl) {
      layerEl = document.createElement('div')
      layerEl.className = 'graph-label-layer'
      getContainer().appendChild(layerEl)
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
      el.addEventListener('click', () => opts.onClick(node))
      layerEl.appendChild(el)
      labelEls.set(node.id, { el, node })
    })

    // 启动投影更新循环（只启动一次）
    if (!rafId) {
      rafId = requestAnimationFrame(tick)
    }
  }

  /**
   * 停止投影循环并移除标签层（组件卸载时调用）
   */
  function dispose() {
    if (rafId) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
    labelEls.clear()
    layerEl?.remove()
    layerEl = null
  }

  return { update, dispose }
}
