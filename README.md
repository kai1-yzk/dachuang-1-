# 轻量化智能运维防护平台

一个面向中小团队的全栈运维平台，聚焦「真实数据采集 + 安全控制 + 智能分析 + 可视化运维」。

系统支持 SSH 多服务器纳管、实时指标采集、服务控制、备份恢复、文件管理、批量命令审批、智能助手执行方案、WebSocket 终端以及 AI 故障预测，并提供审计闭环。

## 项目描述

本项目以 Flask + Vue 3 为核心，构建了一个可直接落地的运维控制台：

- 前端采用控制台布局，操作路径统一。
- 后端采用蓝图化 API 设计，支持多租户上下文与权限控制。
- 指标数据来自受管服务器实时采集并入库，不依赖前端 mock。
- 高风险操作具备确认机制与审计记录，支持追溯。

适用场景：

- 中小型业务集群的统一运维入口。
- 需要终端运维但又要有审批、审计、风险拦截的团队。
- 希望将传统人工巡检升级为可视化 + 自动化 + 智能化流程的项目。

## 功能介绍

### 1. 监控大屏

- 展示 CPU、内存、磁盘、网络吞吐等核心指标。
- 支持趋势图与周期筛选（近 1h / 6h / 24h / 自定义）。
- 支持 AI 故障预测详情（故障类型、风险等级、起因、应急方案、预防建议）。
- 支持 Kubernetes 概览（节点、Pod、Deployment 统计，基于服务器 `kubectl` 上下文）。

### 2. 运维终端（WebSocket）

- 实时会话交互，支持远程执行命令并回显。
- 支持高风险二次确认流程。
- 自动写入审计日志（命令输入、解析结果、执行状态）。

### 3. 服务管理

- 支持常见服务状态查询：`nginx/mysql/redis/docker/ssh/cron`。
- 支持启动、停止、重启、自启动切换。
- 命令执行具备系统兼容回退策略：`systemctl` -> `sudo -n systemctl` -> `service`。

### 4. 备份恢复中心

- 支持数据库备份和配置备份任务创建。
- 支持备份产物恢复（带确认开关）。
- 支持任务状态与执行结果查询。

### 5. 文件管理器

- 支持远程目录浏览、文件读取、在线编辑保存。
- 支持新建目录、删除文件/目录（带确认参数）。

### 6. 批量命令审批

- 支持多服务器批量命令任务创建。
- 支持审批通过后执行，记录每台服务器执行结果。

### 7. 智能助手

- 生成操作方案、风险评估、执行预期。
- 经用户确认后**通过 SSH 真实下发执行**（不再是模拟返回），并回传 `exit_status`、`stdout`、`stderr`。
- 风险评估不允许的命令在方案阶段即返回 403，不签发执行令牌。
- 未配置 `DEEPSEEK_API_KEY` 时自动回退到规则映射（`ai_source=fallback`）。

### 8. 多租户与安全审计

- 租户上下文隔离（`tenant_id`）。
- 角色鉴权（operator / tenant_operator / tenant_admin / platform_admin / superadmin）。
- 审计日志覆盖关键操作链路：终端命令、服务控制、助手方案生成与执行、批量审批。

## 技术创新

### 1. 真实采集闭环

- 指标通过 SSH 从服务器实时采集并落库。
- 大屏、趋势图、预测、审计使用同一真实数据源。

### 2. 安全优先的执行链路

- 高风险操作显式确认。
- 批量命令带审批流程。
- 全链路审计可追溯。

### 3. 模块化后端扩展设计

- Flask 蓝图拆分业务域：`auth / metrics / assistant / services / backup / files / batch / logs`。
- 便于按模块扩展与隔离风险。

### 4. 运维平台化能力聚合

在单控制台内融合监控、终端、服务控制、备份恢复、文件管理、批量审批、智能助手，降低工具割裂成本。

## 技术栈

### 前端

- Vue 3
- Vite
- Element Plus
- ECharts
- Axios
- socket.io-client

### 后端

- Flask
- Flask-SocketIO (gevent)
- Flask-Limiter
- PyJWT
- Paramiko
- Celery + Redis
- PyMySQL

### AI 与数据

- PyTorch
- scikit-learn
- pandas / numpy

### 运维与部署

- Docker / Docker Compose
- Gunicorn
- Prometheus + Grafana（可选）

## 目录结构

