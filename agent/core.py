"""
Agent 核心模块
实现 ReAct (Reasoning + Acting) 模式的 Agent 框架
"""

import json
import re
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from utils.logger import logger


class AgentState(Enum):
    """Agent 状态"""
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    FINISHED = "finished"
    ERROR = "error"


@dataclass
class AgentConfig:
    """Agent 配置"""
    max_iterations: int = 10  # 最大迭代次数
    max_thinking_time: float = 30.0  # 最大思考时间(秒)
    verbose: bool = True  # 是否输出详细日志
    early_stop: bool = True  # 是否在找到答案后提前停止
    retry_on_error: int = 2  # 错误重试次数


@dataclass
class ThoughtAction:
    """思考-行动对"""
    thought: str  # 思考内容
    action: Optional[str] = None  # 行动名称
    action_input: Optional[Dict[str, Any]] = None  # 行动输入
    observation: Optional[str] = None  # 观察结果


@dataclass
class AgentResult:
    """Agent 执行结果"""
    success: bool
    answer: Optional[str] = None
    thought_actions: List[ThoughtAction] = field(default_factory=list)
    error: Optional[str] = None
    iterations: int = 0
    total_tokens: int = 0


class Agent:
    """
    ReAct Agent 实现

    工作流程:
    1. 接收用户问题
    2. 思考(Thought): 分析问题，决定下一步行动
    3. 行动(Action): 调用工具执行操作
    4. 观察(Observation): 获取工具返回结果
    5. 重复 2-4 直到得出最终答案
    """

    REACT_PROMPT = """你是一个智能助手，能够使用工具来回答问题。

可用工具:
{tools_description}

请使用以下格式回答问题:

Question: 用户的问题
Thought: 你的思考过程，分析问题需要什么信息
Action: 要使用的工具名称，必须是 [{tool_names}] 之一
Action Input: 工具的输入参数，JSON 格式
Observation: 工具返回的结果（由系统填充）
... (可以重复 Thought/Action/Action Input/Observation)
Thought: 我现在知道最终答案了
Final Answer: 最终答案

重要规则:
1. 每次只能调用一个工具
2. Action 必须是可用工具之一
3. Action Input 必须是有效的 JSON
4. 当你有足够信息回答问题时，直接给出 Final Answer
5. 如果工具调用失败，尝试其他方法或直接回答

Question: {question}
{agent_scratchpad}"""

    def __init__(
        self,
        llm_client,
        tool_registry: 'ToolRegistry',
        config: Optional[AgentConfig] = None
    ):
        """
        初始化 Agent

        Args:
            llm_client: LLM 客户端
            tool_registry: 工具注册表
            config: Agent 配置
        """
        self.llm = llm_client
        self.tools = tool_registry
        self.config = config or AgentConfig()
        self.state = AgentState.IDLE

    def _build_tools_description(self) -> str:
        """构建工具描述"""
        descriptions = []
        for name, tool in self.tools.get_all_tools().items():
            desc = f"- {name}: {tool.description}"
            if tool.parameters:
                params = ", ".join([
                    f"{p.name}({p.type}): {p.description}"
                    for p in tool.parameters
                ])
                desc += f"\n  参数: {params}"
            descriptions.append(desc)
        return "\n".join(descriptions)

    def _build_tool_names(self) -> str:
        """构建工具名称列表"""
        return ", ".join(self.tools.get_all_tools().keys())

    def _build_scratchpad(self, thought_actions: List[ThoughtAction]) -> str:
        """构建 Agent 草稿本（历史思考和行动）"""
        scratchpad = ""
        for ta in thought_actions:
            scratchpad += f"Thought: {ta.thought}\n"
            if ta.action:
                scratchpad += f"Action: {ta.action}\n"
                scratchpad += f"Action Input: {json.dumps(ta.action_input, ensure_ascii=False)}\n"
            if ta.observation:
                scratchpad += f"Observation: {ta.observation}\n"
        return scratchpad

    def _parse_llm_output(self, output: str) -> ThoughtAction:
        """解析 LLM 输出"""
        thought_action = ThoughtAction(thought="")

        # 提取 Thought
        thought_match = re.search(r'Thought:\s*(.+?)(?=Action:|Final Answer:|$)', output, re.DOTALL)
        if thought_match:
            thought_action.thought = thought_match.group(1).strip()

        # 检查是否有 Final Answer
        final_match = re.search(r'Final Answer:\s*(.+?)$', output, re.DOTALL)
        if final_match:
            thought_action.observation = f"FINAL_ANSWER: {final_match.group(1).strip()}"
            return thought_action

        # 提取 Action
        action_match = re.search(r'Action:\s*(.+?)(?=Action Input:|$)', output, re.DOTALL)
        if action_match:
            thought_action.action = action_match.group(1).strip()

        # 提取 Action Input
        input_match = re.search(r'Action Input:\s*(.+?)(?=Observation:|$)', output, re.DOTALL)
        if input_match:
            try:
                input_str = input_match.group(1).strip()
                # 尝试解析 JSON
                thought_action.action_input = json.loads(input_str)
            except json.JSONDecodeError:
                # 如果不是有效 JSON，作为字符串处理
                thought_action.action_input = {"input": input_str}

        return thought_action

    async def run(self, question: str, context: Optional[str] = None) -> AgentResult:
        """
        运行 Agent

        Args:
            question: 用户问题
            context: 可选的上下文信息

        Returns:
            AgentResult: 执行结果
        """
        self.state = AgentState.THINKING
        thought_actions: List[ThoughtAction] = []
        total_tokens = 0

        try:
            for iteration in range(self.config.max_iterations):
                # 构建 prompt
                prompt = self.REACT_PROMPT.format(
                    tools_description=self._build_tools_description(),
                    tool_names=self._build_tool_names(),
                    question=question,
                    agent_scratchpad=self._build_scratchpad(thought_actions)
                )

                if context:
                    prompt = f"背景信息:\n{context}\n\n{prompt}"

                # 调用 LLM
                if self.config.verbose:
                    logger.info(f"Agent 迭代 {iteration + 1}/{self.config.max_iterations}")

                response = await self.llm.chat(prompt)
                total_tokens += response.get('usage', {}).get('total_tokens', 0)

                # 解析输出
                llm_output = response.get('content', '')
                thought_action = self._parse_llm_output(llm_output)

                # 检查是否有最终答案
                if thought_action.observation and thought_action.observation.startswith("FINAL_ANSWER:"):
                    answer = thought_action.observation.replace("FINAL_ANSWER:", "").strip()
                    thought_actions.append(thought_action)
                    self.state = AgentState.FINISHED

                    return AgentResult(
                        success=True,
                        answer=answer,
                        thought_actions=thought_actions,
                        iterations=iteration + 1,
                        total_tokens=total_tokens
                    )

                # 执行工具
                if thought_action.action:
                    self.state = AgentState.ACTING

                    try:
                        tool = self.tools.get_tool(thought_action.action)
                        if tool:
                            observation = await tool.execute(thought_action.action_input or {})
                            thought_action.observation = str(observation)
                        else:
                            thought_action.observation = f"错误: 工具 '{thought_action.action}' 不存在"
                    except Exception as e:
                        thought_action.observation = f"工具执行错误: {str(e)}"

                    self.state = AgentState.THINKING

                thought_actions.append(thought_action)

            # 达到最大迭代次数
            self.state = AgentState.ERROR
            return AgentResult(
                success=False,
                error="达到最大迭代次数，未能得出答案",
                thought_actions=thought_actions,
                iterations=self.config.max_iterations,
                total_tokens=total_tokens
            )

        except Exception as e:
            self.state = AgentState.ERROR
            logger.error(f"Agent 执行错误: {e}")
            return AgentResult(
                success=False,
                error=str(e),
                thought_actions=thought_actions,
                total_tokens=total_tokens
            )

    def run_sync(self, question: str, context: Optional[str] = None) -> AgentResult:
        """同步运行 Agent"""
        import asyncio
        return asyncio.run(self.run(question, context))
