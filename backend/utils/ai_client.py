import os
import json
import logging

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)

_DEFAULT_BASE = "https://api.deepseek.com/v1"
_DEFAULT_MODEL = "deepseek-chat"


def _resolve_ai_env():
    """Unify AI_API_* with DEEPSEEK_* (same as ai_explainer_service / .env.example)."""
    api_key = (os.environ.get("AI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    base_url = (os.environ.get("AI_BASE_URL") or os.environ.get("DEEPSEEK_BASE_URL") or _DEFAULT_BASE).strip()
    model = (os.environ.get("AI_MODEL") or os.environ.get("DEEPSEEK_MODEL") or _DEFAULT_MODEL).strip()
    return api_key, base_url, model


def get_ai_client():
    if not OpenAI:
        logger.error("OpenAI package is not installed.")
        return None, None

    api_key, base_url, model = _resolve_ai_env()

    if not api_key:
        logger.warning(
            "No AI API key: set DEEPSEEK_API_KEY or AI_API_KEY in environment."
        )
        return None, None

    client = OpenAI(api_key=api_key, base_url=base_url)
    return client, model


def generate_ops_plan(command: str) -> dict:
    """
    Generate operation steps and expected effect using AI.
    Returns a dict with 'steps' (list of str) and 'expected_effect' (str).
    """
    client, model = get_ai_client()
    
    default_response = {
        "steps": [
            "1) 建议先执行命令前置检查（资源与权限）",
            f"2) 执行命令: {command}",
            "3) 校验执行结果是否符合预期，并记录审计日志"
        ],
        "expected_effect": "命令正常返回退出状态 exit_status=0，目标服务状态恢复或指标回落。",
        "command": command,
        "ai_source": "fallback",
    }

    if not client:
        return default_response

    system_prompt = (
        "你是一个专业的Linux系统运维专家。"
        "用户将提供一个运维意图（自然语言）或者一个具体的Linux命令。"
        "请你分析用户的输入，并将其转化为具体的、可执行的Linux命令，同时提供执行步骤(steps)和预期效果(expected_effect)。"
        "你的输出必须是一个合法的JSON对象，不要包含其他无关内容（如Markdown格式的```json标签），包含以下三个字段："
        "\n1. 'command': 根据用户意图生成的具体Linux命令。如果用户输入已经是具体的命令，请保持原样或进行优化修正。"
        "\n2. 'steps': 一个字符串数组，描述执行该命令前、中、后的步骤。"
        "\n3. 'expected_effect': 一个字符串，描述该命令成功执行后的预期效果。"
    )
    
    user_prompt = f"请分析以下运维需求并生成执行方案：\n{command}"
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=1024
        )
        
        content = response.choices[0].message.content.strip()
        # Clean up markdown JSON blocks if present
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
            
        content = content.strip()
        result = json.loads(content)
        
        # Validate result format
        if isinstance(result, dict) and "steps" in result and "expected_effect" in result:
            if "command" not in result:
                result["command"] = command
            result["ai_source"] = "api"
            return result
        else:
            logger.warning("AI response format is invalid, falling back to default.")
            return default_response

    except Exception as e:
        logger.error(f"Error calling AI API: {e}")
        return default_response


def query_ai_assistant(question: str, context: list) -> dict:
    """
    Query the AI assistant with a question and some context.
    Returns a dict with 'answer' (str).
    """
    client, model = get_ai_client()
    
    default_response = {
        "answer": "基于当前运维记录，建议先执行低风险检查，再根据结果决定是否走审批执行高风险操作。",
        "ai_source": "fallback",
    }

    if not client:
        return default_response
        
    context_str = "\n".join([f"- {c.get('text', '')}" for c in context]) if context else "无近期审计日志记录。"
    
    system_prompt = (
        "你是一个专业的Linux系统运维AI助手。"
        "请根据用户提供的问题以及近期的审计日志上下文（如果有），给出专业的分析、建议和回答。"
        "回答请尽量简明扼要，突出重点。"
    )
    
    user_prompt = f"上下文记录：\n{context_str}\n\n用户问题：{question}"
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5,
            max_tokens=800
        )
        
        answer = response.choices[0].message.content.strip()
        return {"answer": answer, "ai_source": "api"}

    except Exception as e:
        logger.error(f"Error calling AI API: {e}")
        return default_response
