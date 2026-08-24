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
// 自转中的行星网格列表：节点每次重建前清空，随标签投影循环逐帧推进角度
const spinMeshes = []

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

// 光晕/星云共用的柔光贴图（canvas 径向渐变，全局复用一份）
let glowTexture = null

/**
 * 生成径向渐变柔光贴图（中心亮、边缘透明）
 */
function getGlowTexture() {
  if (glowTexture) return glowTexture
  const size = 128
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = size
  const ctx = canvas.getContext('2d')
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
  g.addColorStop(0, 'rgba(255,255,255,1)')
  g.addColorStop(0.25, 'rgba(255,255,255,0.55)')
  g.addColorStop(0.6, 'rgba(255,255,255,0.12)')
  g.addColorStop(1, 'rgba(255,255,255,0)')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, size, size)
  glowTexture = new THREE.CanvasTexture(canvas)
  return glowTexture
}

// 吸积盘纹理缓存
let accretionTexture = null
/**
 * 生成黑洞吸积盘纹理：内圈被视界遮挡，向外逐渐发亮，外缘渐暗
 */
function getAccretionTexture() {
  if (accretionTexture) return accretionTexture
  const size = 512
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = size
  const ctx = canvas.getContext('2d')
  const cx = size / 2
  const g = ctx.createRadialGradient(cx, cx, size * 0.18, cx, cx, size * 0.5)
  g.addColorStop(0, 'rgba(0,0,0,0)')
  g.addColorStop(0.22, 'rgba(255,210,130,0.85)')
  g.addColorStop(0.32, 'rgba(255,170,70,0.95)')
  g.addColorStop(0.45, 'rgba(255,120,40,0.8)')
  g.addColorStop(0.65, 'rgba(160,60,15,0.35)')
  g.addColorStop(1, 'rgba(0,0,0,0)')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, size, size)
  // 高温湍流纹理
  for (let i = 0; i < 80; i++) {
    const angle = Math.random() * Math.PI * 2
    const r = size * 0.22 + Math.random() * size * 0.22
    const len = 0.1 + Math.random() * 0.35
    ctx.strokeStyle = `rgba(255,250,220,${0.08 + Math.random() * 0.18})`
    ctx.lineWidth = 1 + Math.random() * 2.5
    ctx.beginPath()
    ctx.arc(cx, cx, r, angle, angle + len)
    ctx.stroke()
  }
  accretionTexture = new THREE.CanvasTexture(canvas)
  return accretionTexture
}

// 星云纹理缓存（按颜色区分）
const nebulaTextureCache = new Map()
/**
 * 生成絮状云雾星云纹理：多色 blob 叠加 + 亮星点缀
 */
