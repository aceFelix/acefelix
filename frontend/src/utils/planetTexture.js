/**
 * 行星纹理生成模块
 * 程序化生成真实行星地表纹理（等距圆柱投影）与大气散射壳，
 * 从 Graph3D.vue 拆出，供节点构建（createNodeObject）复用。
 * @author aceFelix
 */
import * as THREE from 'three'

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
 * @returns {THREE.CanvasTexture} userData.gasGiant 标记是否为气态风格
 */
export function getPlanetTexture(hexColor) {
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
export function createAtmosphereShell(radius, colorHex) {
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
