# Agent Client

此目录提供受管服务器 Agent 的最小示例，实现以下能力：
- 启动后主动注册到后端 `/api/agents/register`
- 定时上报心跳到 `/api/agents/heartbeat`
- 定时上报性能指标到 `/api/agents/metrics`

## 运行方式

```bash
cd agent
pip install -r requirements.txt
python agent_client.py
```

## 环境变量

- `AIOPS_API_BASE`：后端 API 地址，默认 `http://127.0.0.1:5000/api`
- `AGENT_IP`：Agent 报告 IP，默认 `127.0.0.1`
- `AGENT_PORT`：Agent 端口，默认 `22`
- `AGENT_REPORT_INTERVAL`：上报间隔（秒），默认 `15`
