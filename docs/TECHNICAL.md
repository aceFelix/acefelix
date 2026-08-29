# AceFelix 知识图谱 · 技术文档

> 版本：0.1.0 ｜ 更新日期：2026-08-23
> 本文面向开发者，详述核心实现机制与关键代码路径。

## 1. 数据模型

### 1.1 graph.json 结构

```json
{
  "version": 17,
  "entities": [
    {
      "id": "1e2b0a7e-...",
      "name": "AceFelix",
      "type": "Person",
      "properties": { "logo": "http://127.0.0.1:8800/uploads/xxx.png" },
      "color": "#ff6b6b",
      "size": null,
      "created_at": "2026-08-20T10:00:00",
      "updated_at": "2026-08-22T09:00:00"
    }
  ],
  "relations": [
    {
      "id": "6f2d...",
      "source": "1e2b0a7e-...",
      "target": "3f5c...",
      "type": "HAS_SKILL",
      "properties": {},
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "types": { "Person": "#ff6b6b", "Skill": "#4ecdc4" },
  "relation_types": { "HAS_SKILL": "掌握技能" }
}
```

- `version`：数据版本号，每次保存 `+1`，乐观锁依据
- `types` / `relation_types`：动态类型表（名称 → 颜色 / 中文标签）
- 实体 `color` / `size` 为可空的自定义外观字段，`null` 时用类型默认色 / 按连接数自动计算
- 实体的 `properties` 与关系的 `properties` 为任意 JSON 字典，**图片属性**即值为 `http(s)` 或 `/uploads/` 开头的键值

### 1.2 内存模型

- 使用 `networkx.DiGraph()` 存储图结构（有向图）
- 同时维护 `_entities: {id: Entity}` 与 `_relations: {id: Relation}` 两本字典，作为**唯一事实源**
- 图节点/边只做查询加速与算法支撑，CRUD 永远以字典为准再同步图结构

```python
# app/knowledge_graph.py
self.graph = nx.DiGraph()
self._entities: Dict[str, Entity] = {}
self._relations: Dict[str, Relation] = {}
```

## 2. 持久化机制

### 2.1 原子写入（`save()`）

```
加写锁 → 备份当前文件 → version += 1 → 写 .json.tmp 临时文件
  → fsync 落盘 → os.replace(tmp, graph.json) 原子替换
  → 若环境拦截 rename（PermissionError）→ 降级直接写主文件
```

- 使用写锁 `threading.Lock()` 串行化并发保存。FastAPI 的 sync handler 运行在线程池中，多个请求可能同时触发 save。
- `os.replace` 在同一文件系统上是原子操作，保证任意时刻读到的是完整文件。
- 降级路径保留：某些安全组件会拦截 `rename` 类系统调用（本项目开发环境即如此），此时回退为直接写入，避免服务不可用。

### 2.2 滚动备份（`_backup()`）

- 每次保存前将当前 `graph.json` 复制到 `data/backups/graph_{YYYYMMDD_HHMMSS}.json`
- 同秒内多次保存使用相同文件名（`shutil.copy2` 覆盖），避免备份爆炸
- 滚动清理：按文件名排序保留最近 **20** 份
- 备份失败（如文件被占用）不阻塞主流程——备份是尽力而为

### 2.3 乐观锁

前端在打开编辑表单时记录 `graphVersion`（来自 `/api/meta` 的 `version`）。提交更新时携带 `if_version`：

```python
# api.py update_entity
if body.if_version is not None and body.if_version != kg.version:
    raise HTTPException(status_code=409, detail="数据已被其他页面或程序修改，请刷新后重试")
```

- 匹配 → 正常更新并 `version += 1`
- 不匹配 → 返回 **409**，前端提示刷新
- 适用于多标签页、多设备同时编辑的冲突检测

## 3. 动态类型系统

实体类型与关系类型不再硬编码，而是存储在 `graph.json` 的 `types` / `relation_types` 字段中。

### 3.1 实体类型

