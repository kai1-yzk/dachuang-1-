## Plan: 多服务器运维管理（MySQL + WebSocket 终端）

TL;DR - 在现有工程基础上扩展：
- 增加 MySQL 表用于记录服务器接入与指标；
- 实现 agent 主动注册/心跳（push 模式）；
- 数据采集模块定时写入 MySQL；
- 终端改为 WebSocket 双向会话，后端做会话路由到 agent；
- 构建 AI 命令解析引擎（危险命令库 + AST 分析）与审计表；
- 实现分级权限与一次性短码二次验证、会话超时与审计链追踪；
- 提供数据库初始化脚本、核心代码与部署/操作手册。

**Steps**
1. 数据库设计与初始化脚本（*依赖项：第2步 agent 字段*）
   - `servers`：id, hostname, ip, port, protocol, auth_type, auth_data(encrypted), tags, status, last_seen, created_at, updated_at
   - `server_metrics`：id, server_id, metric_type, metric_value(json/numeric), timestamp, raw_payload
   - `audit_logs`：id, user_id, server_id, session_id, command_raw, command_parsed, risk_score, action, result, created_at
   - `users`/`roles`/`mfa_challenges`：支持角色与一次性短码（short_code, expires_at, used）
   - 索引：`server_id+timestamp`、`user_id+created_at`、`risk_score`
2. Agent 主动接入（并行可做）
   - 实现轻量 agent（Python）示例：注册（POST /api/agents/register）、心跳（POST /api/agents/heartbeat）、上报指标（POST /api/agents/metrics）
   - Agent 启动时生成并上报自身元数据与能力标签；后端返回 `agent_token` 用于后续认证
   - 支持 SSH/SNMP 发现作为可选补充（后端提供扫描脚本）
3. 数据采集模块
   - 在 `data_collector/collector.py` 基础上实现采集调度（Celery/apscheduler），采集适配器（agent/http、SSH、SNMP）并写入 `server_metrics`
   - 批量写入与错误重试、去重机制
4. WebSocket 终端实现
   - 后端引入 `flask-socketio`（或 `fastapi`+`uvicorn` 视需要）并实现 WS 认证（JWT）
   - 会话管理：生成 `session_id`，绑定 `user_id` 与目标 `server_id`，保持 last_activity，15 分钟无交互断开
   - 消息路由：前端 WS -> 后端路由 -> 如果 agent 在线则转发到 agent 的 WS/REST；agent 回应再转回前端
   - 支持流式输出与分段推送
5. AI 命令解析与风控
   - 建立危险命令库（静态规则）并实现可配置策略
   - 使用命令解析器（`shlex`/`bashlex`）将命令转 AST，计算风险评分并输出解析结果
   - 语言模式：`ai_engine` 转换自然语言为候选命令并返回置信度，结果先经风控再下发
   - 所有被拦截或通过的操作写入 `audit_logs`
6. 分级权限与一次性短码流程
   - 角色：`operator`（白名单） 与 `superadmin`（可强制放行）
   - 普通用户：仅能执行白名单命令，命令须经 AI 审核
   - 超级用户：对高危命令触发短码二次验证；后端生成短码并通过邮件/短信发送，用户在 WS/REST 提交短码以确认
   - `mfa_challenges` 表用于存储短码、过期时间与使用状态
7. 审计与操作记录
   - 所有操作写入 `audit_logs`（user_id, server_id, session_id, raw_input, parsed_cmd, risk_score, action, result, timestamp）
   - 提供审计查询 API（分页、导出）
8. 性能与可用性设计
   - 使用 Redis 作 session 存储、flask-socketio 消息队列（Redis）与 Celery broker
   - 数据写入采用批量插入，读写分离与索引优化
   - 部署建议：多个后端实例 + 负载均衡（nginx 配置 websocket 支持），MySQL 主从或 RDS
9. 文档与交付
   - 提供 `deploy/init.sql` 完整建表脚本（含索引与必要触发器）
   - 提交 `backend/services/` 与 `backend/routes/` 的核心实现代码
   - 更新 `frontend/src/views/Terminal.vue` 使用 WebSocket 客户端实现
   - 编写部署文档与操作手册（agent 部署、用户使用、审计查询）

**Relevant files (将新增或修改）**
- backend/app.py  注册 WebSocket 服务与全局中间件
- backend/routes/agents.py  agent 注册/心跳/报告接口
- backend/routes/ws_terminal.py  WebSocket 终端入口与会话管理
- backend/routes/servers.py  服务器管理 API（列出/详情/删除）
- backend/routes/audit.py  审计查询与导出
- backend/services/agent_service.py  agent 注册/心跳逻辑
- backend/services/terminal_service.py  会话与命令下发路由
- backend/services/audit_service.py  审计写入/查询
- backend/utils/security.py  JWT 校验、角色校验、短码生成/校验、加密工具
- backend/utils/db.py  扩展批量插入接口
- data_collector/collector.py  多协议采集与入库
- deploy/init.sql  完整 DB 初始化脚本
- frontend/src/views/Terminal.vue  使用 WebSocket 改造前端终端
- agent/（新增）  轻量 agent 示例（Python）

**Verification**
1. 功能测试
   - Agent 注册/心跳/上报：模拟 100 个 agent 并检查 `servers` 表与心跳更新
   - WS 终端：模拟普通/超级用户会话，验证拦截、短码流程与审计记录
2. 性能测试
   - 并发管理 500 台 agent 的采集与指标写入，验证采集延迟 <=30s
   - 命令下发与回传链路压测，99% 响应 <3s
3. 安全测试
   - 短码流程、JWT、权限越权测试与敏感字段加密验证

**Decisions (已确认)**
- Agent 模式：agent 主动注册（push）
- 二次验证：一次性短码（short code，通过邮件/短信发送）
- WebSocket 实现建议：使用 `flask-socketio` + Redis message queue（或如需更高异步性能可选 `fastapi` + `uvicorn`）

**Further Considerations**
1. 短码投递方式：需确认是否有短信服务或仅邮件即可。若两者均无，可使用邮件或企业内部通知工具。推荐优先邮件，生产环境接入 SMS 提供商。
2. Agent 自动发现的频率与扫描权限需谨慎（避免对网络产生过多扫描流量）。
3. 是否需要在本次交付中包含 agent 完整安装脚本与 systemd 单元？（建议包含）

请确认是否开始实现阶段（我将按里程碑生成具体任务清单并开始修改代码）。