```text
frontend/                 Vue 3 前端控制台
backend/                  Flask 后端 API + SocketIO
backend/routes/           路由蓝图
backend/services/         业务服务
backend/utils/            安全、DB、Redis 等工具
ai_engine/                模型训练与推理代码（数据集与模型产物不入库）
ai_engine/README.md       数据集获取与模型生成说明
data_collector/           数据采集预处理脚本
deploy/init.sql           数据库初始化脚本
docker-compose.yml        一键容器编排
docs/                     架构与规划文档
```

## 安装指南

## 方式 A：本地开发（推荐）

### 1. 环境要求

- Python 3.11（推荐）
- Node.js 18+
- MySQL 8.0+
- Redis 6+

> 说明：`scikit-learn==1.3.0` 在 Python 3.14 上构建兼容性较差，建议使用 Python 3.11 虚拟环境。

### 2. 初始化数据库

```bash
mysql -u root -p < deploy/init.sql
```

### 3. 启动后端

```bash
cd backend
pip install -r requirements.txt
python app.py
```

默认监听：`http://localhost:5001`

### 4. 启动 Celery Worker（可选但推荐）

```bash
cd backend
celery -A tasks worker --loglevel=info
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

默认访问：`http://localhost:3000`（或按你当前 Vite 配置端口）

## 方式 B：Docker Compose

```bash
docker compose up -d
```

默认包含：MySQL、Redis、Backend、Celery Worker、Frontend、Prometheus、Grafana。

## 使用示例

### 示例 1：登录获取 Token

```bash
curl -X POST http://localhost:5001/api/auth/login \
 -H "Content-Type: application/json" \
 -d '{"username":"admin","password":"admin123"}'
```

### 示例 2：接入 SSH 服务器

```bash
curl -X POST http://localhost:5001/api/servers/ \
 -H "Authorization: Bearer <ACCESS_TOKEN>" \
 -H "Content-Type: application/json" \
 -d '{
  "hostname":"prod-web-1",
  "ip":"192.168.1.10",
  "port":22,
  "auth_type":"password",
  "ssh_username":"root",
  "ssh_password":"your_password",
  "connect_timeout":15
 }'
```

### 示例 3：查看监控大屏数据

```bash
curl "http://localhost:5001/api/metrics/dashboard?collect_now=1&points=12" \
 -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### 示例 4：操作服务（重启 nginx）

```bash
curl -X POST http://localhost:5001/api/services/control \
 -H "Authorization: Bearer <ACCESS_TOKEN>" \
 -H "Content-Type: application/json" \
 -d '{"server_id":1,"service_name":"nginx","action":"restart"}'
```

### 示例 5：创建批量命令并审批

```bash
# 1) 创建任务
curl -X POST http://localhost:5001/api/batch/jobs \
 -H "Authorization: Bearer <ACCESS_TOKEN>" \
 -H "Content-Type: application/json" \
 -d '{"command":"uptime","server_ids":[1,2]}'

# 2) 审批执行
curl -X POST http://localhost:5001/api/batch/jobs/1/approve \
 -H "Authorization: Bearer <ACCESS_TOKEN>" \
 -H "Content-Type: application/json" \
 -d '{"approve":true}'
```

### 示例 6：智能助手执行流程

```bash
# 1) 生成执行方案（风险不允许时返回 403，且不签发令牌）
curl -X POST http://localhost:5001/api/assistant/ops-plan \
 -H "Authorization: Bearer <ACCESS_TOKEN>" \
 -H "Content-Type: application/json" \
 -d '{"command":"df -h","server_id":1}'

# 2) 确认执行（token 有效期 300 秒，需 consent=true）
curl -X POST http://localhost:5001/api/assistant/ops-execute \
 -H "Authorization: Bearer <ACCESS_TOKEN>" \
 -H "Content-Type: application/json" \
 -d '{"execution_token":"<TOKEN>","consent":true,"high_risk_confirmed":false}'
