# 轻量化智能运维防护平台 — 功能规格说明书

> 本文档以**当前仓库代码为准**编写，替换早期 psutil 单机采集方案的历史版本。
> 最后核对时间：2026-11，对应分支 `fix/pre-test-hardening`。
> 核对方式：逐条比对 `backend/routes/*.py` 的路由注册与 `frontend/src/views/*.vue` 的调用点。

---

## 1. 系统定位

面向中小团队的多服务器运维控制台，核心特征是**真实采集 + 安全控制 + 审计闭环**：

- 指标数据全部来自受管服务器的 **SSH 实时采集**，不使用前端 mock 或本机 psutil。
- 高风险操作走「风险评估 → 显式确认 → 可选 MFA 短码 → 审计留痕」链路。
- 批量命令必须先创建任务、经审批后才会执行。

**不适用场景**：单机个人运维、无 SSH 可达性的封闭网络、需要 Agent 主动推送且完全无法出网的场景。

---

## 2. 技术架构

### 2.1 分层

```
前端 (Vue 3 + Vite + Element Plus + ECharts)
   │  Axios（Bearer Token、401 无感刷新）、socket.io-client
   ▼
后端 (Flask + Flask-SocketIO/gevent)
   ├── routes/      路由蓝图（14 个业务域）
   ├── services/    业务服务（SSH、指标、风险评估、审计、备份…）
   └── utils/       DB 连接池、Redis、JWT、加密、AI 客户端
   │
   ├──► MySQL    业务数据、指标、审计
   ├──► Redis    事件计数、Celery broker
   └──► SSH      受管服务器（paramiko）
```

### 2.2 关键设计取舍

| 决策 | 说明 |
|------|------|
| 采集走 SSH 而非 Agent | 免去在目标机部署组件，代价是采集频率受 SSH 握手开销限制（默认 10s） |
| 天然不支持 Windows 目标机 | `METRICS_COMMAND` 依赖 `top/free/df`，仅适用于 Linux |
| Redis 缺失可降级 | 事件计数回退为 1，不阻断主链路；Celery 不可用时同步执行路径仍工作 |
| 数据库不可用则快速失败 | 注册/登录等接口返回 503 并给出 `last_error`，不做假成功 |

---

## 3. 功能模块

### 3.1 认证与权限

| 能力 | 说明 |
|------|------|
| 注册 / 登录 | bcrypt 存密码，签发 JWT 双令牌（Access 15min / Refresh 7d） |
| 令牌刷新 | Refresh Token 与库中记录比对，支持主动吊销 |
| RBAC | 角色：`operator` / `tenant_operator` / `tenant_admin` / `platform_admin` / `superadmin` |
| 多租户 | 请求上下文携带 `tenant_id`，查询按租户隔离；`GET /api/tenants/`、`POST /api/tenants/`、`GET /api/tenants/context` |

**接口**：`POST /api/auth/register`、`/login`、`/refresh`、`/logout`、`/mfa/request-code`、`/mfa/verify-code`

### 3.2 服务器纳管

| 能力 | 说明 |
|------|------|
| 新增服务器 | 支持 `password` / `key` 两种鉴权；密码经 Fernet 加密后存 `auth_data` JSON |
| SSH 连通性测试 | `POST /api/servers/{id}/ssh-test` |
| SSH 配置更新 | `PUT /api/servers/{id}/ssh-config` |
| 主机指纹校验 | `SSH_STRICT_HOST_KEY=true` 时严格校验，开发环境可关闭 |

> 注意：`servers.ssh_password_ciphertext` 列当前**未使用**，实际密文存于 `auth_data` JSON 的 `ssh_password` 字段（`enc$` 前缀）。该列为历史遗留，读取时不要依赖它。

**接口**：`GET|POST /api/servers/`、`GET|DELETE /api/servers/{id}`、`POST /api/servers/{id}/ssh-test`、`PUT /api/servers/{id}/ssh-config`

### 3.3 监控指标

- 通过 SSH 执行单条聚合命令，一次取回 CPU / 内存 / 磁盘 / 网络四项指标。
- 自动采集器按 `AUTO_COLLECT_INTERVAL_SECONDS`（默认 5s）轮询全部在线服务器。
- 大屏支持 `server_id` 过滤与周期趋势（1h / 6h / 24h / 自定义）。
- Kubernetes 概览依赖目标机已安装 `kubectl` 并配置集群上下文，否则返回空。

