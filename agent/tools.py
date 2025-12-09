"""
Agent 工具模块
提供内置工具和工具注册机制，包含安全加固
"""

import ast
import json
import re
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Set
from urllib.parse import urlparse

from utils.logger import logger


@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: str  # string, number, boolean, object, array
    description: str = ""
    required: bool = True
    default: Any = None


@dataclass
class Tool:
    """工具定义"""
    name: str
    description: str
    func: Callable
    parameters: List[ToolParameter] = field(default_factory=list)
    is_async: bool = False

    async def execute(self, params: Dict[str, Any]) -> Any:
        """执行工具"""
        # 验证必需参数
        for param in self.parameters:
            if param.required and param.name not in params:
                if param.default is not None:
                    params[param.name] = param.default
                else:
                    raise ValueError(f"缺少必需参数: {param.name}")

        # 执行函数
        if self.is_async:
            return await self.func(**params)
        else:
            return self.func(**params)


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """注册工具"""
        self._tools[tool.name] = tool
        logger.info(f"注册工具: {tool.name}")

    def unregister(self, name: str) -> None:
        """注销工具"""
        if name in self._tools:
            del self._tools[name]

    def get_tool(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)

    def get_all_tools(self) -> Dict[str, Tool]:
        """获取所有工具"""
        return self._tools.copy()

    def list_tools(self) -> List[str]:
        """列出所有工具名称"""
        return list(self._tools.keys())


# ============== 安全配置 ==============

class SecurityConfig:
    """安全配置"""

    # 代码执行白名单模块
    ALLOWED_MODULES: Set[str] = {
        'math', 'statistics', 'datetime', 'json', 're',
        'collections', 'itertools', 'functools', 'operator',
        'string', 'textwrap', 'unicodedata',
        'decimal', 'fractions', 'random',
    }

    # 禁止的内置函数
    FORBIDDEN_BUILTINS: Set[str] = {
        'eval', 'exec', 'compile', 'open', 'input',
        '__import__', 'globals', 'locals', 'vars',
        'getattr', 'setattr', 'delattr', 'hasattr',
        'breakpoint', 'memoryview', 'help',
    }

    # 禁止的 AST 节点类型
    FORBIDDEN_AST_NODES: Set[type] = {
        ast.Import,
        ast.ImportFrom,
        ast.With,
        ast.AsyncWith,
        ast.Try,
        ast.Raise,
        ast.Global,
        ast.Nonlocal,
    }

    # URL 白名单域名
    ALLOWED_DOMAINS: Set[str] = {
        'api.github.com',
        'raw.githubusercontent.com',
        'httpbin.org',  # 测试用
    }

    # 最大代码执行时间（秒）
    MAX_EXECUTION_TIME: float = 5.0

    # 最大输出长度
    MAX_OUTPUT_LENGTH: int = 10000


