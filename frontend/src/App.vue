<!--
  AceFelix 个人知识图谱主界面
  布局：顶部搜索栏 + 左侧实体面板 + 中央 3D 可视化 + 右侧关系面板 + 底部统计
  @author aceFelix
-->
<script setup>
import { ref, onMounted } from 'vue'
import { api } from './api'
import Graph3D from './components/Graph3D.vue'
import EntityPanel from './components/EntityPanel.vue'
import RelationPanel from './components/RelationPanel.vue'
import StatsBar from './components/StatsBar.vue'

// 元数据
const entityTypes = ref([])
const relationTypes = ref([])
const relationTypeLabels = ref({}) // 关系类型代码 -> 中文标签
const entityColors = ref({})
const graphVersion = ref(1) // 数据版本号（乐观锁）

// 数据
const entities = ref([])

// 交互状态
const selectedEntityId = ref('')
const selectedEntity = ref(null)
const searchQuery = ref('')
const activeTab = ref('entity') // 'entity' | 'relation'
const showDetail = ref(false)

const graphRef = ref()
const entityPanelRef = ref()
const relationPanelRef = ref()
const statsRef = ref()

/**
 * 加载元数据（实体类型/关系类型/颜色映射）
 * 类型管理操作后需重新加载，保证下拉框与 3D 着色同步
 */
async function loadMeta() {
  const meta = await api.getMeta()
  entityTypes.value = meta.entity_types
  relationTypes.value = meta.relation_types
  relationTypeLabels.value = meta.relation_type_labels || {}
  entityColors.value = meta.entity_colors
  graphVersion.value = meta.version || 1
}

/**
 * 初始化：加载元数据和实体列表
 */
async function init() {
  try {
    await loadMeta()
    await loadEntities()
  } catch (err) {
    console.error('初始化失败:', err)
    alert('无法连接后端服务，请确保后端已启动（python api.py）')
  }
}

/**
 * 加载实体列表
 */
async function loadEntities() {
  entities.value = await api.getEntities()
}

/**
 * 处理 3D 图节点点击
 */
async function onSelectEntity(id) {
  selectedEntityId.value = id
  try {
    const entity = await api.getEntity(id)
    selectedEntity.value = entity
    showDetail.value = true
  } catch (err) {
    console.error(err)
  }
}

/**
 * 刷新所有数据（含元数据，覆盖类型变更场景）
 */
async function refreshAll() {
  await loadMeta()
  await loadEntities()
  graphRef.value?.loadGraph()
  statsRef.value?.loadStats()
}

/**
 * 执行搜索：调后端搜索接口，命中则聚焦第一个结果并打开详情
 */
async function doSearch() {
  if (!searchQuery.value) return
  try {
    const results = await api.search(searchQuery.value)
    if (results.length === 0) {
      alert(`未找到匹配"${searchQuery.value}"的实体`)
      return
    }
    // 聚焦第一个结果并打开详情面板
    graphRef.value?.focusNode(results[0].id)
    await onSelectEntity(results[0].id)
  } catch (err) {
    console.error('搜索失败:', err)
  }
}

onMounted(() => init())
</script>

