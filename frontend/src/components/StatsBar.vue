<!--
  统计栏组件
  展示图谱的实体数、关系数、类型分布等统计信息。
  @author aceFelix
-->
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const stats = ref({ total_entities: 0, total_relations: 0, entity_types: {}, relation_types: {} })
const entityColors = ref({})

/**
 * 加载统计信息
 */
async function loadStats() {
  try {
    const [s, meta] = await Promise.all([api.getStats(), api.getMeta()])
    stats.value = s
    entityColors.value = meta.entity_colors
  } catch (err) {
    console.error('加载统计失败:', err)
  }
}

onMounted(() => loadStats())
defineExpose({ loadStats })
</script>

<template>
  <div class="stats-bar">
    <div class="stat-item">
      <span class="stat-value">{{ stats.total_entities }}</span>
      <span class="stat-label">实体</span>
    </div>
    <div class="stat-item">
      <span class="stat-value">{{ stats.total_relations }}</span>
      <span class="stat-label">关系</span>
    </div>
    <div class="stat-divider"></div>
    <div class="type-breakdown">
      <div
        v-for="(count, type) in stats.entity_types"
        :key="type"
        class="type-chip"
        :style="{ borderColor: entityColors[type] || '#888' }"
      >
        <span class="type-dot" :style="{ background: entityColors[type] || '#888' }"></span>
        <span class="type-name">{{ type }}</span>
        <span class="type-count">{{ count }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stats-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 16px;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
}
.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--accent);
}
.stat-label {
  font-size: 10px;
  color: var(--text-secondary);
  text-transform: uppercase;
}
.stat-divider {
  width: 1px;
  height: 28px;
  background: var(--border);
}
.type-breakdown {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.type-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border: 1px solid;
  border-radius: 12px;
  font-size: 11px;
}
.type-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.type-name {
  color: var(--text-secondary);
}
.type-count {
  font-weight: 600;
  color: var(--text-primary);
}
</style>