| 操作 | 行为 |
|---|---|
| 新增 | 名称去空格、查重，保存后即可在创建实体时选用 |
| 改色 | 直接改 `types[name]` |
| 改名 | `types` 键迁移 + **级联更新**所有实体的 `type` 字段 |
| 删除 | **fail-closed**：有实体在使用时拒绝删除 |

### 3.2 关系类型

与实体类型对称，区别是值为**中文标签**而非颜色；改名级联更新关系与图边。

```python
# 重命名关系类型：同步更新内存关系与图边
for _, _, edge_data in self.graph.edges(data=True):
    if edge_data.get("type") == old_name:
        edge_data["type"] = new_name
```

## 4. 图查询算法

所有查询基于 `self.graph`（NetworkX 有向图）。

### 4.1 邻居子图 `get_neighbors`

使用 `nx.ego_graph(graph.to_undirected(), node, radius=degree)` 获取邻域子图。前端「单击 = 1 跳」「聚焦 = 2 跳」。

### 4.2 路径查询 `find_paths`

**无向视角**（A→B 与 B→A 视为同一条边），按跳数从少到多搜索：

```python
for hops in range(1, max_hops + 1):
    for node_path in nx.all_simple_paths(undirected, source, target, cutoff=hops):
        if len(node_path) - 1 != hops:
            continue  # 只收当前跳数，避免重复
```

- `max_hops` 钳制在 1~4，防止简单路径组合爆炸
- 一对实体间可能有多条关系，通过 `frozenset((source, target))` 归并
- 结果附 `node_names` / `relation_types`，前端直接渲染文本

### 4.3 共同邻居 `common_neighbors`

对无向图求 `neighbors(a) ∩ neighbors(b)`。

### 4.4 搜索 `search`

名称 + 属性值的字符串包含匹配（大小写不敏感），数据量小时足够；数据量增大后建议换倒排索引。

## 5. 前端 3D 渲染

### 5.1 力导向图

基于 `3d-force-graph`（内部使用 d3-force-3d）：

- `forceCollide` 防节点重叠
- 节点半径 = 视觉半径（影响相机距离），力导向质量独立计算，避免"视觉大球互相排斥把图撑爆"
- 布局参数（斥力、连接距离、冷却轮数）集中在 `config/graph.config.js`
- 开局动画节奏：“先自由展开、最后一口气收回”——力引擎运行期间相机固定在 `camera.initialZ`，
  节点自由散开；引擎停止后由 `onEngineStop` 一次性收尾取景，动画时长由 `camera.fitDuration` 控制。
  首屏等待总时长 ≈ `cooldownTicks` ÷ 60fps
- 交互优先：监听轨道控制器 `start` 事件，用户一旦旋转/缩放/平移，收尾取景即让位不夺视角；
  布局期间相机不自动干预，用户可自由操作画面（拖拽节点不受该标记影响）

### 5.2 宇宙主题

布局：3D 画布为**全屏背景层**（App.vue 中 `Graph3D` 绝对定位铺满 `inset: 0`），
导航栏/左右侧栏/底栏用 `--bg-panel` 半透明色 + `backdrop-filter: blur(16px)` 悬浮其上，
毛玻璃直接透出星空。面板透明度由 `graph.config.js` 的 `ui.panelOpacity` 控制（`main.js`
启动时注入 `--panel-alpha` CSS 变量，保存配置后自动重载生效）。`app-layout` 设
`pointer-events: none` 让布局层不拦鼠标，面板与 3D 包装器各自 `pointer-events: auto` 恢复交互。

场景由 `setupCosmos(scene)` 搭建：

