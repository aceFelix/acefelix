<!--
  关系类型管理弹窗
  提供关系类型的查看、新增、改标签、改名、删除功能。
  删除保护：有关联正在使用的类型不可删（后端校验）。
  每个类型 = 英文代码（存储值）+ 中文标签（界面显示）。
  @author aceFelix
-->
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const emit = defineEmits(['close', 'refresh'])

const types = ref({}) // name -> 中文标签
const usage = ref({}) // name -> 关系数
// 新增表单
const newName = ref('')
const newLabel = ref('')
// 改名状态
const renaming = ref('') // 正在改名的类型代码
const renameValue = ref('')
// 改标签状态
const editingLabel = ref('') // 正在改标签的类型代码
const labelValue = ref('')

// 自定义指令：输入框自动聚焦（script setup 中 vFocus 即模板里的 v-focus）
const vFocus = { mounted: (el) => el.focus() }

/**
 * 加载类型表与每个类型的关系用量
 */
async function load() {
  try {
    const [t, relations] = await Promise.all([api.getRelationTypes(), api.getRelations()])
    types.value = t
    const counts = {}
    relations.forEach((r) => {
      counts[r.type] = (counts[r.type] || 0) + 1
    })
    usage.value = counts
  } catch (err) {
    alert('加载类型失败: ' + err.message)
  }
}

/**
 * 新增关系类型
 */
async function addType() {
  const name = newName.value.trim()
  if (!name) {
    alert('请输入类型代码（如 MENTORS）')
    return
  }
  try {
    await api.createRelationType({ name, label: newLabel.value.trim() })
    newName.value = ''
    newLabel.value = ''
    await load()
    emit('refresh')
  } catch (err) {
    alert('新增失败: ' + err.message)
  }
}

/**
 * 提交改标签
 */
async function submitLabel(name) {
  const val = labelValue.value.trim()
  editingLabel.value = ''
  if (!val || val === types.value[name]) return
  try {
    await api.updateRelationType(name, { label: val })
    await load()
    emit('refresh')
  } catch (err) {
    alert('修改标签失败: ' + err.message)
  }
}

/**
 * 提交改名（级联更新关系）
 */
async function submitRename(oldName) {
  const val = renameValue.value.trim()
  renaming.value = ''
  if (!val || val === oldName) return
  try {
    await api.updateRelationType(oldName, { new_name: val })
    await load()
    emit('refresh')
  } catch (err) {
    alert('改名失败: ' + err.message)
  }
}

/**
 * 删除类型
 */
async function removeType(name) {
  const count = usage.value[name] || 0
  if (count > 0) {
    alert(`类型"${name}"正在被 ${count} 条关系使用，无法删除。\n请先删除或修改这些关系的类型。`)
    return
  }
  if (!confirm(`确认删除类型"${name}"？`)) return
  try {
    await api.deleteRelationType(name)
    await load()
    emit('refresh')
  } catch (err) {
    alert('删除失败: ' + err.message)
  }
}

onMounted(() => load())
</script>

<template>
  <div class="modal-overlay" @click.self="emit('close')">
    <div class="modal type-manager">
      <h3>关系类型管理</h3>
      <p class="hint">
        每个类型由「代码」（存储值，建议大写下划线）和「中文标签」（界面显示）组成。
        双击代码可改名，双击标签可修改中文名。
      </p>

      <!-- 类型列表 -->
      <div class="type-list">
        <div v-for="(label, name) in types" :key="name" class="type-item">
          <!-- 代码（可改名） -->
          <template v-if="renaming === name">
            <input
              class="input code-input"
              v-model="renameValue"
              @keyup.enter="submitRename(name)"
              @keyup.esc="renaming = ''"
              @blur="submitRename(name)"
              v-focus
            />
          </template>
          <template v-else>
            <span class="type-code" @dblclick="renaming = name; renameValue = name" title="双击改代码">{{ name }}</span>
          </template>

          <!-- 中文标签（可改） -->
          <template v-if="editingLabel === name">
            <input
              class="input label-input"
              v-model="labelValue"
              @keyup.enter="submitLabel(name)"
              @keyup.esc="editingLabel = ''"
              @blur="submitLabel(name)"
              v-focus
            />
          </template>
          <template v-else>
            <span class="type-label" @dblclick="editingLabel = name; labelValue = label" title="双击改中文名">{{ label }}</span>
          </template>

          <span class="type-usage">{{ usage[name] || 0 }} 关系</span>
          <button
            class="icon-btn"
            :class="{ danger: !(usage[name] > 0) }"
            :title="usage[name] > 0 ? '有关系使用，不可删除' : '删除'"
            @click="removeType(name)"
          >✕</button>
        </div>
        <div v-if="Object.keys(types).length === 0" class="empty-hint">暂无类型</div>
      </div>

      <!-- 新增类型 -->
      <div class="add-row">
        <input class="input code-input" v-model="newName" placeholder="代码（如 MENTORS）" @keyup.enter="addType" />
        <input class="input label-input" v-model="newLabel" placeholder="中文标签（如 指导）" @keyup.enter="addType" />
        <button class="btn btn-primary" @click="addType">添加</button>
      </div>

      <div class="form-actions">
        <button class="btn" @click="emit('close')">关闭</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
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
  margin-bottom: 8px;
  font-size: 16px;
}
.hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 14px;
  line-height: 1.5;
}

.type-list {
  max-height: 320px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: 6px;
  margin-bottom: 16px;
}
.type-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
}
.type-item:last-child {
  border-bottom: none;
}
.type-code {
  flex: 1.4;
  font-size: 12px;
  font-family: 'Consolas', 'Monaco', monospace;
  color: var(--accent);
  cursor: text;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.type-label {
  flex: 1;
  font-size: 13px;
  cursor: text;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.code-input {
  flex: 1.4;
  padding: 2px 8px;
  font-size: 12px;
  font-family: 'Consolas', 'Monaco', monospace;
}
.label-input {
  flex: 1;
  padding: 2px 8px;
  font-size: 13px;
}
.type-usage {
  font-size: 11px;
  color: var(--text-secondary);
  flex-shrink: 0;
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

.add-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
