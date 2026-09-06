/**
 * 属性值识别工具
 * 判断实体属性值是图片链接、文档链接还是普通网站链接，
 * 供编辑弹窗与详情面板共用。
 * @author aceFelix
 */

/**
 * 图片属性的键名特征：键名以这些词开头即视为图片属性
 * （如 image、avatar、logo_1、photoUrl 等；排除 website 这类非图片键）
 */
const IMAGE_KEY_PATTERN = /^(image|img|icon|avatar|logo|photo|pic|cover|thumb|banner)/i

/**
 * 常见图片扩展名（外链无键名线索时，靠 URL 后缀兜底识别）
 */
const IMAGE_EXT_PATTERN = /\.(png|jpe?g|gif|webp|svg|bmp|ico|avif)(\?.*)?$/i

/**
 * 判断属性值是否为图片链接
 * 判定规则（满足其一即可）：
 * 1. 后端上传目录 `/uploads/`（本系统上传的必然是图片）
 * 2. 键名具有图片语义（image/avatar/logo...）且值为 http 链接
 * 3. URL 以图片扩展名结尾（键名无线索时的兜底）
 * 由此 `website: https://www.example.com` 不会被误判为图片
 * @param {string} key - 属性键名
 * @param {*} value - 属性值
 * @returns {boolean}
 */
export function isImageProp(key, value) {
  if (typeof value !== 'string' || !value) return false
  if (value.startsWith('/uploads/')) return true
  if (!/^https?:\/\//i.test(value)) return false
  return IMAGE_KEY_PATTERN.test(key) || IMAGE_EXT_PATTERN.test(value)
}

/**
 * 文档扩展名（与后端 DOC_EXT_WHITELIST 保持一致），
 * 同时兼容外链文档（如 GitHub 上的 .pdf/.md）的识别
 */
const DOC_EXT_PATTERN = /\.(pdf|md|txt|docx|xmind)(\?.*)?$/i

/**
 * 判断属性值是否为文档链接
 * 判定规则（满足其一即可）：
 * 1. URL 包含 `/doc-uploads/`（本系统上传的文档目录）
 * 2. http/https 链接且以文档扩展名结尾
 * 不按键名判定：避免 doc/website 类普通链接被误判
 * @param {string} key - 属性键名
 * @param {*} value - 属性值
 * @returns {boolean}
 */
export function isDocProp(key, value) {
  if (typeof value !== 'string' || !value) return false
  if (value.includes('/doc-uploads/')) return true
  return /^https?:\/\//i.test(value) && DOC_EXT_PATTERN.test(value)
}

/**
 * 从文档 URL 提取展示用文件名：
 * 取路径最后一段并 URL 解码，去掉上传时拼接的短 UUID 前缀（如 "a1b2c3d4_简历.pdf" → "简历.pdf"）
 * @param {string} url - 文档 URL
 * @returns {string} 可读文件名
 */
export function docFileName(url) {
  if (typeof url !== 'string' || !url) return ''
  let name = url.split('?')[0].split('/').pop() || ''
  try {
    name = decodeURIComponent(name)
  } catch {
    // 非法百分号编码时保留原样，不阻断展示
  }
  return name.replace(/^[0-9a-f]{8}_/i, '') || name
}

/**
 * 判断属性值是否为网站链接（非图片、非文档的 http/https 地址）
 * 详情面板中渲染为可点击的 <a> 而非图片/文档
 * @param {string} key - 属性键名
 * @param {*} value - 属性值
 * @returns {boolean}
 */
export function isWebUrl(key, value) {
  return (
    typeof value === 'string' &&
    /^https?:\/\//i.test(value) &&
    !isImageProp(key, value) &&
    !isDocProp(key, value)
  )
}