| 天体 | 实现 |
|---|---|
| 星球节点 | Canvas 程序化生成真实行星地表纹理：周期无缝值噪声 + fBm 分形，按颜色种子分派两种风格——气态巨行星（纬度云带 + 湍流扭曲 + 细流纹 + 风暴暗斑亮环）与类地行星（海陆高程 + 地形明暗 + 环形山 + 极地冰盖），叠加横向拉丝流云；`MeshStandardMaterial`（纹理复用为 bumpMap，气态/类地区分粗糙度）+ BackSide Fresnel 大气散射壳 + 外层光晕 Sprite；行星缓慢自转（`planetSpin`）；同色节点共享纹理缓存 |
| 星空 | 两层粒子球壳（小星 + 亮星），`sizeAttenuation: false` 保持屏幕恒定大小 |
| 银河 | 中心核球（发黄白）+ 4 条对数螺旋旋臂（蓝白/暖白渐变），整体倾斜，`vertexColors + AdditiveBlending` |
| 黑洞 | 事件视界黑球 + 双层吸积盘（Canvas 径向渐变 + 湍流纹理）+ 引力透镜光环（TubeGeometry）+ 螺旋吸积粒子流 + 辉光 |
| 星云 | `getNebulaTexture` 生成絮状云雾（随机 blob + HSL 偏移 + 圆形边缘遮罩），Sprite + AdditiveBlending |

### 5.3 交互模式

- **单击节点**：高亮一跳直接关系，打开详情面板
- **聚焦**：两跳深挖
- **路径**：依次点两个节点，调 `/api/graph/paths` 高亮路径
- **重置**：清空高亮
- 高亮时通过 `nodeColor` / `linkColor` 返回新函数引用强制 Kapsule 重绘（修复过函数引用相同导致的重绘失效）

### 5.4 面板列表排序

实体/关系列表统一按**名称首字母升序**展示，排序规则收口在 `src/utils/sort.js` 的 `nameCompare`：

- `localeCompare(locale: 'zh-Hans-CN-u-co-pinyin')`：中文按拼音序，英文不区分大小写，数字自然序（`numeric: true`）
- 实体面板：按实体名排序；关系面板：先比源实体名、同名再比目标实体名
- 类型列表同样按首字母升序：App.vue `loadMeta` 对实体/关系类型数组排序（供筛选与表单下拉框），
  两个类型管理弹窗（TypeManager / RelationTypeManager）在 `computed` 内对类型条目排序后渲染
- 排序发生在 `computed` 内且先 `slice()`，不改动响应式源数组；类型过滤/搜索后仍保持有序

### 5.5 3D 模块拆分（单文件 ≤800 行）

`Graph3D.vue` 曾达 1500+ 行，按代码结构规则拆为「渲染骨架 + 4 个独立模块」，行为不变：

| 模块 | 职责 |
|---|---|
| `components/Graph3D.vue` | 渲染骨架：数据加载、图实例初始化、高亮/路径交互编排、模板与样式 |
| `utils/planetTexture.js` | 行星纹理（种子噪声 + fBm、气态/类地两种风格）与大气散射壳，同色节点共享纹理缓存 |
| `utils/cosmos.js` | 宇宙场景搭建 `setupCosmos(scene)`：灯光/星空/银河/星云/黑洞，含光晕/吸积盘/星云贴图生成 |
| `utils/graphCamera.js` | 相机控制：全图包围盒自适应取景 `autoFitCamera`（动画时长可传参，缺省用 `camera.fitDuration`） + 单节点聚焦 `focusCamera`（纯函数，图实例由调用方传入） |
| `utils/labelLayer.js` | 节点 HTML 标签覆盖层：rAF 逐帧投影定位，相机/高亮/点击回调由组件注入，循环内顺带驱动行星自转 |

拆分原则：工具模块不依赖组件内部状态（依赖倒置，回调/参数注入），可独立测试与复用。

## 6. 图片上传

### 6.1 后端

```python
@app.post("/api/upload")
def upload_file(file: UploadFile = File(...)):
    # 校验 MIME ∈ {png, jpeg, gif, webp, svg}
    filename = f"{uuid.uuid4().hex}{ext}"     # 唯一文件名
    with save_path.open("wb") as f:
        f.write(file.file.read())
    return {"url": f"/uploads/{filename}"}
```

- 图片保存到 `backend/uploads/`，通过 `app.mount("/uploads", StaticFiles(...))` 提供静态访问
- 文件名用 UUID，天然防冲突、防路径穿越