**接口**：`GET /api/metrics/dashboard`、`/trend`、`/current`、`/k8s-overview`、`POST /api/metrics/collect`

### 3.4 服务管理

- 枚举常见服务（nginx / mysql / redis / docker / ssh / cron 等）状态与自启动状态。
- 支持 start / stop / restart / autostart 切换。
- 命令回退链：`systemctl` → `sudo -n systemctl` → `chkconfig` → `rc-update`。
- 目标机账号需具备 NOPASSWD sudo 权限，否则返回 `permission_denied`（`error_type` 字段）。

**接口**：`GET /api/services/list`、`POST /api/services/control`、`POST /api/services/autostart`

### 3.5 运维终端（WebSocket）

事件流：`terminal_connect` → `terminal_ready` → `terminal_command` → `terminal_output`

- 命令先经风险评估：`LOW` 直接执行；`MEDIUM`/`HIGH` 拦截或要求 MFA。
- `superadmin` 遇到 `HIGH` 命令时下发 `mfa_required`（含 `demo_code`，演示环境直接回传），
  校验通过后下发 `mfa_result`，**需客户端重新提交命令**才会执行。
- 会话空闲超时 `SESSION_TIMEOUT_SECONDS`（900s）后失效。

**事件**：`terminal_connect`、`terminal_command`、`mfa_confirm`、`terminal_disconnect`
**服务端推送**：`terminal_ready`、`terminal_output`、`terminal_error`、`terminal_timeout`、`mfa_required`、`mfa_result`

### 3.6 风险评估模型

`services/command_risk_service.py`：

| 维度 | 规则 |
|------|------|
| 危险模式 | `rm -rf`、`dd`、`fdisk`、`mkfs`、`shutdown`、`reboot` 等每命中 +80 |
| 管道 / 重定向 | 各 +10 |
| 分级 | `>= 80` → HIGH，`>= 10` → MEDIUM，其余 LOW |
| operator | MEDIUM 及以上一律拦截；开启 `TERMINAL_STRICT_WHITELIST` 时仅放行白名单 |
| superadmin | HIGH 需 MFA 短码确认后才放行 |

> 分级阈值与打分口径必须保持一致：早期版本 `>= 40` 才算 MEDIUM，导致
> `cat /etc/passwd > /tmp/out`（得分 20）被判为 LOW 而放行，已修正为 `>= 10`。

### 3.7 AI 分析与预测

- `POST /api/ai/predict` — 接收特征序列，返回异常判定与趋势预测。
- `GET /api/ai/predict/server/{server_id}` — 基于库中该服务器最新指标做预测。
- `GET /api/ai/predict-alert/{server_id}` — 返回故障类型、风险等级、起因、应急方案与预防建议。
- `POST /api/ai/execute_command` — 命令经白名单与风险评估后**通过 SSH 真实下发**；
  缺 `server_id` 返回 400，SSH 失败返回 502，执行结果写入审计。

> 该接口前端未直接使用（前端走 `/api/assistant/*`），保留为对外 API 与调试入口。

### 3.8 智能助手

两阶段执行模型：

1. `POST /api/assistant/ops-plan` — 生成方案、风险评估，签发一次性 `execution_token`（TTL 300s）
   - **风险不允许时直接 403，不签发令牌**
2. `POST /api/assistant/ops-execute` — 校验令牌归属、consent、二次确认，按当前角色**重新评估风险**后经 SSH 执行

审计动作：`assistant_plan`（`planned` / `blocked`）、`assistant_execute`（`success` / `failed` / `error`）

> 有 `DEEPSEEK_API_KEY` 时调用大模型生成方案，否则回退到规则映射（`ai_source=fallback`）。

**接口**：`POST /api/assistant/query`、`/suggestion/approve`、`/ops-plan`、`/ops-execute`

### 3.9 批量命令审批

流程：创建任务（`pending_approval`）→ 审批 → 逐台执行 → 记录每台结果。

**接口**：`GET|POST /api/batch/jobs`、`POST /api/batch/jobs/{id}/approve`、`GET /api/batch/jobs/{id}/results`

### 3.10 文件管理

远程目录浏览、文件读取、在线编辑保存、新建目录、删除（需确认参数）。

**接口**：`GET /api/files/list`、`/read`、`/server-info`、`POST /api/files/write`、`/mkdir`、`/delete`