function getNebulaTexture(baseHex) {
  if (nebulaTextureCache.has(baseHex)) return nebulaTextureCache.get(baseHex)
  const size = 512
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = size
  const ctx = canvas.getContext('2d')
  const base = new THREE.Color(baseHex)
  const cx = size / 2
  const cy = size / 2
  const maxR = size * 0.42
  ctx.clearRect(0, 0, size, size)
  // 随机 blob 叠加出絮状云气（限制在中心圆盘内）
  for (let i = 0; i < 35; i++) {
    const rr = Math.sqrt(Math.random()) * maxR
    const a = Math.random() * Math.PI * 2
    const x = cx + rr * Math.cos(a)
    const y = cy + rr * Math.sin(a)
    const r = 30 + Math.random() * 120
    const alpha = 0.05 + Math.random() * 0.14
    const c = base.clone().offsetHSL(
      (Math.random() - 0.5) * 0.12,
      (Math.random() - 0.5) * 0.25,
      (Math.random() - 0.5) * 0.18
    )
    const g = ctx.createRadialGradient(x, y, 0, x, y, r)
    g.addColorStop(0, `rgba(${c.r * 255 | 0},${c.g * 255 | 0},${c.b * 255 | 0},${alpha})`)
    g.addColorStop(1, `rgba(${c.r * 255 | 0},${c.g * 255 | 0},${c.b * 255 | 0},0)`)
    ctx.fillStyle = g
    ctx.fillRect(0, 0, size, size)
  }
  // 星形成区亮点
  for (let i = 0; i < 16; i++) {
    const rr = Math.sqrt(Math.random()) * maxR
    const a = Math.random() * Math.PI * 2
    const x = cx + rr * Math.cos(a)
    const y = cy + rr * Math.sin(a)
    const r = 3 + Math.random() * 14
    const g = ctx.createRadialGradient(x, y, 0, x, y, r)
    g.addColorStop(0, 'rgba(255,255,255,0.9)')
    g.addColorStop(0.4, 'rgba(255,255,255,0.25)')
    g.addColorStop(1, 'rgba(255,255,255,0)')
    ctx.fillStyle = g
    ctx.fillRect(0, 0, size, size)
  }
  // 圆形边缘遮罩：消除方形纹理硬边，让星云自然融入深空
  ctx.globalCompositeOperation = 'destination-in'
  const mask = ctx.createRadialGradient(cx, cy, 0, cx, cy, size * 0.48)
  mask.addColorStop(0, 'rgba(255,255,255,1)')
  mask.addColorStop(0.7, 'rgba(255,255,255,0.9)')
  mask.addColorStop(1, 'rgba(255,255,255,0)')
  ctx.fillStyle = mask
  ctx.fillRect(0, 0, size, size)
  ctx.globalCompositeOperation = 'source-over'

  const tex = new THREE.CanvasTexture(canvas)
  nebulaTextureCache.set(baseHex, tex)
  return tex
}

// 星球地表纹理缓存（同色节点共享一张贴图）
const planetTextureCache = new Map()

/**
 * 种子化格点值噪声 + fBm 多倍频叠加（行星地表纹理用）
 * period 参数让噪声在水平方向按整数周期无缝循环，
 * 贴到球面后经度 0°/360° 接缝处不可见，避免星球出现一条竖缝
 * @param {number} seed - 随机种子（取自节点颜色，同色星球地表一致）
 * @returns {function(number, number, {octaves?:number, period?:number}): number} fbm 噪声，返回 0~1
 */
function makePlanetNoise(seed) {
  // 整数格点哈希：同一格点永远返回同一随机值，保证噪声连续
  const hash = (x, y) => {
    let n =
      (Math.imul(x, 374761393) +
        Math.imul(y, 668265263) +
        Math.imul(seed | 0, 1442695041)) |
      0
    n = (n ^ (n >>> 13)) | 0
    n = Math.imul(n, 1274126177)
    return ((n ^ (n >>> 16)) >>> 0) / 4294967296
  }
  const smooth = (t) => t * t * (3 - 2 * t)
  // 双线性插值的格点噪声；period > 0 时水平格点按周期取模实现环绕
  const noise2 = (x, y, period) => {
    const xi = Math.floor(x)
    const yi = Math.floor(y)
    const xf = x - xi
    const yf = y - yi
    let x0 = xi
    let x1 = xi + 1
    if (period > 0) {
      x0 = ((xi % period) + period) % period
      x1 = (x0 + 1) % period
    }
    const a = hash(x0, yi)
    const b = hash(x1, yi)
    const c = hash(x0, yi + 1)
    const d = hash(x1, yi + 1)
    const u = smooth(xf)
    const v = smooth(yf)
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v
  }
  // fBm：多个倍频叠加，细节随倍频翻倍、振幅减半；周期同步翻倍保持无缝
  return (x, y, { octaves = 4, period = 0 } = {}) => {
    let sum = 0
    let amp = 0.5
    let f = 1
    let norm = 0
    for (let i = 0; i < octaves; i++) {
      sum += noise2(x * f, y * f, period > 0 ? period * f : 0) * amp
      norm += amp
      amp *= 0.5
      f *= 2
    }
    return sum / norm
  }
}

/**
 * 程序化生成真实行星地表纹理（等距圆柱投影，直接贴到球面）
 * 按颜色种子随机分派两种风格，贴近真实行星的观测特征：
 * - 气态巨行星：纬度云带 + 湍流扭曲 + 沿流向的细流纹 + 风暴暗斑（亮边环）
 * - 类地行星：fBm 高程分海陆 + 地形明暗 + 环形山 + 极地冰盖
 * 两种风格均叠加横向拉丝流云与极地冰盖；水平方向按周期无缝循环
 * @param {string} hexColor - 节点颜色
 * @returns {THREE.CanvasTexture}
 */
