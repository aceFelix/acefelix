<!--
  实体管理面板
  提供实体的列表展示、新增、编辑、删除功能，以及按类型过滤。
  @author aceFelix
-->
<script setup>
import { ref, onMounted, computed } from 'vue'
import { api } from '../api'
import { API_BASE } from '../config/api.config'
import TypeManager from './TypeManager.vue'

const props = defineProps({
  entityTypes: { type: Array, default: () => [] },
  entityColors: { type: Object, default: () => ({}) },
  selectedId: { type: String, default: '' },
  graphVersion: { type: Number, default: 1 },
})
const emit = defineEmits(['select', 'refresh'])

// 预设颜色板（新增/编辑实体时可选）
const PRESET_COLORS = [
  '#ff6b6b', '#4ecdc4', '#45b7d1', '#f9ca24', '#a55eea',
  '#fd79a8', '#6c5ce7', '#00b894', '#e17055', '#fdcb6e',
  '#ff9ff3', '#54a0ff', '#01a3a4', '#f368e0', '#eb4d4b',
]

const entities = ref([])
const filterType = ref('')
const searchQuery = ref('')
const showTypeManager = ref(false)
const hoveredId = ref('')

// 新增/编辑表单
const showForm = ref(false)
const editingId = ref(null)
const form = ref({ name: '', type: '', properties: '{}', color: '' })
// 表单打开时的数据版本（乐观锁：提交时校验，防多页面并发覆盖）
const formVersion = ref(null)

// 图片属性管理
const imagePropName = ref('image')
const imageUrl = ref('')
const uploading = ref(false)
const uploadError = ref('')

/**
 * 计算实体显示颜色：自定义颜色 > 类型默认色
 * @param {object} entity - 实体对象
 * @returns {string} 颜色值
 */
function entityColor(entity) {
  return entity.color || props.entityColors[entity.type] || '#888'
}

const filteredEntities = computed(() => {
  let result = entities.value
  if (filterType.value) {
    result = result.filter((e) => e.type === filterType.value)
  }
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter((e) => e.name.toLowerCase().includes(q))
  }
  return result
})

/**
 * 加载实体列表
 */
async function loadEntities() {
  try {
    entities.value = await api.getEntities()
  } catch (err) {
    console.error('加载实体失败:', err)
  }
}

/**
 * 打开新增表单
 */
function openAdd() {
  editingId.value = null
  form.value = {
    name: '',
    type: props.entityTypes[0] || '',
    properties: '{}',
    color: '', // 空 = 使用类型默认色
  }
  showForm.value = true
}

/**
 * 打开编辑表单
 */
function openEdit(entity) {
  editingId.value = entity.id
  formVersion.value = props.graphVersion
  form.value = {
    name: entity.name,
    type: entity.type,
    properties: JSON.stringify(entity.properties || {}, null, 2),
    color: entity.color || '',
  }
  showForm.value = true
}

/**
 * 解析当前 properties JSON
 */
function getProperties() {
  try {
    return form.value.properties && form.value.properties.trim()
      ? JSON.parse(form.value.properties)
      : {}
  } catch {
    return {}
  }
}

/**
 * 把图片 URL 写入指定属性键
 */
function setImageProp(key, url) {
  const properties = getProperties()
  properties[key] = url
  form.value.properties = JSON.stringify(properties, null, 2)
}

/**
 * 添加图片 URL 属性
 */
function addImageUrl() {
  const key = imagePropName.value.trim()
  const url = imageUrl.value.trim()
  if (!key || !url) return
  setImageProp(key, url)
  imageUrl.value = ''
}

/**
 * 上传本地图片并写入属性
 */
async function uploadImage(event) {
  const file = event.target.files?.[0]
  if (!file) return
  uploadError.value = ''
  uploading.value = true
  try {
    const { url } = await api.uploadFile(file)
    // 自动生成不重复的键名
    const properties = getProperties()
    let key = imagePropName.value.trim() || 'image'
    let idx = 1
    const base = key
    while (properties[key] !== undefined) {
      key = `${base}_${idx++}`
    }
    setImageProp(key, `${API_BASE}${url}`)
  } catch (err) {
    uploadError.value = err.message || '上传失败'
  } finally {
    uploading.value = false
    event.target.value = ''
  }
}

/**
 * 删除图片属性
 */
function removeImageProp(key) {
  const properties = getProperties()
  delete properties[key]
  form.value.properties = JSON.stringify(properties, null, 2)
}

/**
 * 判断属性值是否为图片 URL
 */
function isImageUrl(value) {
  if (typeof value !== 'string') return false
  return /^https?:\/\//i.test(value) || value.startsWith('/uploads/')
}