<template>
  <div class="app-layout">
    <!-- 顶部搜索栏 -->
    <header class="topbar">
      <div class="logo">
        <span class="logo-icon">◆</span>
        <span class="logo-text">AceFelix 知识图谱</span>
      </div>
      <div class="search-box">
        <input
          class="input search-input"
          v-model="searchQuery"
          placeholder="搜索实体名称..."
          @keyup.enter="doSearch"
        />
      </div>
    </header>

    <!-- 主体区域 -->
    <div class="main-body">
      <!-- 左侧面板 -->
      <aside class="sidebar left">
        <div class="tab-bar">
          <button
            class="tab"
            :class="{ active: activeTab === 'entity' }"
            @click="activeTab = 'entity'"
          >实体 ({{ entities.length }})</button>
          <button
            class="tab"
            :class="{ active: activeTab === 'relation' }"
            @click="activeTab = 'relation'"
          >关系</button>
        </div>
        <div class="tab-content">
          <EntityPanel
            v-show="activeTab === 'entity'"
            ref="entityPanelRef"
            :entity-types="entityTypes"
            :entity-colors="entityColors"
            :selected-id="selectedEntityId"
            :graph-version="graphVersion"
            @select="onSelectEntity"
            @refresh="refreshAll"
          />
          <RelationPanel
            v-show="activeTab === 'relation'"
            ref="relationPanelRef"
            :relation-types="relationTypes"
            :relation-type-labels="relationTypeLabels"
            :entities="entities"
            :graph-version="graphVersion"
            @refresh="refreshAll"
          />
        </div>
      </aside>

      <!-- 中央 3D 可视化 -->
      <main class="graph-area">
        <Graph3D
          ref="graphRef"
          :highlight-name="searchQuery"
          @select-entity="onSelectEntity"
        />
      </main>

      <!-- 右侧详情面板 -->
      <aside class="sidebar right" v-if="showDetail && selectedEntity">
        <div class="detail-panel">
          <div class="detail-header">
            <span class="entity-dot" :style="{ background: selectedEntity.color || entityColors[selectedEntity.type] || '#888' }"></span>
            <div class="detail-title">
              <h2>{{ selectedEntity.name }}</h2>
              <span class="tag" :style="{ background: (selectedEntity.color || entityColors[selectedEntity.type] || '#888') + '33', color: selectedEntity.color || entityColors[selectedEntity.type] || '#888' }">{{ selectedEntity.type }}</span>
            </div>
            <button class="icon-btn" @click="showDetail = false">✕</button>
          </div>
          <div class="detail-body" v-if="selectedEntity.properties">
            <div class="prop-section">
              <h4>属性</h4>
              <div class="prop-list">
                <div class="prop-item" v-for="(val, key) in selectedEntity.properties" :key="key">
                  <span class="prop-key">{{ key }}</span>
                  <span class="prop-val">{{ val }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </div>

    <!-- 底部统计栏 -->
    <footer>
      <StatsBar ref="statsRef" />
    </footer>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

/* 顶部栏 */
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 52px;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border);
  z-index: 10;
}
.logo {
  display: flex;
  align-items: center;
  gap: 8px;
}
.logo-icon {
  color: var(--accent);
  font-size: 20px;
}
.logo-text {
  font-size: 15px;
  font-weight: 600;
}
.search-box {
  width: 320px;
}
.search-input {
  width: 100%;
}

/* 主体 */
.main-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 侧边栏 */
.sidebar {
  width: 300px;
  background: var(--bg-panel);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.sidebar.right {
  border-right: none;
  border-left: 1px solid var(--border);
}

/* Tab */
.tab-bar {
  display: flex;
  border-bottom: 1px solid var(--border);
}
.tab {
  flex: 1;
  padding: 10px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
  border-bottom: 2px solid transparent;
}
.tab.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}
.tab-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 图谱区域 */
.graph-area {
  flex: 1;
  position: relative;
  overflow: hidden;
  min-width: 0;
}

/* 详情面板 */
.detail-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.detail-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px;
  border-bottom: 1px solid var(--border);
}
.entity-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}
.detail-title {
  flex: 1;
}
.detail-title h2 {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 4px;
}
.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
.prop-section h4 {
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
  margin-bottom: 8px;
}
.prop-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.prop-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 8px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 4px;
  font-size: 13px;
}
.prop-key {
  color: var(--text-secondary);
}
.prop-val {
  color: var(--text-primary);
  font-weight: 500;
}
.icon-btn {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 14px;
  padding: 4px 8px;
  border-radius: 4px;
}
.icon-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
}

footer {
  border-top: 1px solid var(--border);
}
</style>