function getPlanetTexture(hexColor) {
  if (planetTextureCache.has(hexColor)) return planetTextureCache.get(hexColor)
  const w = 512
  const h = 256
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')

  // 用颜色字符串做种子的线性同余伪随机（同色星球地表、风格一致）
  let seed = 0
  for (const c of hexColor) seed = (seed * 31 + c.charCodeAt(0)) >>> 0
  const rand = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0
    return seed / 4294967296
  }
  const fbm = makePlanetNoise(seed)
  const base = new THREE.Color(hexColor)

  // 风格抽签：约一半为气态条纹行星，其余为类地行星，图谱中星球更多样
  const gasGiant = rand() > 0.45

  // ---- 气态巨行星参数：云带数量/湍流幅度/云带调色板/风暴斑 ----
  const bandCount = 7 + Math.floor(rand() * 4)
  const warpAmp = 0.45 + rand() * 0.55 // 湍流对云带边界的扭曲幅度（云带数单位）
  const palette = Array.from({ length: 6 }, (_, i) =>
    base
      .clone()
      .offsetHSL(
        (rand() - 0.5) * 0.08,
        (rand() - 0.5) * 0.22,
        (i % 2 === 0 ? 1 : -1) * (0.05 + rand() * 0.11)
      )
  )
  const storms = Array.from({ length: gasGiant ? 1 + Math.floor(rand() * 2) : 0 }, () => ({
    u: rand(),
    v: 0.22 + rand() * 0.56,
    ru: 0.045 + rand() * 0.05, // 横向半径（经度占比）
    rv: 0.028 + rand() * 0.035, // 纵向半径（纬度占比）
    core: base.clone().offsetHSL(rand() > 0.5 ? 0.045 : -0.04, 0.14, -0.16),
  }))

  // ---- 类地行星参数：海陆分界高程 + 海洋/陆地配色 ----
  const seaLevel = 0.46 + rand() * 0.08
  const ocean = base.clone().offsetHSL(0, 0.06, -0.17)
  const land = base.clone().offsetHSL(0.025, -0.06, 0.07)

  // 逐像素绘制（全部颜色分量按 0~1 计算，落盘时再乘 255）
  const img = ctx.createImageData(w, h)
  const px = img.data
  for (let y = 0; y < h; y++) {
    const v = y / h
    for (let x = 0; x < w; x++) {
      const u = x / w
      let r, g, b
      if (gasGiant) {
        // 纬度云带：带的位置被湍流扭曲，产生大气流体的搅动感（木星式条纹）
        const warp = (fbm(u * 6, v * 5, { octaves: 4, period: 6 }) - 0.5) * warpAmp
        const bandPos = v * bandCount + warp
        const bi = Math.floor(bandPos)
        let t = bandPos - bi
        t = t * t * (3 - 2 * t) // 相邻云带之间平滑过渡，避免硬条纹
        const p0 = palette[((bi % 6) + 6) % 6]
        const p1 = palette[(((bi + 1) % 6) + 6) % 6]
        r = p0.r + (p1.r - p0.r) * t
        g = p0.g + (p1.g - p0.g) * t
        b = p0.b + (p1.b - p0.b) * t
        // 沿云带流向的细流纹：横向拉伸的高频噪声，模拟高速气流
        const streak = (fbm(u * 22, v * 70, { octaves: 3, period: 22 }) - 0.5) * 0.17
        r += streak
        g += streak
        b += streak
      } else {
        // 类地行星：fBm 高程决定海陆，高程差与细节噪声叠加成地形明暗
        const elev = fbm(u * 4, v * 3, { octaves: 5, period: 4 })
        const src = elev < seaLevel ? ocean : land
        const shade =
          (elev - seaLevel) * 0.55 +
          (fbm(u * 12, v * 9, { octaves: 3, period: 12 }) - 0.5) * 0.16
        r = src.r + shade
        g = src.g + shade
        b = src.b + shade
      }
      // 风暴斑（气态巨行星）：暗色核心 + 外圈亮环，模拟大红斑式巨型涡旋
      for (const s of storms) {
        let du = Math.abs(u - s.u)
        du = Math.min(du, 1 - du) // 经度环绕：跨越接缝的风暴也完整显示
        const d = (du / s.ru) ** 2 + ((v - s.v) / s.rv) ** 2
        if (d < 1) {
          const dd = Math.sqrt(d)
          const coreAmt = Math.pow(1 - dd, 1.6) * 0.85
          r += (s.core.r - r) * coreAmt
          g += (s.core.g - g) * coreAmt
          b += (s.core.b - b) * coreAmt
          // 风暴边缘的抬升亮环（约 72% 半径以外）
          if (dd > 0.72) {
            const rim = ((dd - 0.72) / 0.28) * 0.2
            r += rim
            g += rim
            b += rim
          }
        }
      }
      // 极地冰盖：边界带噪声抖动（非直线），向极点逐渐泛白
      const jitter = (fbm(u * 10, 0.37, { octaves: 2, period: 10 }) - 0.5) * 0.035
      const capTop = 0.055 + jitter
      const capBottom = 0.945 - jitter
      if (v < capTop) {
        const m = ((capTop - v) / capTop) * 0.75
        r += (1 - r) * m
        g += (1 - g) * m
        b += (1 - b) * m
      } else if (v > capBottom) {
        const m = ((v - capBottom) / (1 - capBottom)) * 0.75
        r += (1 - r) * m
        g += (1 - g) * m
        b += (1 - b) * m
      }
      // 稀薄流云：横向拉丝的白色云系浮于地表之上（两种风格共用）
      const cloud = fbm(u * 8 + 3.7, v * 26, { octaves: 4, period: 8 })
      if (cloud > 0.56) {
        const ca = ((cloud - 0.56) / 0.44) * 0.42
        r += (1 - r) * ca
        g += (1 - g) * ca
        b += (1 - b) * ca
      }
      const i = (y * w + x) * 4
      px[i] = Math.min(255, Math.max(0, r * 255))
      px[i + 1] = Math.min(255, Math.max(0, g * 255))
      px[i + 2] = Math.min(255, Math.max(0, b * 255))
      px[i + 3] = 255
    }
  }
  ctx.putImageData(img, 0, 0)

  // 环形山：暗心 + 亮缘的圆形陨坑（仅类地行星，Canvas 叠加即可）
  if (!gasGiant) {
    for (let i = 0; i < 16; i++) {
      const cx = rand() * w
      const cy = h * (0.14 + rand() * 0.72)
      const cr = 2 + rand() * 6
      const g = ctx.createRadialGradient(cx, cy, cr * 0.15, cx, cy, cr)
      g.addColorStop(0, 'rgba(0,0,0,0.30)')
      g.addColorStop(0.72, 'rgba(0,0,0,0.08)')
      g.addColorStop(1, 'rgba(255,255,255,0.16)')
      ctx.fillStyle = g
      ctx.beginPath()
      ctx.arc(cx, cy, cr, 0, Math.PI * 2)
      ctx.fill()
    }
  }

  const tex = new THREE.CanvasTexture(canvas)
  tex.colorSpace = THREE.SRGBColorSpace // 保证颜色按 sRGB 正确显示，不发灰
  tex.wrapS = THREE.RepeatWrapping
  tex.userData = { gasGiant } // 供材质按风格区分粗糙度等参数
  planetTextureCache.set(hexColor, tex)
  return tex
}

