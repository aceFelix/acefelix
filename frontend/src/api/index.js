/**
 * API 请求封装
 * 统一管理与后端 FastAPI 的通信，提供知识图谱 CRUD 接口。
 * @author aceFelix
 */

const BASE_URL = 'http://127.0.0.1:8800/api'

/**
 * 通用请求封装
 * @param {string} path - 请求路径
 * @param {object} options - fetch 配置
 * @returns {Promise<any>} 响应数据
 */
async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || '请求失败')
  }
  return res.json()
}

export const api = {
  // 获取元数据
  getMeta: () => request('/meta'),

  // 实体 CRUD
  getEntities: (type) => request(`/entities${type ? `?type=${type}` : ''}`),
  getEntity: (id) => request(`/entities/${id}`),
  createEntity: (data) => request('/entities', { method: 'POST', body: JSON.stringify(data) }),
  updateEntity: (id, data) => request(`/entities/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteEntity: (id) => request(`/entities/${id}`, { method: 'DELETE' }),

  // 关系 CRUD
  getRelations: (type) => request(`/relations${type ? `?type=${type}` : ''}`),
  createRelation: (data) => request('/relations', { method: 'POST', body: JSON.stringify(data) }),
  updateRelation: (id, data) => request(`/relations/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteRelation: (id) => request(`/relations/${id}`, { method: 'DELETE' }),

  // 实体类型管理
  getTypes: () => request('/types'),
  createType: (data) => request('/types', { method: 'POST', body: JSON.stringify(data) }),
  updateType: (name, data) => request(`/types/${encodeURIComponent(name)}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteType: (name) => request(`/types/${encodeURIComponent(name)}`, { method: 'DELETE' }),

  // 图谱查询
  getGraph: () => request('/graph'),
  getNeighbors: (id, degree = 1) => request(`/graph/neighbors/${id}?degree=${degree}`),
  search: (q) => request(`/search?q=${encodeURIComponent(q)}`),
  getStats: () => request('/stats'),
}
