# 详情面板关闭后左侧列表选中态残留修复复盘

## 1. 问题现象

- **场景**：点击左侧实体列表项（或 3D 节点），右侧弹出实体详情面板，同时左侧列表项高亮选中
- **具体表现**：点击右侧详情面板的 ✕ 关闭按钮后，详情面板消失，但左侧列表项仍保持高亮选中样式
- **影响范围**：前端交互状态一致性，纯视觉/交互体验问题，不影响数据

## 2. 排查过程

| 阶段 | 排查点 | 结论 |
|---|---|---|
| 1 | 左侧选中样式来源 | `EntityPanel.vue` 列表项 `:class="{ selected: entity.id === selectedId }"`，由父组件 `selectedEntityId` prop 驱动 |
| 2 | 关闭按钮行为 | `App.vue` 中 ✕ 按钮只执行 `showDetail = false`，未清空 `selectedEntityId` |

## 3. 根因分析

- **真正原因**：选中状态（`selectedEntityId`）与详情面板显示（`showDetail`）是两份独立状态，
  打开详情时两者同步写入，但关闭时只重置了 `showDetail`，`selectedEntityId` 残留，
  导致左侧列表项持续命中 `selected` 样式类——典型的"状态打开时成对写入、关闭时漏清一半"。
- **涉及模块**：`frontend/src/App.vue`

## 4. 修复方案

**修改文件**：[frontend/src/App.vue](file:///e:/2.MyProjects/MyAgentChat/J.A.R.V.I.S/acefelix/frontend/src/App.vue)

```diff
- <button class="icon-btn" @click="showDetail = false">✕</button>
+ <button class="icon-btn" @click="closeDetail">✕</button>
```

新增 `closeDetail()` 统一收口关闭动作，一次性清空全部关联状态：

```js
function closeDetail() {
  showDetail.value = false
  selectedEntityId.value = ''
  selectedEntity.value = null
}
```

**为什么有效**：选中态与详情面板从此双向同步——打开时成对写入，关闭时成对清空，
左侧列表项因 `selectedId` 变为空串而取消高亮。

## 5. 验证结果

- **编译验证**：`npx vite build --mode development` 通过（exit code 0）
- **手工验证**：点击左侧实体 → 详情弹出且列表高亮 → 点 ✕ → 详情关闭且列表高亮同步消失；
  再次点击同一实体可正常重新打开

## 6. 涉及文件

| 文件 | 改动说明 |
|---|---|
| `frontend/src/App.vue` | 新增 `closeDetail()`，✕ 按钮改为统一收口关闭并清空选中态 |
| `docs/fixlogs/detail-panel-close-selection-fix.md` | 本复盘文档 |

## 7. 经验总结

- **成对状态必须成对管理**：一个状态被"打开动作"写入多个字段时，"关闭动作"必须清空同一组字段，
  最好收口为单个函数（如 `closeDetail`），避免模板里散落多处部分重置。
- **跨组件选中态**：子组件高亮由父组件 prop 驱动时，任何"取消选中"需求都应回到父组件改状态源头，
  而不是在子组件里打补丁。