### 3.11 备份恢复

支持数据库备份与配置备份任务，恢复需带确认开关。

**接口**：`GET|POST /api/backup/jobs`、`POST /api/backup/restore`

### 3.12 日志与审计

- 日志检索与异常聚类：`GET /api/logs/search`、`/anomaly-clusters`
- 审计查询与安全概览：`GET /api/audit/logs`、`GET /api/audit/security-overview`
- `audit_logs` 记录字段：用户、角色、服务器、命令原文/解析后、风险分/等级、动作、结果、明细、时间

### 3.13 数据接入（Agent 模式，可选）

支持轻量 Agent 主动上报，作为 SSH 采集的补充通道。

**接口**：`POST /api/data/ingest`、`GET /api/data/stats`、`POST /api/agents/register`、`/heartbeat`、`/metrics`、`GET /api/agents/servers`、`POST /api/agents/discover`

---

## 4. 前端视图

| 路由 | 视图 | 主要能力 |
|------|------|----------|
| `/login`、`/register` | Login / Register | 登录注册，密码复杂度校验 |
| `/dashboard` | Dashboard | 指标卡、趋势图、异常时间轴、K8s 概览 |
| `/metrics/trend` | MetricTrend | 周期筛选与多指标趋势 |
| `/servers` | Servers | 服务器纳管、SSH 测试 |
| `/terminal` | Terminal | WebSocket 终端、MFA 确认、审计回显 |
| `/services` | Services | 服务状态与控制 |
| `/logs` | Logs | 日志检索与异常聚类 |
| `/backup` | Backup | 备份任务与恢复 |
| `/files` | FileManager | 远程文件浏览与编辑 |
| `/batch` | BatchExec | 批量命令创建与审批 |
| `/assistant` | Assistant | 方案生成与确认执行 |
| `/tenants` | Tenants | 租户管理 |

---

## 5. 数据模型（主要表）

| 表 | 用途 |
|----|------|
| `user` | 用户、角色、租户、refresh_token |
| `tenants` | 租户 |
| `servers` | 受管服务器与鉴权信息 |
| `server_metrics` | 指标时序数据 |
| `audit_logs` | 审计日志 |
| `mfa_challenges` | MFA 短码挑战 |
| `terminal_sessions` | 终端会话 |
| `batch_jobs` / `batch_job_results` | 批量任务与逐台结果 |
| `backup_jobs` / `backup_artifacts` / `restore_records` | 备份与恢复 |

建表脚本：`deploy/init.sql`（**幂等**，可重复执行）。

---

## 6. 已知限制

1. **仅支持 Linux 目标机**：采集与服务管理命令依赖 `top/free/df/systemctl`。
2. **服务控制依赖 NOPASSWD sudo**：否则返回 `permission_denied`，属环境配置而非缺陷。
3. **MFA 为演示形态**：短码通过响应体直接回传，生产环境需接短信/邮件。
4. **Docker Compose 需 WSL2**：Windows 上若 WSL2 不可用，compose 无法启动；本地开发可用原生 MySQL + Redis。
5. **无 License 文件**：开源前需补充。

---

## 7. 测试与验证

```bash
cd backend
python -m pytest -q
```

当前覆盖（86 个用例）：

| 测试文件 | 覆盖内容 |
|----------|----------|
| `test_command_risk.py` | 危险命令拦截、管道/重定向分级、角色策略、自然语言映射 |
| `test_ai_execute.py` | 命令拦截、缺参 400、真实 SSH 下发、SSH 失败 502 |
| `test_assistant_ops.py` | 风险拦截不签发令牌、consent、令牌归属、重放拦截、审计写入 |
| `test_auth_middleware.py` | JWT 校验、过期/伪造令牌、公开路径、安全响应头 |
| `test_metrics_parse.py` | 指标输出解析、布尔严格解析 |
| `test_service_manager.py` | 命令回退链、成功时不残留错误信息 |
| `test_ssh_pty.py` | pty 默认关闭、显式开启、输出收集 |
| `test_mfa_timezone.py` | MFA 过期时间使用本地时区 |
| `test_redis_config.py` | Redis 惰性初始化、Celery URL 组装 |
| `test_data_ingestion.py` | 数据接入、Redis 降级、空请求体 |

CI（`.github/workflows/ci.yml`）在 push/PR 时执行后端 `pytest` 与前端 `npm run build`。