### 6.2 前端

- `api.uploadFile(file)` 使用 `FormData` 上传（不能走通用 JSON request）
- 编辑弹窗「图片属性」区：URL 粘贴添加 / 本地文件上传
- 详情面板按 `utils/property.js` 的 `isImageProp(key, val)` 判断属性值：图片渲染为 `<img>`，普通网站链接（如 `website`）渲染为可点击 `<a>`；识别规则 = `/uploads/` 目录 ∨ 图片语义键名（image/avatar/logo…）∨ 图片扩展名兜底
- 存储的是 URL 字符串（而非 base64），避免撑爆 `graph.json`

## 7. MCP Server（Agent 接入）

### 7.1 运行形态

`mcp_server.py` 基于官方 mcp SDK 的 **FastMCP**，以 **stdio transport** 运行：
客户端（jarvis 等）在需要时拉起子进程，通过 stdin/stdout 的 JSON-RPC 通信。
与 `api.py`（HTTP REST）**共享同一个 `KnowledgeGraph` 引擎与 `data/graph.json`**。

```python
# mcp_server.py
kg = KnowledgeGraph(str(DATA_PATH))   # 与 api.py 相同的 data 文件
mcp = FastMCP("acefelix-knowledge", instructions=...)
@mcp.tool()
def get_profile(max_items: int = 15) -> str:
    ...
if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### 7.2 工具清单

| 类别 | 工具 | 说明 |
|---|---|---|
| 画像 | `get_profile` | 以 Person 实体为中心聚合一跳关联，输出紧凑画像 |
| 查询 | `search_entity` / `get_entity` / `list_entities` | 实体搜索与详情 |
| 图查询 | `get_neighbors` / `find_paths` / `common_neighbors` | 邻居/路径/共同邻居 |
| 元数据 | `get_stats` / `list_types` / `list_relation_types` | 统计与类型表 |
| 写入 | `add_entity` / `add_relation` | 新增实体/关系，复用引擎的乐观锁与备份 |
| 抽取 | `ingest_text` | 文本交给第 8 节抽取管线（内置防噪闸与查重），`dry_run` 预览确认后写入；jarvis `/memory sync` 画像回写走此工具 |

### 7.3 权限模型

MCP 协议层面工具**没有只读/写入标记**，权限由客户端侧控制：

- jarvis 的 `MCPToolWrapper.check_permissions` 默认返回 `ASK`（外部进程调用需用户确认）
- 本 server 的写工具（`add_entity` / `add_relation`）在 jarvis 侧自然走"需确认"流程
- 只读工具（查询类）不修改数据，客户端可放行

### 7.4 多进程并发说明

`api.py` 与 `mcp_server.py` 是**两个独立进程**，可能同时读写 `graph.json`：

- `KnowledgeGraph._write_lock` 是**进程内**锁，无法跨进程互斥
- 跨进程安全由**原子写**（`os.replace`，写坏不丢旧数据）+ **乐观锁**（写前校验 version）兜底
- 个人单用户场景下冲突概率低；若需更强一致性，后续可在存储层替换时统一处理

## 8. 知识抽取管线（GraphRAG 自动抽取）

### 8.1 管线结构

`ingest.py` 实现「文本 → 三元组 → 查重 → 写入」管线，与 `api.py` 共享同一个
`KnowledgeGraph` 引擎，写入复用乐观锁与自动备份（可回滚）：

```
输入（文本 / .txt / .md / .json 会话文件）
  → 闸④ 信息密度预检（过短/纯疑问句直接拒绝，不调 LLM）
  → LLM 抽取（OpenAI 兼容协议，标准库 urllib，零新依赖）
  → 闸② 价值预判（寒暄/情绪/琐事 → 空三元组，零写入）
  → 闸③ 类型白名单（实体/关系类型必须命中现有类型表，否则进待确认清单）
  → 实体/关系查重（名称归一化匹配 + (源,目标,类型) 指纹）
  → 写入 KnowledgeGraph（dry_run 时只返回预览）
