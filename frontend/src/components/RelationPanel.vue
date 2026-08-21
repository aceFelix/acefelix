<!--
  关系管理面板
  提供关系的列表展示、新增、编辑、删除功能。
  @author aceFelix
-->
<script setup>
import { ref, onMounted, computed } from 'vue'
import { api } from '../api'

const props = defineProps({
  relationTypes: { type: Array, default: () => [] },
  entities: { type: Array, default: () => [] },
})
const emit = defineEmits(['refresh'])

const relations = ref([])
const filterType = ref('')

// 新增/编辑表单
const showForm = ref(false)
const editingId = ref(null)
const form = ref({ source: '', target: '', type: '', properties: '{}' })

const entityMap = computed(() => {
  const map = {}
  props.entities.forEach((e) => {
    map[e.id] = e.name
  })
  return map
})

const filteredRelations = computed(() => {
  if (!filterType.value) return relations.value
  return relations.value.filter((r) => r.type === filterType.value)
})

/**
 * 加载关系列表
 */
async function loadRelations() {
  try {
    relations.value = await api.getRelations()
  } catch (err) {
    console.error('加载关系失败:', err)
  }
}

/**
 * 打开新增表单
 */
function openAdd() {
  editingId.value = null
  form.value = {
    source: props.entities[0]?.id || '',
    target: props.entities[1]?.id || '',
    type: props.relationTypes[0] || '',
    properties: '{}',
  }
  showForm.value = true
}

/**
 * 打开编辑表单
 */
function openEdit(relation) {
  editingId.value = relation.id
  form.value = {
    source: relation.source,
    target: relation.target,
    type: relation.type,
    properties: JSON.stringify(relation.properties || {}, null, 2),
  }
  showForm.value = true
}

/**
 * 提交表单
 */
async function submitForm() {
  try {
    let properties = {}
    if (form.value.properties && form.value.properties.trim()) {
      properties = JSON.parse(form.value.properties)
    }
    const data = {
      source: form.value.source,
      target: form.value.target,
      type: form.value.type,
      properties,
    }
    if (editingId.value) {
      await api.updateRelation(editingId.value, data)
    } else {
      await api.createRelation(data)
    }
    showForm.value = false
    await loadRelations()
    emit('refresh')
  } catch (err) {
    alert('操作失败: ' + err.message)
  }
}

/**
 * 删除关系
 */
async function removeRelation(id) {
  if (!confirm('确认删除此关系？')) return
  try {
    await api.deleteRelation(id)
    await loadRelations()
    emit('refresh')
  } catch (err) {
    alert('删除失败: ' + err.message)
  }
}

onMounted(() => loadRelations())
defineExpose({ loadRelations })
</script>

<template>
  <div class="relation-panel">
    <div class="panel-header">
      <h3>关系管理</h3>
      <button class="btn btn-primary" @click="openAdd">+ 新增</button>
    </div>

    <div class="filters">
      <select class="select" v-model="filterType">
        <option value="">全部类型</option>
        <option v-for="t in relationTypes" :key="t" :value="t">{{ t }}</option>
      </select>
    </div>

    <div class="relation-list">
      <div
        v-for="rel in filteredRelations"
        :key="rel.id"
        class="relation-item"
      >
        <div class="relation-info">
          <span class="entity-label">{{ entityMap[rel.source] || '?' }}</span>
          <span class="relation-arrow">
            <span class="relation-type">{{ rel.type }}</span>
            →
          </span>
          <span class="entity-label">{{ entityMap[rel.target] || '?' }}</span>
        </div>
        <div class="relation-actions">
          <button class="icon-btn" @click="openEdit(rel)" title="编辑">✎</button>
          <button class="icon-btn danger" @click="removeRelation(rel.id)" title="删除">✕</button>
        </div>
      </div>
      <div v-if="filteredRelations.length === 0" class="empty-hint">暂无关系</div>
    </div>

    <!-- 弹窗 -->
    <div v-if="showForm" class="modal-overlay" @click.self="showForm = false">
      <div class="modal">
        <h3>{{ editingId ? '编辑关系' : '新增关系' }}</h3>
        <div class="form-group">
          <label>源实体</label>
          <select class="select" v-model="form.source">
            <option v-for="e in entities" :key="e.id" :value="e.id">{{ e.name }} [{{ e.type }}]</option>
          </select>
        </div>
        <div class="form-group">
          <label>目标实体</label>
          <select class="select" v-model="form.target">
            <option v-for="e in entities" :key="e.id" :value="e.id">{{ e.name }} [{{ e.type }}]</option>
          </select>
        </div>
        <div class="form-group">
          <label>关系类型</label>
          <select class="select" v-model="form.type">
            <option v-for="t in relationTypes" :key="t" :value="t">{{ t }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>属性 (JSON)</label>
          <textarea class="input textarea" v-model="form.properties" placeholder='{}'></textarea>
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
.relation-panel {
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
  padding: 8px 16px;
  border-bottom: 1px solid var(--border);
}
.relation-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}
.relation-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  transition: background 0.15s;
}
.relation-item:hover {
  background: rgba(255, 255, 255, 0.04);
}
.relation-info {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
  font-size: 12px;
}
.entity-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-primary);
}
.relation-arrow {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--text-secondary);
  flex-shrink: 0;
}
.relation-type {
  background: rgba(78, 205, 196, 0.15);
  color: var(--accent);
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
}
.relation-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.15s;
}
.relation-item:hover .relation-actions {
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
  height: 80px;
  resize: vertical;
  font-family: 'Consolas', 'Monaco', monospace;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}
</style>