```

> 注：`high_risk_confirmed` 仅在高风险命令时需要为 `true`；风险等级为 `HIGH` 且未确认时返回 409。
> 若命令被判为不允许执行，`ops-plan` 阶段就会直接返回 403，不会走到执行环节。

## 核心接口清单（节选）

- 认证：`/api/auth/*`
- 监控：`/api/metrics/dashboard`、`/api/metrics/trend`、`/api/metrics/k8s-overview`
- 服务器：`/api/servers/*`
- 终端：WebSocket `terminal_connect / terminal_command / mfa_confirm`
- 服务管理：`/api/services/list`、`/api/services/control`、`/api/services/autostart`
- 日志中心：`/api/logs/search`、`/api/logs/anomaly-clusters`
- 备份恢复：`/api/backup/jobs`、`/api/backup/restore`
- 文件管理：`/api/files/list`、`/api/files/read`、`/api/files/write`、`/api/files/mkdir`、`/api/files/delete`
- 批量审批：`/api/batch/jobs`、`/api/batch/jobs/{id}/approve`、`/api/batch/jobs/{id}/results`
- 智能助手：`/api/assistant/query`、`/api/assistant/ops-plan`、`/api/assistant/ops-execute`

## 配置说明

完整配置文档请先看：`docs/环境配置与自定义项.md`

后端支持自动加载 `backend/.env`（也兼容 `backend/.ENV`）。建议先执行：

```powershell
cd backend
copy .env.example .env
# 然后编辑 .env，把 DB_PASSWORD 改成你的 MySQL 密码
```

如果你启动后端看到：

`Access denied for user 'root'@'localhost' (using password: NO)`

说明 `DB_PASSWORD` 没有设置。可在当前 PowerShell 会话先执行：

```powershell
$env:DB_HOST="127.0.0.1"
$env:DB_PORT="3306"
$env:DB_USER="root"
$env:DB_PASSWORD="你的MySQL密码"
$env:DB_NAME="aiops_db"
```

常用环境变量（后端）：

- `JWT_SECRET_KEY`：JWT 密钥
- `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME`
- `REDIS_HOST` / `REDIS_PORT`
- `AUTO_COLLECT_ENABLED`：是否开启自动采集（默认 1）
- `AUTO_COLLECT_INTERVAL_SECONDS`：自动采集周期秒数（默认 5）
- `SSH_STRICT_HOST_KEY`：SSH 严格主机指纹校验开关
- `DEEPSEEK_API_KEY`：DeepSeek API Key（仅后端读取）
- `DEEPSEEK_BASE_URL`：DeepSeek API 地址（默认 `https://api.deepseek.com/v1`）
- `DEEPSEEK_MODEL`：DeepSeek 模型（默认 `deepseek-chat`）

## 常见问题与排障

### 1. 前端能打开但接口 401

- 检查是否已登录并携带 `access_token`。
- 检查 `JWT_SECRET_KEY` 是否被重置导致旧 token 失效。

### 2. 服务控制失败

- 确认目标服务器已接入并 SSH 可连接。
- 确认目标系统具备 `systemctl` 或 `service`。
- 确认账号权限允许操作服务。

### 3. 备份/文件/批量功能不可用

- 先确认有可用 `server_id`。
- 检查路由返回的错误信息（前端已显示后端 message）。

### 4. k8s 概览为空

- 目标服务器未安装 `kubectl` 或未配置集群上下文。

### 5. 服务控制返回 permission_denied

- 目标机运维账号缺少 NOPASSWD sudo 权限。检查：`sudo -n true`。
- 需要在该服务器上为运维账号配置免密 sudo，平台不会交互式输入密码。

### 6. MFA 短码提示「无效或已过期」

- 常见原因是数据库与应用时区不一致。短码的 `expires_at` 与 MySQL `NOW()` 比较，
  两者必须处于同一时区基准。若服务器时区与数据库会话时区不同，请统一配置。

### 7. Docker Compose 起不来

- Windows 上 compose 依赖 WSL2。若 `wsl --status` 报错或 `HCS_E_SERVICE_NOT_AVAILABLE`，
  需安装 WSL2 并开启虚拟化后重启。
- 本地开发可改用原生 MySQL + Redis，不必依赖 Docker。

## 测试

```bash
cd backend
python -m pytest -q
```

当前共 86 个用例，覆盖命令风险评估、JWT 鉴权、AI 执行链、助手审批与审计、
服务命令回退链、SSH pty 行为、MFA 时区、Redis/Celery 配置、数据接入降级。

CI 在 push / PR 时自动执行后端测试与前端构建。

## 文档与规划

- 功能规格：`Project_Functional_Specification.md`
- 多服务器规划：`docs/multi_server_management_plan.md`
- 架构图：`docs/architecture_8_layers.mmd`
- 已知问题：`docs/项目存在问题_按修复难度分级.md`

## 贡献指南

欢迎提交 Issue / PR。建议遵循：

- 小步提交，单一变更目标。
- 新增接口保持统一返回结构：`code/message/data`。
- 涉及高风险行为时补齐审计与权限校验。
- 新增核心逻辑时同步补充单元测试。

## License

本项目采用 [MIT License](LICENSE)。

注意：仓库中的 AI 数据集（GAIA、UNSW-NB15）为第三方公开学术数据集，
不在本许可证覆盖范围内，使用时请遵守其各自的许可与引用要求。
详见 `ai_engine/README.md`。