```

### 8.2 五道防噪闸（闲聊不入图谱）

| 闸 | 机制 | 实现位置 |
|---|---|---|
| ① 入口闸 | 不挂聊天实时链路，仅 REST/MCP/批量脚本显式触发 | 架构约束 |
| ② 价值判断闸 | 抽取 prompt 内置预判 + 负例示范，无知识含量返回空 | `build_system_prompt` |
| ③ 类型白名单闸 | 类型不在表内进 `pending_review`，不写入 | `ingest_text` |
| ④ 信息密度闸 | 少于 12 字符/纯疑问句直接拒绝 | `density_check` |
| ⑤ 人工闸 | `dry_run` 预览 + 写入前自动备份可回滚 | API `dry_run` 参数 |

### 8.3 抽取模型配置

配置优先级：**环境变量 > `backend/config/ingest.toml` > 内置默认值**（模板见 `config/ingest.toml.example`，
真实配置含密钥已被 .gitignore 排除）：

| 字段 | 默认值 | 说明 |
|---|---|---|
| `base_url` | DashScope 兼容端点 | OpenAI 兼容协议 |
| `model` | `qwen-flash` | 独立便宜模型，与主 LLM 解耦 |
| `api_key` | 留空 | 明文密钥（不建议），留空走环境变量 |
| `api_key_env` | 留空 | 指定从哪个环境变量读密钥（如 `DEEPSEEK_API_KEY`）；再留空则依次回退 `DASHSCOPE_API_KEY` / `OPENAI_API_KEY` |
| `max_chars` | 8000 | 送入 LLM 的文本上限，超长截断 |

环境变量 `INGEST_BASE_URL` / `INGEST_MODEL` / `INGEST_API_KEY` 可临时覆盖。
厂商欠费/不可用时只需改 `base_url` / `model` / `api_key_env` 即可切换（如切 DeepSeek）；
HTTP 错误会在接口 `detail` 中透出厂商返回的具体原因（欠费/模型不存在/限流）。
实体写入时自动附带 `properties.source`（text / file）溯源。

### 8.4 对外接口

| 接口 | 说明 |
|---|---|
| `POST /api/ingest` | JSON 文本抽取（`dry_run` 预览，`as_session` 按会话 JSON 解析） |
| `POST /api/ingest/file` | 上传 .txt/.md/.json 文件抽取（上限 2MB，UTF-8） |

返回统一结果结构：`created_entities` / `created_relations` /
`skipped_duplicate_*`（查重）/ `pending_review`（待人工裁决）/
`skipped_relations`（含拒绝原因）/ `gate`（闸门判定）。
单元测试见 `tests/test_ingest.py`（LLM 全 mock），含闲聊零写入负例。

## 9. 已知限制

| 限制 | 说明 |
|---|---|
| 全内存图 | NetworkX 图在内存中，数据量大（万级节点）时内存与性能受限 |
| 弱并发 | 乐观锁适合个人单写场景，不支持事务级并发 |
| 搜索为线性扫描 | `search()` 每次全量遍历 |
| 图片无回收 | 删除实体的图片属性不会删除 `uploads/` 里的文件 |
| 属性整体替换 | 更新实体/关系时 `properties` 为整体替换，非深合并 |

## 10. 演进路线

按数据量与并发增长，优先级建议：

1. **存储层替换**：JSON → SQLite（`KnowledgeGraph` 内部实现替换，接口不变）
2. **图数据库**：Kùzu（嵌入式，列式图存储）/ Neo4j（服务化），当路径查询变慢时
3. **搜索升级**：SQLite FTS5 或 PostgreSQL 全文索引替代线性扫描；或 embedding 语义检索（P3）
4. ~~**自动抽取**~~：✅ 已完成（P1，见第 8 节）；MCP `ingest_text` 工具已补（P2，jarvis 画像回写链路）；查重后续可引入 embedding 相似度（依赖 P3）
5. **图片管理**：上传文件纳入备份/迁移范围，支持删除回收
