"""
Agent 模块 - ReAct 模式的智能代理框架

提供工具调用、多步推理、任务分解等能力
"""

from .core import Agent, AgentConfig, AgentResult, AgentState, ThoughtAction
from .tools import (
    Tool,
    ToolParameter,
    ToolRegistry,
    create_search_tool,
    create_calculator_tool,
    create_code_executor_tool,
    create_datetime_tool,
    create_json_tool,
    create_web_search_tool,
    create_default_tool_registry,
)

__all__ = [
    # 核心类
    'Agent',
    'AgentConfig',
    'AgentResult',
    'AgentState',
    'ThoughtAction',
    # 工具类
    'Tool',
    'ToolParameter',
    'ToolRegistry',
    # 工具工厂函数
    'create_search_tool',
    'create_calculator_tool',
    'create_code_executor_tool',
    'create_datetime_tool',
    'create_json_tool',
    'create_web_search_tool',
    'create_default_tool_registry',
]
