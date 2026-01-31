"""
LLM MCP Host Refactor - 模块化重构版本
提供增强的MCP代理功能，包括：
1. 向量搜索工具匹配（mock实现）
2. 聊天上下文管理（基于时间和回合数）
3. 多MCP服务器支持
4. MCP提示获取
"""

from .agent import MCPVoiceAgent, process_llm_host
from .context_manager import ContextManager
from .tool_selector import ToolSelector
from .mcp_manager import MCPServerManager
from .prompt_manager import PromptManager
from .utils import mcp_tools_to_openai_tools

__all__ = [
    'MCPVoiceAgent',
    'process_llm_host',
    'ContextManager',
    'ToolSelector',
    'MCPServerManager',
    'PromptManager',
    'mcp_tools_to_openai_tools',
]

__version__ = '1.0.0'
