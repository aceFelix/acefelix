# AceFelix 知识图谱 · 部署与运维

> 版本：0.1.0 ｜ 更新日期：2026-08-22

## 1. 环境要求

| 组件 | 要求 | 说明 |
|---|---|---|
| Python | 3.9+（开发环境 3.13） | 后端运行 |
| Node.js | 16+ | 前端构建 |
| npm | 8+ | 前端依赖管理 |
| 操作系统 | Windows / macOS / Linux | 本项目在 Windows 开发验证 |

## 2. 快速启动（开发模式）

### 2.1 后端

```bash
cd backend
python -m pip install -r requirements.txt   # 首次
python seed.py                               # 首次初始化示例数据（已有数据跳过）
python api.py                                # 或：python -m uvicorn api:app --reload --port 8800
```

服务监听 `http://127.0.0.1:8800`。

> **重要（Windows + 本机多 Python 环境）**：若使用 `python -m uvicorn`，请先确认 `python` 指向正确解释器（`python --version`），并显式设置 `PYTHONPATH` 为项目根目录，避免加载到其他工具的 shim 崩溃：
>
> ```bash
> cd backend
> PYTHONPATH=<项目根目录> python -m uvicorn api:app --reload --host 127.0.0.1 --port 8800
> ```

### 2.2 前端

```bash
cd frontend
npm install          # 首次
npm run dev          # 启动 Vite，监听 http://127.0.0.1:5173
```

浏览器访问 **http://127.0.0.1:5173/**。

> `npm run dev` 已固定 `--host 127.0.0.1`。Windows 上 `localhost` 常解析到 IPv6 `[::1]`，Vite 若只绑定 IPv6，用 IPv4 访问会失败。

### 2.3 Windows 一键启动

项目根目录提供 `start.bat`，双击即可同时拉起前后端。

---

## 3. 生产部署

### 3.1 构建前端

```bash
cd frontend
npm run build        # 产物输出到 frontend/dist/
```

### 3.2 部署方式 A：Nginx + Uvicorn

**后端（多 worker）**

```bash
cd backend
PYTHONPATH=<项目根目录> python -m uvicorn api:app --host 0.0.0.0 --port 8800 --workers 2
```

**Nginx 反向代理**

```nginx
server {
    listen 80;
    server_name kg.example.com;

    # 前端静态资源
    root /path/to/acefelix/frontend/dist;
    index index.html;
    location / { try_files $uri $uri/ /index.html; }

    # 后端 API
    location /api/  { proxy_pass http://127.0.0.1:8800; }
    location /uploads/ { proxy_pass http://127.0.0.1:8800; }
}
```

### 3.3 部署方式 B：同机单进程（个人使用）

直接把 `frontend/dist` 由 FastAPI 挂载托管（若需）：

```python
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="../frontend/dist", html=True), name="static")
```

> 注意：`/uploads` 与 `/api` 路由需先注册，静态 `Mount("/")` 放最后。

---

## 4. 数据管理

### 4.1 数据文件

| 文件 | 内容 | 备份建议 |
|---|---|---|
| `backend/data/graph.json` | 主数据（实体/关系/类型/版本） | **必须备份** |
| `backend/data/backups/` | 每次保存前的滚动备份（保留 20 份） | 随主数据一起 |
| `backend/uploads/` | 上传的图片文件 | 图片属性引用它们，**需一并备份** |
| `backend/api.log` | 运行日志 | 按需 |

### 4.2 手动备份

```bash
tar -czf kg-backup.tar.gz backend/data backend/uploads
```

### 4.3 数据迁移注意事项

1. **复制迁移**：拷贝 `graph.json` + `backups/` + `uploads/` 到新环境对应目录
2. **改实体类型标签**：类型重命名通过类型管理界面的「改名」，会级联更新实体，**不要手动改 JSON**
3. **版本号**：手改 JSON 后保持 `version` 递增，否则乐观锁会立即 409

---

## 5. 常见问题排查

### 5.1 前端访问不了（Windows）

```
现象：浏览器打不开 http://127.0.0.1:5173/
原因：Vite 绑定到 IPv6 [::1]:5173
解决：确认 package.json dev 脚本为 "vite --host 127.0.0.1"；或访问 http://[::1]:5173/
```

### 5.2 前端提示「无法连接后端服务」

```
原因1：后端没启动，或端口不对
      前端 src/api/index.js 的 BASE_URL 固定为 http://127.0.0.1:8800/api
解决1：把后端启动在 8800 端口，或同步修改 BASE_URL
原因2：跨域未放行
解决2：检查 api.py CORS allow_origins 是否包含前端地址
```

### 5.3 后端启动报 `python-multipart` 缺失

```
pip install python-multipart
# 注意：务必装到运行 uvicorn 的解释器里（which python 确认）
```

### 5.4 后端启动崩溃、无法导入 api

```
原因：PYTHONPATH 指向了其他工具的 Python 环境（如某些 shim）
解决：显式指定 PYTHONPATH=<项目根目录> 再启动，见 2.1
```

### 5.5 保存失败 / graph.json 写入被拒

```
原因：安全组件拦截了 rename/remove 类操作
处理：系统已内置降级（直接写主文件），无需干预；
      若仍失败，检查 backend/data 目录写权限
```

### 5.6 端口被占用

```bash
netstat -ano | grep :8800        # 找到 PID
taskkill -F -PID <PID>           # 结束进程
```

### 5.7 提交更新返回 409

```
原因：数据版本在打开表单后被其他页面/程序修改过
处理：刷新页面重新编辑即可（这是乐观锁的正常行为）
```

### 5.8 图片属性在详情面板不显示

```
原因：图片 URL 无法访问
检查：
1. 后端是否运行（图片通过 http://127.0.0.1:8800/uploads/ 提供）
2. 本地上传的图片是否还在 backend/uploads/
3. 粘贴的外部 URL 是否可公开访问
```

---

## 6. 升级与回滚

- **升级**：git pull 后重装依赖（`pip install -r requirements.txt`、`npm install`），无需迁移数据（JSON 兼容）
- **回滚**：从 `data/backups/` 选择目标时间点的备份，覆盖 `graph.json` 即可