class CodeSecurityChecker:
    """代码安全检查器"""

    def __init__(self, config: SecurityConfig = None):
        self.config = config or SecurityConfig()

    def check_code(self, code: str) -> tuple[bool, str]:
        """
        检查代码安全性

        Returns:
            (is_safe, error_message)
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"语法错误: {e}"

        # 检查 AST 节点
        for node in ast.walk(tree):
            # 检查禁止的节点类型
            if type(node) in self.config.FORBIDDEN_AST_NODES:
                return False, f"不允许使用 {type(node).__name__}"

            # 检查函数调用
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    if func_name in self.config.FORBIDDEN_BUILTINS:
                        return False, f"不允许调用 {func_name}()"

                # 检查属性调用（如 os.system）
                if isinstance(node.func, ast.Attribute):
                    attr_name = node.func.attr
                    if attr_name in {'system', 'popen', 'spawn', 'fork', 'exec'}:
                        return False, f"不允许调用 {attr_name}()"

            # 检查危险的属性访问
            if isinstance(node, ast.Attribute):
                if node.attr in {'__class__', '__bases__', '__subclasses__', '__mro__', '__globals__', '__code__'}:
                    return False, f"不允许访问 {node.attr}"

        return True, ""

    def create_safe_globals(self) -> Dict[str, Any]:
        """创建安全的全局命名空间"""
        import math
        import statistics
        import datetime
        import json as json_module
        import re as re_module
        import collections
        import itertools
        import functools
        import operator
        import string
        import decimal
        import fractions
        import random

        safe_builtins = {
            'abs': abs, 'all': all, 'any': any, 'ascii': ascii,
            'bin': bin, 'bool': bool, 'bytearray': bytearray, 'bytes': bytes,
            'callable': callable, 'chr': chr, 'complex': complex,
            'dict': dict, 'divmod': divmod, 'enumerate': enumerate,
            'filter': filter, 'float': float, 'format': format,
            'frozenset': frozenset, 'hex': hex, 'int': int,
            'isinstance': isinstance, 'issubclass': issubclass,
            'iter': iter, 'len': len, 'list': list, 'map': map,
            'max': max, 'min': min, 'next': next, 'oct': oct,
            'ord': ord, 'pow': pow, 'print': print, 'range': range,
            'repr': repr, 'reversed': reversed, 'round': round,
            'set': set, 'slice': slice, 'sorted': sorted,
            'str': str, 'sum': sum, 'tuple': tuple, 'type': type,
            'zip': zip,
            'True': True, 'False': False, 'None': None,
        }

        return {
            '__builtins__': safe_builtins,
            'math': math,
            'statistics': statistics,
            'datetime': datetime,
            'json': json_module,
            're': re_module,
            'collections': collections,
            'itertools': itertools,
            'functools': functools,
            'operator': operator,
            'string': string,
            'decimal': decimal,
            'fractions': fractions,
            'random': random,
        }


# ============== 内置工具实现 ==============

def create_search_tool(retriever) -> Tool:
    """创建知识库搜索工具"""

    async def search(query: str, top_k: int = 5) -> str:
        """搜索知识库"""
        try:
            results = await retriever.search(query, top_k=top_k)
            if not results:
                return "未找到相关内容"

            output = []
            for i, doc in enumerate(results, 1):
                content = doc.get('content', '')[:500]
                source = doc.get('metadata', {}).get('source', '未知')
                output.append(f"{i}. [{source}]\n{content}")

            return "\n\n".join(output)
        except Exception as e:
            return f"搜索失败: {e}"

    return Tool(
        name="search",
        description="搜索知识库，查找相关信息",
        func=search,
        parameters=[
            ToolParameter(name="query", type="string", description="搜索查询"),
            ToolParameter(name="top_k", type="number", description="返回结果数量", required=False, default=5),
        ],
        is_async=True
    )


def create_calculator_tool() -> Tool:
    """创建计算器工具（安全版本）"""

    security_checker = CodeSecurityChecker()

    def calculate(expression: str) -> str:
        """安全计算数学表达式"""
        # 安全检查
        is_safe, error = security_checker.check_code(expression)
        if not is_safe:
            return f"安全检查失败: {error}"

        try:
            # 使用安全的全局命名空间
            safe_globals = security_checker.create_safe_globals()
            safe_locals = {}

            # 执行表达式
            result = eval(expression, safe_globals, safe_locals)
            return str(result)
        except Exception as e:
            return f"计算错误: {e}"

    return Tool(
        name="calculator",
        description="计算数学表达式，支持基本运算和数学函数（如 math.sqrt, math.sin）",
        func=calculate,
        parameters=[
            ToolParameter(name="expression", type="string", description="数学表达式"),
        ],
        is_async=False
    )


def create_code_executor_tool() -> Tool:
    """创建代码执行工具（安全沙箱版本）"""

    security_checker = CodeSecurityChecker()

    def execute_code(code: str) -> str:
        """
        在安全沙箱中执行 Python 代码

        限制:
        - 不能导入模块（只能使用预置的安全模块）
        - 不能访问文件系统
        - 不能执行系统命令
        - 不能访问网络
        - 执行时间限制
        """
        # 安全检查
        is_safe, error = security_checker.check_code(code)
        if not is_safe:
            return f"安全检查失败: {error}"

        try:
            import io
            import contextlib
            import signal

            # 捕获输出
            output_buffer = io.StringIO()

            # 创建安全的执行环境
            safe_globals = security_checker.create_safe_globals()
            safe_locals = {}

            # 设置超时（仅 Unix）
            def timeout_handler(signum, frame):
                raise TimeoutError("代码执行超时")

            try:
                if hasattr(signal, 'SIGALRM'):
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(int(SecurityConfig.MAX_EXECUTION_TIME))
            except (ValueError, OSError):
                pass  # 在某些环境下可能不支持

            try:
                # 执行代码并捕获输出
                with contextlib.redirect_stdout(output_buffer):
                    exec(code, safe_globals, safe_locals)

                output = output_buffer.getvalue()

                # 限制输出长度
                if len(output) > SecurityConfig.MAX_OUTPUT_LENGTH:
                    output = output[:SecurityConfig.MAX_OUTPUT_LENGTH] + "\n... (输出被截断)"

                # 如果没有输出，返回最后一个表达式的值
                if not output and safe_locals:
                    last_value = list(safe_locals.values())[-1] if safe_locals else None
                    if last_value is not None:
                        output = str(last_value)

                return output if output else "代码执行成功（无输出）"

            finally:
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)

        except TimeoutError:
            return "错误: 代码执行超时（最大 5 秒）"
        except Exception as e:
            return f"执行错误: {type(e).__name__}: {e}"

    return Tool(
        name="code_executor",
        description="在安全沙箱中执行 Python 代码。支持数学计算、数据处理等。不能导入模块、访问文件或网络。",
        func=execute_code,
        parameters=[
            ToolParameter(name="code", type="string", description="要执行的 Python 代码"),
        ],
        is_async=False
    )


def create_web_search_tool() -> Tool:
    """创建网络搜索工具（模拟）"""

    def web_search(query: str) -> str:
        """模拟网络搜索（实际项目中应接入搜索 API）"""
        return f"网络搜索功能暂未实现。查询: {query}\n提示: 请使用知识库搜索工具 (search) 查找本地知识。"

    return Tool(
        name="web_search",
        description="搜索互联网获取最新信息（当前为模拟实现）",
        func=web_search,
        parameters=[
            ToolParameter(name="query", type="string", description="搜索查询"),
        ],
        is_async=False
    )


def create_datetime_tool() -> Tool:
    """创建日期时间工具"""

    def get_datetime(format: str = "%Y-%m-%d %H:%M:%S", timezone: str = "local") -> str:
        """获取当前日期时间"""
        from datetime import datetime
        import time

        now = datetime.now()

        try:
            return now.strftime(format)
        except Exception as e:
            return f"格式化错误: {e}"

    return Tool(
        name="datetime",
        description="获取当前日期和时间",
        func=get_datetime,
        parameters=[
            ToolParameter(name="format", type="string", description="日期格式，如 %Y-%m-%d", required=False, default="%Y-%m-%d %H:%M:%S"),
        ],
        is_async=False
    )


def create_json_tool() -> Tool:
    """创建 JSON 处理工具"""

    def process_json(data: str, operation: str = "parse", path: str = "") -> str:
        """处理 JSON 数据"""
        try:
            if operation == "parse":
                parsed = json.loads(data)
                return json.dumps(parsed, indent=2, ensure_ascii=False)

            elif operation == "get":
                parsed = json.loads(data)
                # 简单的路径访问，如 "a.b.c"
                for key in path.split('.'):
                    if key:
                        if isinstance(parsed, dict):
                            parsed = parsed.get(key)
                        elif isinstance(parsed, list) and key.isdigit():
                            parsed = parsed[int(key)]
                        else:
                            return f"无法访问路径: {path}"
                return json.dumps(parsed, indent=2, ensure_ascii=False) if isinstance(parsed, (dict, list)) else str(parsed)

            elif operation == "validate":
                json.loads(data)
                return "JSON 格式有效"

            else:
                return f"未知操作: {operation}"

        except json.JSONDecodeError as e:
            return f"JSON 解析错误: {e}"
        except Exception as e:
            return f"处理错误: {e}"

    return Tool(
        name="json",
        description="处理 JSON 数据：解析、验证、提取字段",
        func=process_json,
        parameters=[
            ToolParameter(name="data", type="string", description="JSON 字符串"),
            ToolParameter(name="operation", type="string", description="操作类型: parse/get/validate", required=False, default="parse"),
            ToolParameter(name="path", type="string", description="字段路径，如 a.b.c（仅 get 操作）", required=False, default=""),
        ],
        is_async=False
    )


def create_default_tool_registry(retriever=None) -> ToolRegistry:
    """创建默认工具注册表"""
    registry = ToolRegistry()

    # 注册内置工具
    registry.register(create_calculator_tool())
    registry.register(create_code_executor_tool())
    registry.register(create_datetime_tool())
    registry.register(create_json_tool())
    registry.register(create_web_search_tool())

    # 如果提供了 retriever，注册搜索工具
    if retriever:
        registry.register(create_search_tool(retriever))

    return registry
