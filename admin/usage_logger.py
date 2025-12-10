"""
LLM 使用日志记录工具
统一记录所有 LLM 调用（问答、Agent、MCP 等）
"""
from typing import Optional, Dict, Any
from admin.database import SessionLocal
from admin.models import LLMUsageLog, LLMModel, LLMProvider
from utils.logger import logger


def get_default_model_info(db=None) -> Dict[str, Any]:
    """
    获取默认模型的 ID 和供应商 ID

    Returns:
        包含 model_id, provider_id, model_name, provider_name 的字典
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # 查找默认模型
        model = db.query(LLMModel).filter(LLMModel.is_default == True).first()
        if model:
            provider = db.query(LLMProvider).filter(LLMProvider.id == model.provider_id).first()
            return {
                "model_id": model.id,
                "provider_id": model.provider_id,
                "model_name": model.display_name,
                "provider_name": provider.name if provider else None
            }

        # 没有默认模型，尝试获取第一个激活的模型
        model = db.query(LLMModel).filter(LLMModel.is_active == True).first()
        if model:
            provider = db.query(LLMProvider).filter(LLMProvider.id == model.provider_id).first()
            return {
                "model_id": model.id,
                "provider_id": model.provider_id,
                "model_name": model.display_name,
                "provider_name": provider.name if provider else None
            }

        return {"model_id": None, "provider_id": None, "model_name": None, "provider_name": None}
    finally:
        if close_db:
            db.close()


def log_llm_usage(
    request_type: str,
    question: Optional[str] = None,
    answer: Optional[str] = None,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    model_id: Optional[int] = None,
    provider_id: Optional[int] = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    cost: float = None,  # None 表示自动计算
    request_time: float = 0.0,
    total_time: float = 0.0,
    retrieval_count: int = 0,
    rerank_used: bool = False,
    status: str = "success",
    error_message: Optional[str] = None,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Optional[int]:
    """
    记录 LLM 使用日志

    Args:
        request_type: 请求类型 ('query', 'query_stream', 'search', 'test', 'add_knowledge', 'agent', 'mcp', 'other')
        question: 用户问题/查询内容
        answer: 回答内容（会截断到前1000字）
        user_id: 用户ID
        username: 用户名
        model_id: 模型ID（不提供则使用默认模型）
        provider_id: 供应商ID（不提供则使用默认模型的供应商）
        prompt_tokens: 输入 token 数
        completion_tokens: 输出 token 数
        total_tokens: 总 token 数
        cost: 估算成本
        request_time: LLM 请求耗时（秒）
        total_time: 总耗时（秒）
        retrieval_count: 检索到的文档数
        rerank_used: 是否使用了重排
        status: 状态 ('success', 'error')
        error_message: 错误信息
        client_ip: 客户端 IP
        user_agent: 用户代理

    Returns:
        日志记录 ID，失败返回 None
    """
    db = None
    try:
        db = SessionLocal()

        # 如果没有提供 model_id，获取默认模型
        if model_id is None or provider_id is None:
            default_info = get_default_model_info(db)
            if model_id is None:
                model_id = default_info.get("model_id")
            if provider_id is None:
                provider_id = default_info.get("provider_id")

        # 截断问题和回答
        truncated_question = question[:500] if question else None
        truncated_answer = answer[:1000] if answer else None
        truncated_error = error_message[:1000] if error_message else None

        # 自动计算费用（如果未提供）
        if cost is None:
            # 获取模型信息用于精确计费
            model_name = None
            if model_id:
                model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
                if model:
                    model_name = model.model_id
            cost = calculate_cost(prompt_tokens, completion_tokens, model_name)

        # 创建日志记录
        log_entry = LLMUsageLog(
            model_id=model_id,
            provider_id=provider_id,
            user_id=user_id,
            username=username,
            request_type=request_type,
            question=truncated_question,
            answer_preview=truncated_answer,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            request_time=request_time,
            total_time=total_time,
            retrieval_count=retrieval_count,
            rerank_used=rerank_used,
            status=status,
            error_message=truncated_error,
            client_ip=client_ip,
            user_agent=user_agent
        )

        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)

        logger.debug(f"LLM 使用日志已记录: {request_type}, ID={log_entry.id}")
        return log_entry.id

    except Exception as e:
        logger.warning(f"记录 LLM 使用日志失败: {e}")
        if db:
            db.rollback()
        return None
    finally:
        if db:
            db.close()


def estimate_tokens(text: str) -> int:
    """
    简单估算文本的 token 数
    粗略估计：中文约 1 字符 = 1.5 token，英文约 4 字符 = 1 token
    """
    if not text:
        return 0

    # 计算中文字符数
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars

    # 估算 token 数
    estimated = int(chinese_chars * 1.5 + other_chars / 4)
    return max(1, estimated)


def estimate_cost(total_tokens: int, model_name: str = None) -> float:
    """
    估算调用成本（简化版，已废弃，请使用 calculate_cost）
    """
    return calculate_cost(0, total_tokens, model_name)


# 模型定价表（每百万 token 的美元价格）
MODEL_PRICING = {
    # Claude 模型
    "claude-3-5-haiku": {"input": 0.25, "output": 1.25},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-opus": {"input": 15.0, "output": 75.0},
    # OpenAI 模型
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-4": {"input": 30.0, "output": 60.0},
    "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
    # 默认定价（用于未知模型）
    "default": {"input": 1.0, "output": 3.0},
}


def calculate_cost(prompt_tokens: int, completion_tokens: int, model_name: str = None) -> float:
    """
    根据模型计算调用成本

    Args:
        prompt_tokens: 输入 token 数
        completion_tokens: 输出 token 数
        model_name: 模型名称（如 claude-3-5-haiku-20241022）

    Returns:
        成本（美元）
    """
    # 查找匹配的定价
    pricing = MODEL_PRICING.get("default")

    if model_name:
        model_lower = model_name.lower()
        for key in MODEL_PRICING:
            if key in model_lower:
                pricing = MODEL_PRICING[key]
                break

    # 计算费用（价格是每百万 token）
    input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output"]

    return round(input_cost + output_cost, 6)