/**
 * 补全图片地址（相对路径补成后端绝对 URL）
 */
function imageSrc(url) {
  if (typeof url !== 'string') return ''
  if (url.startsWith('http')) return url
  return `${API_BASE}${url}`
}

/**
 * 当前 JSON 中的图片属性列表
 */
const imagePropsList = computed(() => {
  const properties = getProperties()
  return Object.entries(properties)
    .filter(([, value]) => isImageUrl(value))
    .map(([key, value]) => ({ key, value }))
})

/**
 * 提交表单（新增或更新）
 */
async function submitForm() {
  try {
    let properties = {}
    if (form.value.properties && form.value.properties.trim()) {
      properties = JSON.parse(form.value.properties)
    }
    const data = { name: form.value.name, type: form.value.type, properties }
    if (form.value.color) {
      data.color = form.value.color
    } else if (editingId.value) {
      // 编辑时未选颜色 = 清除自定义色，回退类型默认色
      data.color = ''
    }
    if (editingId.value) {
      // 乐观锁：携带表单打开时的版本，后端不匹配返回 409
      await api.updateEntity(editingId.value, { ...data, if_version: formVersion.value })
    } else {
      await api.createEntity(data)
    }
    showForm.value = false
    await loadEntities()
    emit('refresh')
  } catch (err) {
    alert('操作失败: ' + err.message)
  }
}

/**
 * 删除实体
 */
async function removeEntity(id) {
  if (!confirm('确认删除此实体？关联的关系也会被删除。')) return
  try {
    await api.deleteEntity(id)
    await loadEntities()
    emit('refresh')
  } catch (err) {
    alert('删除失败: ' + err.message)
  }
}

onMounted(() => loadEntities())
defineExpose({ loadEntities })
</script>

<template>
  <div class="entity-panel">
    <div class="panel-header">
      <h3>实体管理</h3>
      <div class="header-actions">
        <button class="icon-btn" title="类型管理" @click="showTypeManager = true">⚙</button>
        <button class="btn btn-primary" @click="openAdd">+ 新增</button>
      </div>
    </div>

    <!-- 过滤与搜索 -->
    <div class="filters">
      <select class="select" v-model="filterType">
        <option value="">全部类型</option>
        <option v-for="t in entityTypes" :key="t" :value="t">{{ t }}</option>
      </select>
      <input class="input" v-model="searchQuery" placeholder="搜索实体..." />
    </div>

    <!-- 实体列表 -->
    <div class="entity-list">
      <div
        v-for="entity in filteredEntities"
        :key="entity.id"
        class="entity-item"
        :class="{ selected: entity.id === selectedId }"
        @click="emit('select', entity.id)"
        @mouseenter="hoveredId = entity.id"
        @mouseleave="hoveredId = ''"
      >
        <div class="entity-info">
          <span class="entity-dot" :style="{ background: entityColor(entity) }"></span>
          <span
            class="entity-name"
            :style="entity.id === selectedId || entity.id === hoveredId ? { color: entityColor(entity) } : {}"
          >{{ entity.name }}</span>
          <span class="tag" :style="{ background: entityColor(entity) + '33', color: entityColor(entity) }">{{ entity.type }}</span>
        </div>
        <div class="entity-actions">
          <button class="icon-btn" @click.stop="openEdit(entity)" title="编辑">✎</button>
          <button class="icon-btn danger" @click.stop="removeEntity(entity.id)" title="删除">✕</button>
        </div>
      </div>
      <div v-if="filteredEntities.length === 0" class="empty-hint">暂无实体</div>
    </div>

    <!-- 新增/编辑弹窗 -->
    <div v-if="showForm" class="modal-overlay" @click.self="showForm = false">
      <div class="modal">
        <h3>{{ editingId ? '编辑实体' : '新增实体' }}</h3>
        <div class="form-group">
          <label>名称</label>
          <input class="input" v-model="form.name" placeholder="实体名称" />
        </div>
        <div class="form-group">
          <label>类型</label>
          <select class="select" v-model="form.type">
            <option v-for="t in entityTypes" :key="t" :value="t">{{ t }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>属性 (JSON)</label>
          <textarea class="input textarea" v-model="form.properties" placeholder='{"key": "value"}'></textarea>
        </div>
        <div class="form-group">
          <label>图片属性</label>
          <div class="image-props">
            <div
              v-for="img in imagePropsList"
              :key="img.key"
              class="image-prop-item"
            >
              <img :src="imageSrc(img.value)" class="image-thumb" />
              <span class="image-key">{{ img.key }}</span>
              <button class="icon-btn danger" @click="removeImageProp(img.key)" title="删除">✕</button>
            </div>
            <div v-if="imagePropsList.length === 0" class="empty-hint small">暂无图片属性</div>
          </div>
          <div class="image-add-row">
            <input class="input" v-model="imagePropName" placeholder="属性名" style="width: 90px" />
            <input class="input" v-model="imageUrl" placeholder="粘贴图片 URL" />
            <button class="btn" @click="addImageUrl" :disabled="!imageUrl.trim()">添加</button>
          </div>
          <div class="image-upload-row">
            <label class="btn image-upload-btn">
              <input type="file" accept="image/*" @change="uploadImage" :disabled="uploading" />
              {{ uploading ? '上传中...' : '上传本地图片' }}
            </label>
            <span v-if="uploadError" class="upload-error">{{ uploadError }}</span>
          </div>
        </div>
        <div class="form-group">
          <label>颜色（可选，留空使用类型默认色）</label>
          <div class="color-picker">
            <div
              class="color-option default"
              :class="{ active: !form.color }"
              title="类型默认色"
              @click="form.color = ''"
            >默认</div>
            <div
              v-for="c in PRESET_COLORS"
              :key="c"
              class="color-option"
              :class="{ active: form.color === c }"
              :style="{ background: c }"
              :title="c"
              @click="form.color = c"
            ></div>
          </div>
          <div class="color-custom">
            <input type="color" v-model="form.color" />
            <span>自定义颜色</span>
          </div>
        </div>
        <div class="form-actions">
          <button class="btn" @click="showForm = false">取消</button>
          <button class="btn btn-primary" @click="submitForm">保存</button>
        </div>
      </div>
    </div>

    <!-- 类型管理弹窗 -->
    <TypeManager
      v-if="showTypeManager"
      @close="showTypeManager = false"
      @refresh="emit('refresh')"
    />
  </div>
</template>

<style scoped>
.entity-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}
.panel-header h3 {
  font-size: 14px;
  font-weight: 600;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.filters {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  border-bottom: 1px solid var(--border);
}
.filters .select {
  width: 120px;
}
.entity-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}
.entity-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  cursor: pointer;
  transition: background 0.15s;
}
.entity-item:hover {
  background: rgba(255, 255, 255, 0.04);
}
.entity-item.selected {
  background: rgba(78, 205, 196, 0.1);
  border-left: 3px solid var(--accent);
}
.entity-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}
.entity-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.entity-name {
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.entity-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.15s;
}
.entity-item:hover .entity-actions {
  opacity: 1;
}
.icon-btn {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 13px;
}
.icon-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
}
.icon-btn.danger:hover {
  color: var(--danger);
}
.empty-hint {
  padding: 24px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 13px;
}
.empty-hint.small {
  padding: 8px 0;
  font-size: 12px;
}