/**
 * 创建大气散射壳：略大于球体的 BackSide Fresnel 辉光球，
 * 视线越贴近球缘越亮，模拟真实行星大气层的边缘散射光（地球式的蓝色镶边）
 * @param {number} radius - 行星半径
 * @param {string} colorHex - 大气颜色（取节点色）
 * @returns {THREE.Mesh}
 */
function createAtmosphereShell(radius, colorHex) {
  const material = new THREE.ShaderMaterial({
    uniforms: { atmosphereColor: { value: new THREE.Color(colorHex) } },
    vertexShader: `
      varying vec3 vNormal;
      void main() {
        vNormal = normalize(normalMatrix * normal);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }`,
    fragmentShader: `
      uniform vec3 atmosphereColor;
      varying vec3 vNormal;
      void main() {
        // BackSide 渲染时法线朝内，与视线夹角越小（球缘处）强度越高
        float intensity = pow(max(0.0, 0.74 - dot(vNormal, vec3(0.0, 0.0, 1.0))), 3.0);
        gl_FragColor = vec4(atmosphereColor * 1.35, 1.0) * intensity;
      }`,
    side: THREE.BackSide,
    blending: THREE.AdditiveBlending,
    transparent: true,
    depthWrite: false,
  })
  return new THREE.Mesh(new THREE.SphereGeometry(radius * 1.16, 40, 40), material)
}

