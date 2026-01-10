"""
工具函数模块
包含MCP工具转换、配置解析等通用函数
"""
import json
import os
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from openai.types.chat import ChatCompletionToolParam
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client


# --- Tool conversion logic ---
def mcp_tools_to_openai_tools(mcp_list_tools_result) -> List[ChatCompletionToolParam]:
    """将MCP工具转换为OpenAI工具格式"""
    openai_tools: List[ChatCompletionToolParam] = []
    for tool in mcp_list_tools_result.tools:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            }
        )
    return openai_tools


# --- Transport layer factory ---
@asynccontextmanager
async def mcp_transport_factory(config_dict: Dict[str, Any]):
    """MCP传输层工厂，支持stdio和sse两种类型"""
    server_type = config_dict.get("type", "stdio")
    
    if server_type == "stdio":
        server_params = StdioServerParameters(
            command=config_dict["command"],
            args=config_dict.get("args", []),
            env={**os.environ, **config_dict.get("env", {})},
        )
        async with stdio_client(server_params) as streams:
            yield streams
            
    elif server_type == "sse":
        url = config_dict["url"]
        headers = config_dict.get("headers", {})
        async with sse_client(url=url, headers=headers) as streams:
            yield streams
            
    else:
        raise ValueError(f"不支持的MCP服务器类型: {server_type}")


def parse_server_config(config_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    解析MCP服务器配置
    支持旧版单服务器配置和新版多服务器配置
    """
    servers = {}
    
    # 新版多服务器配置格式
    if "mcp_servers" in config_data:
        mcp_servers = config_data["mcp_servers"]
        if isinstance(mcp_servers, dict):
            # 格式: {server_name: config}
            for server_name, server_config in mcp_servers.items():
                servers[server_name] = server_config
        elif isinstance(mcp_servers, list):
            # 格式: [config1, config2]
            for i, server_config in enumerate(mcp_servers):
                server_name = server_config.get("name", f"server_{i}")
                servers[server_name] = server_config
    # 旧版单服务器配置格式
    elif "mcp_server" in config_data:
        servers["default"] = config_data["mcp_server"]
    
    return servers


def create_tool_identifier(server_name: str, tool_name: str) -> str:
    """创建工具唯一标识符"""
    return f"{server_name}:{tool_name}"


def parse_tool_identifier(tool_id: str) -> tuple[str, str]:
    """解析工具唯一标识符"""
    if ":" in tool_id:
        server_name, tool_name = tool_id.split(":", 1)
        return server_name, tool_name
    return "default", tool_id
