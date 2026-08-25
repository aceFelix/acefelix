/**
 * 宇宙场景搭建模块
 * 负责 3D 图谱的深空背景：灯光、粒子星空、螺旋银河、星云、黑洞，
 * 以及光晕/吸积盘/星云等共用贴图的程序化生成。
 * 从 Graph3D.vue 拆出，主组件只需调用 setupCosmos(scene)。
 * @author aceFelix
 */
import * as THREE from 'three'
import { graphConfig } from '../config/graph.config'

// ---------- 程序化贴图 ----------

// 光晕/星云共用的柔光贴图（canvas 径向渐变，全局复用一份）
let glowTexture = null

/**
 * 生成径向渐变柔光贴图（中心亮、边缘透明）
 * 节点光晕、星云外层雾、黑洞辉光共用
 */
export function getGlowTexture() {
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

// ---------- 黑洞 ----------

/**
 * 创建黑洞：事件视界 + 多层吸积盘 + 引力透镜光环 + 螺旋粒子吸积流
 * 动画循环自带 rAF，销毁句柄挂在 bh.userData.disposeAnimation 上
 * @param {THREE.Scene} scene
 * @param {object} config - graphConfig.cosmos.blackHole（size/position）
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

// ---------- 场景总装 ----------

/**
 * 搭建宇宙场景：灯光 + 粒子星空 + 螺旋银河 + 星云 + 黑洞
 * @param {THREE.Scene} scene - 3d-force-graph 的场景对象
 */
export function setupCosmos(scene) {
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
