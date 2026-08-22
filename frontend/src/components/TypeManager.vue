<!--
  实体类型管理弹窗
  提供类型的查看、新增、改色、改名、删除功能。
  删除保护：有实体正在使用的类型不可删（后端校验）。
  @author aceFelix
-->
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const emit = defineEmits(['close', 'refresh'])

// 预设颜色板
const PRESET_COLORS = [
  '#ff6b6b', '#4ecdc4', '#45b7d1', '#f9ca24', '#a55eea',
  '#fd79a8', '#6c5ce7', '#00b894', '#e17055', '#fdcb6e',
  '#ff9ff3', '#54a0ff', '#01a3a4', '#f368e0', '#eb4d4b',
]

const types = ref({}) // name -> color
const usage = ref({}) // name -> 实体数
// 新增表单
const newName = ref('')
const newColor = ref(PRESET_COLORS[1])
// 改名状态
const renaming = ref('') // 正在改名的类型名
const renameValue = ref('')

// 自定义指令：输入框自动聚焦（script setup 中 vFocus 即模板里的 v-focus）
const vFocus = { mounted: (el) => el.focus() }

/**
 * 加载类型表与每个类型的实体用量
 */
async function load() {
  try {
    const [t, entities] = await Promise.all([api.getTypes(), api.getEntities()])
    types.value = t
    const counts = {}
    entities.forEach((e) => {
      counts[e.type] = (counts[e.type] || 0) + 1
    })
    usage.value = counts
  } catch (err) {
    alert('加载类型失败: ' + err.message)
  }
}

/**
 * 新增类型
 */
async function addType() {
  const name = newName.value.trim()
  if (!name) {
    alert('请输入类型名称')
    return
  }
  try {
    await api.createType({ name, color: newColor.value })
    newName.value = ''
    await load()
    emit('refresh')
  } catch (err) {
    alert('新增失败: ' + err.message)
  }
}

/**
 * 修改类型颜色
 */
async function changeColor(name, color) {
  try {
    await api.updateType(name, { color })
    await load()
    emit('refresh')
  } catch (err) {
    alert('修改颜色失败: ' + err.message)
  }
}

/**
 * 提交改名
 */
async function submitRename(oldName) {
  const newNameVal = renameValue.value.trim()
  renaming.value = ''
  if (!newNameVal || newNameVal === oldName) return
  try {
    await api.updateType(oldName, { new_name: newNameVal })
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
    alert(`类型"${name}"正在被 ${count} 个实体使用，无法删除。\n请先删除或修改这些实体的类型。`)
    return
  }
  if (!confirm(`确认删除类型"${name}"？`)) return
  try {
    await api.deleteType(name)
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
      <h3>实体类型管理</h3>

      <!-- 类型列表 -->
      <div class="type-list">
        <div v-for="(color, name) in types" :key="name" class="type-item">
          <label class="type-color" :style="{ background: color }" :title="'修改颜色 ' + color">
            <input type="color" :value="color" @input="changeColor(name, $event.target.value)" />
          </label>
          <template v-if="renaming === name">
            <input
              class="input rename-input"
              v-model="renameValue"
              @keyup.enter="submitRename(name)"
              @keyup.esc="renaming = ''"
              @blur="submitRename(name)"
              v-focus
            />
          </template>
          <template v-else>
            <span class="type-name" @dblclick="renaming = name; renameValue = name" title="双击改名">{{ name }}</span>
          </template>
          <span class="type-usage">{{ usage[name] || 0 }} 实体</span>
          <button
            class="icon-btn"
            :class="{ danger: !(usage[name] > 0) }"
            :title="usage[name] > 0 ? '有实体使用，不可删除' : '删除'"
            @click="removeType(name)"
          >✕</button>
        </div>
        <div v-if="Object.keys(types).length === 0" class="empty-hint">暂无类型</div>
      </div>

      <!-- 新增类型 -->
      <div class="add-section">
        <div class="add-row-top">
          <input class="input name-input" v-model="newName" placeholder="新类型名称" @keyup.enter="addType" />
          <button class="btn btn-primary" @click="addType">添加</button>
        </div>
        <div class="mini-colors">
          <div
            v-for="c in PRESET_COLORS"
            :key="c"
            class="mini-color"
            :class="{ active: newColor === c }"
            :style="{ background: c }"
            @click="newColor = c"
          ></div>
        </div>
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
  width: 440px;
  max-width: 90vw;
}
.modal h3 {
  margin-bottom: 16px;
  font-size: 16px;
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
.type-color {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  cursor: pointer;
  flex-shrink: 0;
  position: relative;
  overflow: hidden;
}
.type-color input[type='color'] {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}
.type-name {
  flex: 1;
  font-size: 13px;
  cursor: text;
}
.rename-input {
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

.add-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.add-row-top {
  display: flex;
  align-items: center;
  gap: 10px;
}
.name-input {
  flex: 1;
  min-width: 0;
}
.mini-colors {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 6px;
}
.mini-color {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  cursor: pointer;
  border: 2px solid transparent;
  transition: transform 0.12s;
}
.mini-color:hover {
  transform: scale(1.2);
}
.mini-color.active {
  border-color: #fff;
  transform: scale(1.2);
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