/**
 * 创建节点对象：行星（真实地表纹理 + 大气散射壳）+ 外层柔光晕（面向相机的 Sprite）
 * @param {object} node - 节点数据
 * @returns {THREE.Group}
 */
function createNodeObject(node) {
  // 高亮激活时，非高亮节点用暗色球体（视觉淡化）
  const dimmed = hlNodes.value.size > 0 && !hlNodes.value.has(node.id)
  const radius = nodeRadius(node)
  const { glowScale, glowOpacity, emissive } = graphConfig.cosmos

  const group = new THREE.Group()
  // 行星本体：纹理已含基底色，材质 color 置白避免二次着色；
  // 不再使用自发光贴图，让定向光形成明暗晨昏线，突出昼夜立体感；
  // 低强度自发光仅保证暗面不至于全黑，仍能辨认节点颜色
  const tex = graphConfig.cosmos.planetTexture && !dimmed ? getPlanetTexture(node.color) : null
  const material = new THREE.MeshStandardMaterial({
    color: dimmed ? '#2a3142' : tex ? '#ffffff' : node.color,
    emissive: dimmed ? '#000000' : node.color,
    emissiveIntensity: dimmed ? 0 : emissive,
    // 气态行星大气反光更柔（粗糙度低），类地行星地表更粗粝；
    // bumpMap 复用纹理亮度作凹凸，让云带/地形在光照下有起伏感
    roughness: tex?.userData.gasGiant ? 0.62 : 0.9,
    metalness: 0.02,
    ...(tex ? { map: tex, bumpMap: tex, bumpScale: 0.7 } : {}),
  })
  const planet = new THREE.Mesh(new THREE.SphereGeometry(radius, 48, 48), material)
  // 初始自转相位随机，避免同色行星斑纹朝向整齐划一
  planet.rotation.y = Math.random() * Math.PI * 2
  if (tex && graphConfig.cosmos.planetSpin) {
    // 登记进自转列表，由标签投影循环统一驱动（各自速度略有差异）
    spinMeshes.push({ mesh: planet, speed: 0.0009 + Math.random() * 0.0016 })
  }
  group.add(planet)
  // 大气散射壳：球缘一圈柔和的大气辉光（暗化节点跳过）
  if (tex) group.add(createAtmosphereShell(radius, node.color))
  // 外层柔光晕：Sprite 始终面向相机，远处也能辨认节点颜色
  const glow = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: getGlowTexture(),
      color: node.color,
      transparent: true,
      opacity: dimmed ? 0.05 : glowOpacity,
      depthWrite: false,
    })
  )
  glow.scale.set(radius * glowScale, radius * glowScale, 1)
  group.add(glow)
  return group
}

/**
 * 创建黑洞：事件视界 + 多层吸积盘 + 引力透镜光环 + 螺旋粒子吸积流
 * @param {THREE.Scene} scene
 * @param {object} config
 */
