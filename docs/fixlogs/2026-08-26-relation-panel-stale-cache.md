# 修复复盘：删除实体后关系面板残留 "?" 悬空关系

- 日期：2026-08-26
- 作者：aceFelix
- 影响范围：前端 `RelationPanel.vue`（关系管理面板）

## 现象

在实体面板删除实体后，切换到"关系"标签页，仍能看到指向该实体的关系条目，
实体名位置显示为占位符 `?`（如 `? 掌握技能 → Python`）。

## 排查过程

1. 检查后端数据文件 `data/graph.json`：0 条悬空关系 —— 数据干净
2. 检查后端 `delete_entity`（knowledge_graph.py）：已实现级联删除关联关系 —— 逻辑正确
3. 通过 `GET /api/relations` + `GET /api/entities` 交叉比对：0 条悬空 —— 接口正确
4. 检查前端：`?` 来自 `RelationPanel.vue` 模板的 `entityMap[rel.source] || '?'` 兜底渲染

## 根因

**前端本地缓存未同步**，非数据问题：

- `RelationPanel` 在 App.vue 中用 `v-show` 保活（切标签不销毁），
  其 `relations` 列表是组件挂载时加载的一次性快照
- 删除实体走 `EntityPanel.removeEntity` → `emit('refresh')` → App.vue `refreshAll()`，
  `refreshAll` 只刷新了元数据、实体列表、3D 图和统计，**从未通知关系面板重新加载**
- 于是关系面板持有删除前的旧关系列表，而 `entityMap`（来自新实体列表）
  已查不到被删实体的名字 → 渲染兜底为 `?`

## 修复方案

`RelationPanel.vue` 监听 `graphVersion` prop（乐观锁数据版本号）：
任何写操作后 `refreshAll` 都会拉取新版本号，版本号变化即触发 `loadRelations()` 重新加载。

该方案同时覆盖所有写路径（删实体/删关系/新增/编辑），且与组件已有的
`graphVersion` prop 语义一致，无需改动 App.vue。

## 验证

- `npx vite build --mode development` 编译通过（exit 0）
- 人工验证清单：
  1. 新建一个测试实体 + 一条关联关系
  2. 切到"关系"标签确认关系可见
  3. 回到"实体"标签删除该实体
  4. 再切到"关系"标签 —— 关联关系应已消失，无 `?` 占位

## 经验教训

`v-show` 保活组件持有独立数据快照时，必须订阅全局数据版本变化（本项目为
`graphVersion` 乐观锁版本号），否则跨面板写操作会导致列表过期。
