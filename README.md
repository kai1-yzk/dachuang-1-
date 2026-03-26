# 轻量化 AI 服务器运维防护系统

面向中小企业的智能运维平台，支持多服务器接入、实时指标采集、AI 风险命令分析、分级权限控制和全链路审计。

## 1. 功能概览

- 多服务器管理：Agent 主动注册、心跳维持、在线状态追踪。
- 指标采集：CPU、内存、磁盘、网络指标定时入库 MySQL。
- 双模式终端：命令模式 + 自然语言模式（映射标准 Linux 命令）。
- AI 风控：危险命令特征库 + 语法解析 + 风险分级。
- 分级权限：`operator` 白名单执行；`superadmin` 高危操作需一次性短码。
- 会话安全：15 分钟无操作自动超时。
- 审计闭环：记录用户、命令、风险评分、执行结果、会话链路。

## 2. 系统架构

- 8 层架构图：`docs/architecture_8_layers.mmd`
- 多服务器规划文档：`docs/multi_server_management_plan.md`

核心组件：
- 前端：`frontend/`（Vue 3 + Element Plus）
- 后端：`backend/`（Flask + Flask-SocketIO + Celery）
- 数据：MySQL + Redis
- AI：`ai_engine/`（Isolation Forest + LSTM）
- Agent：`agent/`（主动注册、心跳、指标上报）

## 3. 技术栈

- Frontend：Vue 3、Vite、Element Plus、Axios、Socket.IO Client
- Backend：Flask、Flask-SocketIO、PyJWT、Celery、Redis、PyMySQL
- AI：PyTorch、Scikit-learn、Pandas、NumPy
- Ops：Docker Compose、Gunicorn、Gevent

## 4. 目录结构

```text
frontend/                 前端项目（登录、仪表盘、终端）
backend/                  后端 API 与 WebSocket 服务
backend/routes/           路由层（auth/ai/metrics/agents/audit/servers）
backend/services/         业务服务层（agent/audit/risk）
ai_engine/                训练与推理模型代码
data_collector/           数据采集与预处理模块
agent/                    受管服务器 agent 示例
deploy/init.sql           数据库初始化脚本（含表结构与存储过程）
docs/                     架构、部署、操作文档
```

## 5. 快速开始

### 5.1 初始化数据库

```bash
mysql -u root -p < deploy/init.sql
```

### 5.2 启动后端

```bash
cd backend
pip install -r requirements.txt
python app.py
```

### 5.3 启动异步任务

```bash
cd backend
celery -A tasks worker --loglevel=info
```

### 5.4 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 5.5 启动 Agent 示例

```bash
cd agent
pip install -r requirements.txt
python agent_client.py
```

## 6. API 与 WebSocket

### 6.1 认证与会话

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `POST /api/auth/mfa/request-code`
- `POST /api/auth/mfa/verify-code`

### 6.2 Agent 接入

- `POST /api/agents/register`
- `POST /api/agents/heartbeat`
- `POST /api/agents/metrics`
- `GET /api/agents/servers`

### 6.3 审计与服务器

- `GET /api/audit/logs?limit=100`
- `GET /api/servers/`
- `GET /api/servers/{id}`

### 6.4 终端 WebSocket 事件

客户端发送：
- `terminal_connect`：携带 `token`、`server_id`
- `terminal_command`：携带 `session_id`、`input`
- `mfa_confirm`：携带 `session_id`、`code`
- `terminal_disconnect`

服务端返回：
- `terminal_ready`
- `terminal_output`
- `mfa_required`
- `mfa_result`
- `terminal_timeout`
- `terminal_error`

## 7. 安全设计

- JWT 身份校验 + 角色字段（`operator`/`superadmin`）。
- 高危命令识别（`rm -rf`、`dd`、`fdisk`、`mkfs` 等）。
- 超级用户高危命令必须通过一次性短码。
- 所有关键行为写入 `audit_logs`。
- 终端会话 15 分钟空闲超时。

## 8. 性能目标

- 支持管理 >= 500 台服务器（多实例后端 + Redis + Celery）。
- 命令响应时间 <= 3 秒（P99 目标）。
- 指标采集延迟 <= 30 秒。
- 系统可用性目标 99.9%。

## 9. 文档清单

- 部署指南：`docs/DEPLOYMENT.md`
- 操作手册：`docs/OPERATION_MANUAL.md`
- 功能规格：`Project_Functional_Specification.md`

## 10. 注意事项

- 生产环境请使用环境变量管理密钥与数据库凭据。
- `mfa/request-code` 在演示环境返回 `demo_code`，生产请接入短信/邮件网关。
- Flask 内存限流适合单实例，生产建议切换 Redis 存储。
