<!--
  实体管理面板
  提供实体的列表展示、新增、编辑、删除功能，以及按类型过滤。
  @author aceFelix
-->
<script setup>
import { ref, onMounted, computed } from 'vue'
import { api } from '../api'

const props = defineProps({
  entityTypes: { type: Array, default: () => [] },
  entityColors: { type: Object, default: () => ({}) },
  selectedId: { type: String, default: '' },
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

// 新增/编辑表单
const showForm = ref(false)
const editingId = ref(null)
const form = ref({ name: '', type: '', properties: '{}', color: '', size: 0 })

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
    size: 0, // 0 = 自动（按连接数计算）
  }
  showForm.value = true
}

/**
 * 打开编辑表单
 */
function openEdit(entity) {
  editingId.value = entity.id
  form.value = {
    name: entity.name,
    type: entity.type,
    properties: JSON.stringify(entity.properties || {}, null, 2),
    color: entity.color || '',
    size: entity.size || 0,
  }
  showForm.value = true
}

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
    if (form.value.size > 0) {
      data.size = Number(form.value.size)
    } else if (editingId.value) {
      // 编辑时 size 为 0 = 清除自定义大小，回退自动计算
      data.size = 0
    }
    if (editingId.value) {
      await api.updateEntity(editingId.value, data)
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
      <button class="btn btn-primary" @click="openAdd">+ 新增</button>
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
      >
        <div class="entity-info">
          <span class="entity-dot" :style="{ background: entityColor(entity) }"></span>
          <span class="entity-name">{{ entity.name }}</span>
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
        <div class="form-group">
          <label>大小（0 = 自动，按连接数计算）</label>
          <div class="size-picker">
            <input
              type="range"
              min="0"
              max="10"
              step="1"
              v-model.number="form.size"
              :style="{ '--slider-fill': form.size > 0 ? '#4ecdc4' : 'var(--border)' }"
            />
            <span class="size-value" :class="{ auto: form.size === 0 }">
              {{ form.size === 0 ? '自动' : form.size }}
            </span>
          </div>
        </div>
        <div class="form-actions">
          <button class="btn" @click="showForm = false">取消</button>
          <button class="btn btn-primary" @click="submitForm">保存</button>
        </div>
      </div>
    </div>
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

/* 大小滑块 */
.size-picker {
  display: flex;
  align-items: center;
  gap: 12px;
}
.size-picker input[type='range'] {
  flex: 1;
  -webkit-appearance: none;
  appearance: none;
  height: 4px;
  border-radius: 2px;
  background: linear-gradient(
    to right,
    var(--slider-fill, var(--accent)) 0%,
    var(--slider-fill, var(--accent)) var(--slider-progress, 0%),
    rgba(255, 255, 255, 0.12) var(--slider-progress, 0%),
    rgba(255, 255, 255, 0.12) 100%
  );
  outline: none;
  cursor: pointer;
}
.size-picker input[type='range']::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--accent);
  border: 2px solid #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
  cursor: pointer;
}
.size-picker input[type='range']::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--accent);
  border: 2px solid #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
  cursor: pointer;
}
.size-value {
  min-width: 44px;
  text-align: center;
  font-size: 13px;
  font-weight: 600;
  color: var(--accent);
  background: rgba(78, 205, 196, 0.12);
  border-radius: 4px;
  padding: 2px 8px;
}
.size-value.auto {
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.06);
}
</style>
