import os
import socket
import time
from typing import Dict

import psutil
import requests

API_BASE = os.environ.get("AIOPS_API_BASE", "http://127.0.0.1:5000/api")
HOSTNAME = socket.gethostname()
IP = os.environ.get("AGENT_IP", "127.0.0.1")
PORT = int(os.environ.get("AGENT_PORT", 22))
INTERVAL = int(os.environ.get("AGENT_REPORT_INTERVAL", 15))


def collect_metrics() -> Dict:
    net = psutil.net_io_counters()
    return {
        "cpu": psutil.cpu_percent(interval=0.5),
        "memory": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage("/").percent,
        "network_rx": round(net.bytes_recv / 1024 / 1024, 3),
        "network_tx": round(net.bytes_sent / 1024 / 1024, 3),
    }


def register_agent() -> Dict:
    payload = {
        "hostname": HOSTNAME,
        "ip": IP,
        "port": PORT,
        "protocol": "agent",
        "tags": ["linux", "auto-register"],
        "capabilities": {"metrics": True, "command": True},
    }
    resp = requests.post(f"{API_BASE}/agents/register", json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()["data"]


def main():
    print("[agent] registering...")
    data = register_agent()
    server_id = data["server_id"]
    token = data["agent_token"]
    print(f"[agent] registered server_id={server_id}")

    while True:
        try:
            hb_payload = {
                "server_id": server_id,
                "agent_token": token,
                "stats": {"uptime_sec": int(time.time())},
            }
            requests.post(f"{API_BASE}/agents/heartbeat", json=hb_payload, timeout=10).raise_for_status()

            metric_payload = {
                "server_id": server_id,
                "agent_token": token,
                "metrics": collect_metrics(),
            }
            requests.post(f"{API_BASE}/agents/metrics", json=metric_payload, timeout=10).raise_for_status()
            print("[agent] heartbeat + metrics uploaded")
        except Exception as exc:
            print(f"[agent] report failed: {exc}")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
