/**
 * 3D 图谱相机控制工具
 * 全图自适应取景与单节点聚焦，从 Graph3D.vue 拆出；
 * 纯函数式实现，图实例与节点坐标均由调用方传入，不依赖组件状态。
 * @author aceFelix
 */
import { graphConfig } from '../config/graph.config'

/**
 * 根据节点包围盒自动调整相机距离，使全图完整可见
 * 默认相机 fov 约 60°，distance = 包围盒对角线 / (2*tan(fov/2)) * margin
 * @param {object} graphInstance - 3d-force-graph 实例
 * @param {number} [duration] - 相机移动时长（ms）；缺省用配置 camera.fitDuration，0 = 瞬间到位（布局期间实时跟随时用）
 */
export function autoFitCamera(graphInstance, duration) {
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

  const animMs = typeof duration === 'number' ? duration : graphConfig.camera.fitDuration
  graphInstance.cameraPosition(
    { x: center.x, y: center.y, z: center.z + distance },
    center,
    animMs
  )
}

/**
 * 聚焦到指定节点（相机移动到该节点位置）
 * 节点尚未完成布局（无坐标）时静默跳过
 * @param {object} graphInstance - 3d-force-graph 实例
 * @param {object} node - 目标节点（含 x/y/z 坐标）
 */
export function focusCamera(graphInstance, node) {
  if (!graphInstance || !node || typeof node.x === 'undefined') return
  const distance = graphConfig.camera.focusDistance
  const lookAt = { x: node.x, y: node.y, z: node.z }
  const cameraPos = { x: node.x, y: node.y, z: node.z + distance }
  graphInstance.cameraPosition(cameraPos, lookAt, 1000)
}
