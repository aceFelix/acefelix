# CI 后端 job 失败修复复盘：mcp 2.0 移除 fastmcp

## 1. 问题现象

- **场景**：为 acefelix 配置 GitHub Actions CI 后，首次运行 **Backend (Python 3.11)** job 失败
- **具体表现**：`python test_mcp_server.py` 报错

```
File ".../backend/mcp_server.py", line 22, in <module>
    from mcp.server.fastmcp import FastMCP
ModuleNotFoundError: No module named 'mcp.server.fastmcp'
```

- **影响范围**：所有 Python 版本矩阵的后端测试全部失败，CI 无法通过

## 2. 排查过程

| 阶段 | 假设/判断 | 实际操作 | 结论 |
|---|---|---|---|
| 1 | 本地代码有误？ | 本地运行 `python backend/test_mcp_server.py` | 10/10 通过，**本地正常** |
| 2 | CI 与本地依赖不一致 | 对比本地 `pip show mcp` 与 CI 安装逻辑 | 本地 mcp **1.28.0**；CI 按 `mcp>=1.0.0` 安装 |
| 3 | **mcp 大版本变更（根因）** | `pip index versions mcp` | 最新版已是 **2.0.0**，`>=1.0.0` 在 CI 解析到 2.0.0 |

### 关键转折点

`pip index versions mcp` 显示 LATEST = 2.0.0，而本地 INSTALLED = 1.28.0。
mcp 2.0 对包结构做了重构，`mcp.server.fastmcp`（FastMCP 所在位置）被移动/移除，
导致按最新版安装的 CI 环境 `from mcp.server.fastmcp import FastMCP` 报模块不存在。

## 3. 根因分析

- **真正原因**：`requirements.txt` 中 `mcp>=1.0.0` 是**无上限的范围约束**。GitHub Actions 全新环境
  会解析到最新版 **mcp 2.0.0**，而 2.0 重构了 `mcp.server.fastmcp` 模块位置；
  本地开发环境停留在 1.28.0，掩盖了该问题——典型的"本地与 CI 依赖版本漂移"。
- **为什么之前的实现会出错**：只写了下限 `>=1.0.0`，未考虑 major 版本的破坏性变更
- **涉及模块**：`backend/requirements.txt`、CI 依赖安装步骤

## 4. 修复方案

**修改文件**：[backend/requirements.txt](file:///e:/2.MyProjects/MyAgentChat/J.A.R.V.I.S/acefelix/backend/requirements.txt)

```diff
- mcp>=1.0.0
+ mcp>=1.28.0,<2.0.0
```

- 下限 `>=1.28.0`：不低于本地已验证可用的版本（1.28.0 含 `mcp.server.fastmcp`）
- 上限 `<2.0.0`：避开 mcp 2.0 的模块重构，直到代码适配新 API
- 同步更新 [docs/ARCHITECTURE.md](file:///e:/2.MyProjects/MyAgentChat/J.A.R.V.I.S/acefelix/docs/ARCHITECTURE.md) 技术栈表中 mcp 版本说明

**为什么有效**：把版本约束在 1.x 稳定线内，CI 与本地环境依赖保持一致，fastmcp 必定可用。

## 5. 验证结果

- **本地验证**：`python backend/test_mcp_server.py` 10/10 通过，无回归
- **CI 验证**：重新推送触发 GitHub Actions，待后端矩阵全部变绿（二次确认中）
- **前端 job**：不受影响（Node 侧无 mcp 依赖）

## 6. 涉及文件

| 文件 | 改动说明 |
|---|---|
| `backend/requirements.txt` | mcp 版本约束 `>=1.0.0` → `>=1.28.0,<2.0.0` |
| `docs/ARCHITECTURE.md` | 技术栈表 mcp 版本与原因说明 |

## 7. 经验总结

- **依赖必须写版本上下限**：对快速迭代的库（mcp、fastapi 等），只写下限会在全新环境
  装到带破坏性变更的 major 版本，造成"本地绿、CI 红"。
- **排查"本地正常 CI 失败"的有效路径**：先对比本地与 CI 的依赖版本（`pip show` vs 安装逻辑），
  再查 `pip index versions <pkg>` 确认是否有新 major。
- **可固化为规则**：`requirements.txt` 中对核心依赖采用 `>=x.y,<major+1` 的约束；
  引入新依赖后在本机验证过的最小版本作为下限。