function createBlackHole(scene, config) {
  const bh = new THREE.Group()
  const s = config.size

  // 事件视界：纯黑球体
  bh.add(
    new THREE.Mesh(
      new THREE.SphereGeometry(s, 40, 40),
      new THREE.MeshBasicMaterial({ color: 0x000000 })
    )
  )

  // 主吸积盘：带径向渐变纹理，内暗外亮
  const accretionTex = getAccretionTexture()
  const diskMat = new THREE.MeshBasicMaterial({
    map: accretionTex,
    transparent: true,
    opacity: 0.95,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  })
  const disk = new THREE.Mesh(new THREE.RingGeometry(s * 1.35, s * 3.4, 96, 1), diskMat)
  disk.rotation.x = Math.PI / 2.25
  bh.add(disk)

  // 第二吸积盘：更外侧、更淡，反向微倾，营造多环扭曲
  const disk2Mat = new THREE.MeshBasicMaterial({
    map: accretionTex,
    transparent: true,
    opacity: 0.4,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  })
  const disk2 = new THREE.Mesh(new THREE.RingGeometry(s * 2.9, s * 4.6, 96, 1), disk2Mat)
  disk2.rotation.x = Math.PI / 2.05
  disk2.rotation.y = 0.18
  bh.add(disk2)

  // 引力透镜光环：上下弯曲的亮环（受黑洞引力弯曲的光线）
  const lensCurve = new THREE.CatmullRomCurve3(
    Array.from({ length: 80 }, (_, i) => {
      const t = i / 79
      const angle = t * Math.PI * 2
      const r = s * 4.4
      return new THREE.Vector3(
        r * Math.cos(angle),
        r * Math.sin(angle) * 0.38,
        r * Math.sin(angle) * 0.18
      )
    }),
    true
  )
  const lensGeo = new THREE.TubeGeometry(lensCurve, 128, s * 0.1, 8, true)
  const lensMat = new THREE.MeshBasicMaterial({
    color: 0xffddaa,
    transparent: true,
    opacity: 0.55,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  })
  const lensRing = new THREE.Mesh(lensGeo, lensMat)
  lensRing.rotation.x = Math.PI / 2.25
  bh.add(lensRing)

  // 内侧细光环（更接近视界，更亮）
  const lensCurve2 = new THREE.CatmullRomCurve3(
    Array.from({ length: 80 }, (_, i) => {
      const t = i / 79
      const angle = t * Math.PI * 2
      const r = s * 2.8
      return new THREE.Vector3(
        r * Math.cos(angle),
        r * Math.sin(angle) * 0.22,
        r * Math.sin(angle) * 0.1
      )
    }),
    true
  )
  const lensGeo2 = new THREE.TubeGeometry(lensCurve2, 128, s * 0.06, 8, true)
  const lensMat2 = new THREE.MeshBasicMaterial({
    color: 0xffeebb,
    transparent: true,
    opacity: 0.7,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  })
  const lensRing2 = new THREE.Mesh(lensGeo2, lensMat2)
  lensRing2.rotation.x = Math.PI / 2.25
  bh.add(lensRing2)

  // 吸积粒子流：绕黑洞螺旋下落的亮点
  const particleCount = 500
  const pPos = new Float32Array(particleCount * 3)
  const pAngles = new Float32Array(particleCount)
  const pRadii = new Float32Array(particleCount)
  for (let i = 0; i < particleCount; i++) {
    const angle = Math.random() * Math.PI * 2
    const r = s * 1.6 + Math.random() * s * 3.0
    pAngles[i] = angle
    pRadii[i] = r
    pPos[i * 3] = r * Math.cos(angle)
    pPos[i * 3 + 1] = (Math.random() - 0.5) * s * 0.25
    pPos[i * 3 + 2] = r * Math.sin(angle)
  }
  const pGeo = new THREE.BufferGeometry()
  pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3))
  const pMat = new THREE.PointsMaterial({
    color: 0xffcc80,
    size: 2.0,
    transparent: true,
    opacity: 0.85,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  })
  const particles = new THREE.Points(pGeo, pMat)
  particles.userData = { angles: pAngles, radii: pRadii }
  particles.rotation.x = Math.PI / 2.25
  bh.add(particles)

  // 外层暖色辉光
  const glow = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: getGlowTexture(),
      color: 0xffb060,
      transparent: true,
      opacity: 0.22,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    })
  )
  glow.scale.set(s * 9, s * 9, 1)
  bh.add(glow)

  bh.position.set(...config.position)
  scene.add(bh)

  // 黑洞动画循环
  let rafId
  function animate() {
    disk.rotation.z += 0.002
    disk2.rotation.z -= 0.0012
    lensRing.rotation.z += 0.0015
    lensRing2.rotation.z += 0.0022
    const positions = particles.geometry.attributes.position.array
    for (let i = 0; i < particleCount; i++) {
      pAngles[i] += 0.006 / (pRadii[i] / s)
      pRadii[i] *= 0.9994
      if (pRadii[i] < s * 1.4) pRadii[i] = s * 4.0
      positions[i * 3] = pRadii[i] * Math.cos(pAngles[i])
      positions[i * 3 + 2] = pRadii[i] * Math.sin(pAngles[i])
    }
    particles.geometry.attributes.position.needsUpdate = true
    rafId = requestAnimationFrame(animate)
  }
  animate()
  bh.userData.disposeAnimation = () => cancelAnimationFrame(rafId)
}

