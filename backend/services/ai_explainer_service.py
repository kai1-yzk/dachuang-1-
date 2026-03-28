import json
import logging
import os
from typing import Any, Dict, List

import requests


DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_TIMEOUT_SECONDS = int(os.environ.get("DEEPSEEK_TIMEOUT_SECONDS", "12"))
logger = logging.getLogger(__name__)


def _fallback_explain(alert: Dict[str, Any], prediction: Dict[str, Any]) -> Dict[str, Any]:
    metrics = (alert or {}).get("metrics_snapshot") or {}
    risk_level = (alert or {}).get("risk_level") or "低"
    is_anomaly = bool((prediction or {}).get("is_anomaly"))
    score = float((prediction or {}).get("anomaly_score") or 0.0)

    summary = "未检测到显著异常，建议持续观察。"
    if is_anomaly:
        summary = f"检测到异常风险（score={score:.2f}, risk={risk_level}），建议优先排查高负载资源。"

    causes: List[str] = []
    if float(metrics.get("cpu") or 0.0) >= 85:
        causes.append("CPU 长时间高负载")
    if float(metrics.get("memory") or 0.0) >= 85:
        causes.append("内存占用接近上限")
    if float(metrics.get("disk") or 0.0) >= 85:
        causes.append("磁盘空间或 IO 压力过高")
    if not causes:
        causes.append("短时抖动或业务流量波动")

    return {
        "provider": "fallback",
        "model": "rule-based",
        "degraded": True,
        "failure_reason": "deepseek_not_configured_or_failed",
        "summary": summary,
        "probable_causes": causes,
        "emergency_actions": [
            "检查 top/htop，定位高资源进程",
            "检查关键服务日志并确认错误峰值时间",
            "必要时先做限流或重启单个异常服务",
        ],
        "prevention_actions": [
            "配置资源阈值告警并分级通知",
            "为关键服务设置容量冗余与自动扩缩容策略",
            "定期清理日志并做压测基线校准",
        ],
    }


def _parse_json_content(content: str) -> Dict[str, Any]:
    text = (content or "").strip()
    if not text:
        return {}
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except Exception:
        return {"summary": text}


def _build_prompt(alert: Dict[str, Any], prediction: Dict[str, Any], server_id: int) -> str:
    payload = {
        "server_id": server_id,
        "prediction": prediction,
        "alert": alert,
    }
    return (
        "你是运维故障分析助手。请基于输入数据输出严格 JSON，不要输出其它文字。"
        "JSON schema: {summary:string, probable_causes:string[], emergency_actions:string[], prevention_actions:string[]}。"
        f"输入: {json.dumps(payload, ensure_ascii=False)}"
    )


def build_explain(alert: Dict[str, Any], prediction: Dict[str, Any], server_id: int) -> Dict[str, Any]:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        logger.info("DeepSeek explain fallback because API key is missing, server_id=%s", server_id)
        fallback = _fallback_explain(alert, prediction)
        fallback["failure_reason"] = "deepseek_api_key_missing"
        return fallback

    try:
        url = f"{DEEPSEEK_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": DEEPSEEK_MODEL,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": "你是资深 SRE，回答要简洁、可执行。"},
                {"role": "user", "content": _build_prompt(alert, prediction, server_id)},
            ],
        }
        resp = requests.post(url, headers=headers, json=body, timeout=DEEPSEEK_TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()
        content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        parsed = _parse_json_content(content)

        fallback = _fallback_explain(alert, prediction)
        return {
            "provider": "deepseek",
            "model": DEEPSEEK_MODEL,
            "degraded": False,
            "failure_reason": None,
            "summary": parsed.get("summary") or fallback.get("summary"),
            "probable_causes": parsed.get("probable_causes") or fallback.get("probable_causes"),
            "emergency_actions": parsed.get("emergency_actions") or fallback.get("emergency_actions"),
            "prevention_actions": parsed.get("prevention_actions") or fallback.get("prevention_actions"),
        }
    except Exception as e:
        logger.warning("DeepSeek explain failed for server_id=%s: %s", server_id, str(e))
        fallback = _fallback_explain(alert, prediction)
        fallback["failure_reason"] = "deepseek_request_failed"
        return fallback
