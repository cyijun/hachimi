"""
MCP服务器管理器
支持多个MCP服务器连接和工具映射
"""
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from contextlib import AsyncExitStack
from dataclasses import dataclass

from mcp import ClientSession
from logger import logger

from .utils import mcp_transport_factory, create_tool_identifier, parse_tool_identifier
from .tool_selector import ToolInfo


@dataclass
class ServerInfo:
    """服务器信息"""
    name: str
    config: Dict[str, Any]
    session: Optional[ClientSession] = None
    tools: List[Any] = None  # 原始MCP工具
    prompts: List[Any] = None  # MCP提示
    
    def __post_init__(self):
        if self.tools is None:
            self.tools = []
        if self.prompts is None:
            self.prompts = []


class MCPServerManager:
    """MCP服务器管理器，支持多个服务器"""
    
    def __init__(self):
        self.servers: Dict[str, ServerInfo] = {}
        self._exit_stack = AsyncExitStack()
        self.tool_mapping: Dict[str, Tuple[str, str]] = {}  # unique_name -> (server_name, original_name)
        self.name_conflict_resolution: Dict[str, int] = {}  # original_name -> 冲突计数
    
    async def add_server(self, server_name: str, config: Dict[str, Any]) -> bool:
        """
        添加并连接MCP服务器
        
        Args:
            server_name: 服务器名称
            config: 服务器配置
            
        Returns:
            是否成功连接
        """
        try:
            logger.info(f"🔌 连接MCP服务器: {server_name}")
            
            # 创建传输层
            read, write = await self._exit_stack.enter_async_context(
                mcp_transport_factory(config)
            )
            
            # 创建会话
            session = await self._exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            
            await session.initialize()
            
            # 获取工具和提示
            tools_result = await session.list_tools()
            prompts_result = await session.list_prompts() if hasattr(session, 'list_prompts') else None
            
            # 创建服务器信息
            server_info = ServerInfo(
                name=server_name,
                config=config,
                session=session,
                tools=tools_result.tools if tools_result else [],
                prompts=prompts_result.prompts if prompts_result else []
            )
            
            self.servers[server_name] = server_info
            logger.info(f"✅ 服务器 {server_name} 连接成功，加载 {len(server_info.tools)} 个工具")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 连接服务器 {server_name} 失败: {e}")
            return False
    
    async def get_all_tools(self) -> List[ToolInfo]:
        """从所有服务器获取工具信息"""
        all_tools = []
        
        for server_name, server_info in self.servers.items():
            for tool in server_info.tools:
                # 处理工具名冲突
                unique_name = self._resolve_tool_name(server_name, tool.name)
                
                tool_info = ToolInfo(
                    name=unique_name,
                    original_name=tool.name,
                    server_name=server_name,
                    description=tool.description or "",
                    parameters=tool.inputSchema,
                    metadata={
                        "server_type": server_info.config.get("type", "unknown"),
                        "original_tool": tool,
                    }
                )
                
                all_tools.append(tool_info)
                # 保存映射
                self.tool_mapping[unique_name] = (server_name, tool.name)
        
        return all_tools
    
    async def get_all_prompts(self) -> List[Dict[str, Any]]:
        """从所有服务器获取提示信息"""
        all_prompts = []
        
        for server_name, server_info in self.servers.items():
            for prompt in server_info.prompts:
                prompt_info = {
                    "name": prompt.name,
                    "server": server_name,
                    "description": prompt.description or "",
                    "arguments": prompt.arguments or {},
                }
                all_prompts.append(prompt_info)
        
        return all_prompts
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        调用工具
        
        Args:
            tool_name: 工具唯一标识符
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        if tool_name not in self.tool_mapping:
            raise ValueError(f"工具未找到: {tool_name}")
        
        server_name, original_tool_name = self.tool_mapping[tool_name]
        
        if server_name not in self.servers:
            raise ValueError(f"服务器未找到: {server_name}")
        
        server_info = self.servers[server_name]
        
        try:
            logger.info(f"🛠️  调用工具: {server_name}:{original_tool_name}")
            result = await server_info.session.call_tool(original_tool_name, arguments=arguments)
            return result
        except Exception as e:
            logger.error(f"❌ 工具调用失败 {tool_name}: {e}")
            raise
    
    async def get_prompt(self, prompt_name: str, server_name: Optional[str] = None, **kwargs) -> Optional[str]:
        """
        获取提示内容
        
        Args:
            prompt_name: 提示名称
            server_name: 服务器名称（可选，如果为None则搜索所有服务器）
            **kwargs: 提示参数
            
        Returns:
            提示内容，如果未找到则返回None
        """
        if server_name:
            # 从指定服务器获取
            if server_name in self.servers:
                server_info = self.servers[server_name]
                for prompt in server_info.prompts:
                    if prompt.name == prompt_name:
                        try:
                            result = await server_info.session.get_prompt(prompt_name, **kwargs)
                            return result.content[0].text if result.content else ""
                        except Exception as e:
                            logger.error(f"❌ 获取提示失败 {prompt_name}: {e}")
                            return None
        else:
            # 搜索所有服务器
            for s_name, server_info in self.servers.items():
                for prompt in server_info.prompts:
                    if prompt.name == prompt_name:
                        try:
                            result = await server_info.session.get_prompt(prompt_name, **kwargs)
                            return result.content[0].text if result.content else ""
                        except Exception as e:
                            logger.error(f"❌ 获取提示失败 {s_name}:{prompt_name}: {e}")
                            continue
        
        return None
    
    def _resolve_tool_name(self, server_name: str, original_name: str) -> str:
        """
        解决工具名冲突
        
        Args:
            server_name: 服务器名称
            original_name: 原始工具名
            
        Returns:
            唯一工具标识符
        """
        # 首先尝试使用标准格式
        standard_name = create_tool_identifier(server_name, original_name)
        
        # 检查是否有冲突（相同原始工具名在不同服务器）
        if original_name in self.name_conflict_resolution:
            # 已经有冲突，使用带编号的格式
            count = self.name_conflict_resolution[original_name]
            unique_name = f"{original_name}_{server_name}"
            self.name_conflict_resolution[original_name] += 1
        else:
            # 首次出现，记录
            self.name_conflict_resolution[original_name] = 1
            unique_name = standard_name
        
        return unique_name
    
    async def close(self):
        """关闭所有连接"""
        logger.info("🔌 关闭所有MCP服务器连接")
        await self._exit_stack.aclose()
        self.servers.clear()
        self.tool_mapping.clear()
        self.name_conflict_resolution.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取管理器统计信息"""
        total_tools = sum(len(server.tools) for server in self.servers.values())
        total_prompts = sum(len(server.prompts) for server in self.servers.values())
        
        return {
            "total_servers": len(self.servers),
            "total_tools": total_tools,
            "total_prompts": total_prompts,
            "servers": list(self.servers.keys()),
            "name_conflicts": len([k for k, v in self.name_conflict_resolution.items() if v > 1]),
        }