/**
 * 搭建宇宙场景：灯光 + 粒子星空 + 螺旋银河 + 星云 + 黑洞
 * @param {THREE.Scene} scene - 3d-force-graph 的场景对象
 */
function setupCosmos(scene) {
  const { starCount, starRadius, nebulaCount, galaxyBandCount, blackHole } =
    graphConfig.cosmos

  // 灯光：环境光 + 主定向光 + 蓝色补光，营造星球立体感
  scene.add(new THREE.AmbientLight(0xaabbee, 0.9))
  const dirLight = new THREE.DirectionalLight(0xffffff, 1.0)
  dirLight.position.set(300, 400, 500)
  scene.add(dirLight)
  const fillLight = new THREE.DirectionalLight(0x4455aa, 0.35)
  fillLight.position.set(-400, -200, 300)
  scene.add(fillLight)

  // 星空：远景小星 + 中景亮星
  const makeStars = (count, size, opacity, color = 0xffffff, radiusRange = starRadius) => {
    const positions = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      const r = radiusRange[0] + Math.random() * (radiusRange[1] - radiusRange[0])
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta)
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta)
      positions[i * 3 + 2] = r * Math.cos(phi)
    }
    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    scene.add(
      new THREE.Points(
        geo,
        new THREE.PointsMaterial({
          color,
          size,
          sizeAttenuation: false,
          transparent: true,
          opacity,
          depthWrite: false,
        })
      )
    )
  }
  makeStars(Math.floor(starCount * 0.85), 1.4, 0.75, 0xffffff)
  makeStars(Math.floor(starCount * 0.15), 2.6, 0.95, 0xddeeff)

  // 银河系：螺旋臂 + 中心核球
  {
    const positions = []
    const colors = []
    const sizes = []
    const bulgeCount = Math.floor(galaxyBandCount * 0.12)
    const colorInner = new THREE.Color(0xfff4e0)
    const colorArm = new THREE.Color(0xcfe8ff)
    const colorArmWarm = new THREE.Color(0xffe0c0)
    // 核球：中心密集、发黄白
    for (let i = 0; i < bulgeCount; i++) {
      const r = Math.pow(Math.random(), 2) * 220
      const theta = Math.random() * Math.PI * 2
      const h = (Math.random() - 0.5) * 60 * (1 - r / 220)
      positions.push(r * Math.cos(theta), h, r * Math.sin(theta))
      const c = colorInner.clone().lerp(new THREE.Color(0xffcc80), Math.random() * 0.3)
      colors.push(c.r, c.g, c.b)
      sizes.push(2.0 + Math.random() * 2.0)
    }
    // 四条旋臂：对数螺旋 + 随机散开
    const arms = 4
    const armCount = galaxyBandCount - bulgeCount
    for (let i = 0; i < armCount; i++) {
      const arm = i % arms
      const armOffset = (arm / arms) * Math.PI * 2
      const t = Math.random() * Math.PI * 3.5
      const r = 260 + t * 85 + Math.random() * 140
      const theta = armOffset + t * 0.55 + (Math.random() - 0.5) * 0.5
      const h = (Math.random() - 0.5) * (40 + r * 0.08)
      positions.push(r * Math.cos(theta), h, r * Math.sin(theta))
      const mix = Math.min(1, (r - 260) / 700)
      const c = colorArm.clone().lerp(colorArmWarm, Math.random() * 0.5).lerp(new THREE.Color(0x88aaff), mix * 0.4)
      colors.push(c.r, c.g, c.b)
      sizes.push(1.2 + Math.random() * 1.3)
    }
    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
    geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3))
    geo.setAttribute('size', new THREE.Float32BufferAttribute(sizes, 1))
    const galaxy = new THREE.Points(
      geo,
      new THREE.PointsMaterial({
        size: 1.5,
        vertexColors: true,
        transparent: true,
        opacity: 0.8,
        sizeAttenuation: false,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      })
    )
    galaxy.rotation.x = Math.PI / 3.2
    scene.add(galaxy)
  }

  // 星云：多色絮状云雾团
  const nebulaColors = [0x6c5ce7, 0x45b7d1, 0x4ecdc4, 0xa55eea, 0xff6b81, 0x2c3e87, 0x8e44ad]
  for (let i = 0; i < nebulaCount; i++) {
    const color = nebulaColors[i % nebulaColors.length]
    const r = 800 + Math.random() * 600
    const theta = Math.random() * Math.PI * 2
    const phi = Math.acos(2 * Math.random() - 1)
    const pos = new THREE.Vector3(
      r * Math.sin(phi) * Math.cos(theta),
      r * Math.sin(phi) * Math.sin(theta),
      r * Math.cos(phi)
    )
    const s = 500 + Math.random() * 700
    // 主云雾
    const cloud = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: getNebulaTexture(color),
        color: 0xffffff,
        transparent: true,
        opacity: 0.45 + Math.random() * 0.25,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        alphaTest: 0.005,
      })
    )
    cloud.position.copy(pos)
    cloud.scale.set(s, s, 1)
    scene.add(cloud)
    // 淡色外层雾
    const halo = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: getGlowTexture(),
        color,
        transparent: true,
        opacity: 0.06 + Math.random() * 0.05,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        alphaTest: 0.005,
      })
    )
    halo.position.copy(pos)
    halo.scale.set(s * 1.8, s * 1.8, 1)
    scene.add(halo)
  }

  // 黑洞
  if (blackHole) {
    createBlackHole(scene, blackHole)
  }
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
 * 注意：每次传新函数引用，确保 Kapsule prop diff 检测到变化触发重绘
 */
