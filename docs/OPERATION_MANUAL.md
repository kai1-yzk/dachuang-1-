# Operation Manual

环境与变量配置总入口：`docs/环境配置与自定义项.md`

## 1. 用户角色

- `operator`：仅允许白名单命令，所有请求均经 AI 风控。
- `superadmin`：可强制执行高危命令，但必须通过一次性短码确认。

## 2. 终端使用流程

1. 用户登录后进入 `Terminal` 页面。
2. 前端通过 WebSocket 建立会话，服务端返回 `session_id`。
3. 用户输入命令或自然语言描述。
4. 后端执行命令解析、语法分析与风险评级。
5. 若为高危命令且角色为 `superadmin`，触发短码校验。
6. 校验通过后放行执行并记录完整审计日志。

## 3. 审计日志查询

- 接口：`GET /api/audit/logs?limit=100`
- 关键字段：`user_id`, `session_id`, `command_raw`, `risk_score`, `result`

## 4. 常见运维操作

- 查看已接入服务器：`GET /api/servers/`
- 查看指定服务器指标：`GET /api/servers/{id}`
- 查看 Agent 在线状态：`GET /api/agents/servers`

## 5. 故障排查

- WebSocket 连接失败：检查 Nginx 是否正确转发 Upgrade 头。
- Agent 无法注册：检查 `AIOPS_API_BASE`、防火墙策略与后端地址。
- 指标无数据：检查 Redis、Celery Worker、MySQL 写入权限。