/* 弹窗 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 24px;
  width: 480px;
  max-width: 90vw;
  max-height: 85vh;
  overflow-y: auto;
}
.modal h3 {
  margin-bottom: 16px;
  font-size: 16px;
}
.form-group {
  margin-bottom: 12px;
}
.form-group label {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}
.textarea {
  height: 120px;
  resize: vertical;
  font-family: 'Consolas', 'Monaco', monospace;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

/* 图片属性 */
.image-props {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}
.image-prop-item {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px;
}
.image-thumb {
  width: 40px;
  height: 40px;
  object-fit: cover;
  border-radius: 4px;
}
.image-key {
  font-size: 12px;
  color: var(--text-secondary);
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.image-add-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.image-add-row .input {
  flex: 1;
  min-width: 0;
}
.image-upload-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.image-upload-btn {
  position: relative;
  cursor: pointer;
  overflow: hidden;
}
.image-upload-btn input[type='file'] {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}
.upload-error {
  color: var(--danger);
  font-size: 12px;
}

/* 颜色选择器 */
.color-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.color-option {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  cursor: pointer;
  border: 2px solid transparent;
  transition: transform 0.15s, border-color 0.15s;
}
.color-option:hover {
  transform: scale(1.15);
}
.color-option.active {
  border-color: #fff;
  transform: scale(1.15);
  box-shadow: 0 0 0 2px var(--bg-secondary), 0 0 0 3.5px var(--accent);
}
.color-option.default {
  width: auto;
  padding: 0 8px;
  border-radius: 4px;
  border: 1px dashed var(--text-secondary);
  color: var(--text-secondary);
  font-size: 11px;
  display: flex;
  align-items: center;
  line-height: 20px;
}
.color-option.default.active {
  border-style: solid;
  border-color: var(--accent);
  color: var(--accent);
}
.color-custom {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}
.color-custom input[type='color'] {
  width: 34px;
  height: 24px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg-primary);
  padding: 1px;
  cursor: pointer;
}

</style>