function refreshHighlight() {
  if (!graphInstance) return
  // 节点对象即将全部重建，先清空自转登记，避免旧网格残留空转
  spinMeshes.length = 0
  graphInstance.nodeColor((node) => nodeColorFn(node))
  graphInstance.linkColor((link) => linkColorFn(link))
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
 * 邻域高亮：以 node 为中心，本地 BFS 计算 N 跳邻域
 * @param {object} node - 中心节点
 * @param {number} hops - 跳数（单击默认 1 跳=直接关系；聚焦模式 2 跳）
 */
function focusNeighborhood(node, hops = 1) {
  // BFS（无向视角：既看入边也看出边）
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
  for (let i = 0; i < hops; i++) {
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
  hlLinks.value = new Set() // 邻域模式按端点判断，无需边集合
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
    focusNeighborhood(node, 2) // 聚焦模式：两跳深挖
    return
  }
  if (mode.value === 'path') {
    handlePathPick(node)
    return
  }
  // 默认交互：高亮直接关系（一跳）+ 打开详情
  focusNeighborhood(node, 1)
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

  // 行星自转：借用标签投影循环逐帧推进角度，不额外开 rAF
  for (const s of spinMeshes) s.mesh.rotation.y += s.speed

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
    // 节点即将重建，清空旧的自转登记列表（重建时会重新注册）
    spinMeshes.length = 0
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
        .backgroundColor(graphConfig.cosmos.spaceColor)
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
      // 搭建宇宙场景：灯光、星空、星云
      setupCosmos(graphInstance.scene())
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
        title="开启后单击节点，高亮其两跳邻域（默认单击为一跳直接关系）"
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
