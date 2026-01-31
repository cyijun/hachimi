# LLM MCP Host Module

## Overview

This is a modular MCP (Model Context Protocol) host implementation for the Hachimi voice assistant. It provides enhanced features including:

1. **Vector-based Tool Selection** - Intelligently selects the most relevant tools for user queries using BGE-M3 embeddings
2. **Context Management** - Advanced conversation context with time-based and turn-based expiration, plus optional LLM-based summarization
3. **Multi-MCP Server Support** - Simultaneous connection and management of multiple MCP servers
4. **MCP Prompt Management** - Discover and use MCP prompts from connected servers

## Module Structure

```
src/llm_mcp_host/
├── __init__.py               # Module exports and initialization
入口：所有公共API的导出点
├── agent.py                  # Main MCPVoiceAgent class
主代理类，整合所有功能模块
├── context_manager.py         # Context management with expiration & summarization
上下文管理，支持时间/回合过期和LLM总结
├── vector_tool_selector.py    # Vector-based tool selection using embeddings
向量搜索工具选择器，基于BGE-M3 embedding
├── tool_selector.py          # Base tool selector interface
工具选择器基类定义
├── mcp_manager.py            # Multi-server MCP manager
MCP服务器管理器，支持多服务器连接
├── prompt_manager.py         # MCP prompt discovery & loading
提示管理器，管理MCP提示和系统提示整合
├── utils.py                  # Utility functions
工具函数和辅助方法
├── config_example.yaml        # Configuration example
配置示例文件
└── README.md                 # This document
```

## Quick Start

### 1. Install Dependencies

Ensure you have the required dependencies installed:

```bash
pip install openai mcp numpy requests
```

### 2. Configuration

The module uses `config.yaml` in the project root. Key configuration sections:

```yaml
# MCP servers configuration (supports multiple servers)
mcp_servers:
  smart_home:
    type: "sse"
    url: "http://your-mcp-server:8123/mcp_server/sse"
    headers:
      Authorization: "${MCP_AUTH_TOKEN}"

# Tool selection configuration
tool_selection:
  top_k: 10  # Select top 10 most relevant tools
  use_vector_search: true
  embedding:
    url: "https://api.siliconflow.cn/v1/embeddings"
    model: "BAAI/bge-m3"
    api_key: "${SILICONFLOW_API_KEY}"
    dimensions: 1024

# Context management configuration
context:
  max_turns: 10  # Keep last 10 conversation turns
  max_time_minutes: 30  # Expire context after 30 minutes
  enable_summarization: true  # Enable LLM-based summarization
  summary_role: "user"
  summarization:
    max_summary_tokens: 200
    summary_prompt: "请用中文简洁总结以下对话历史，保留关键信息，总结长度不超过{max_tokens}个token："
```

### 3. Usage

#### Method 1: Using with main.py (Default)

The module is already integrated with the main voice assistant system:

```bash
python main.py
```

#### Method 2: Using MCPVoiceAgent directly

```python
import asyncio
from src.llm_mcp_host import MCPVoiceAgent

async def main():
    async with MCPVoiceAgent() as agent:
        response = await agent.chat("打开客厅的灯")
        print(f"Assistant response: {response}")

if __name__ == "__main__":
    asyncio.run(main())
```

#### Method 3: Using individual components

```python
from src.llm_mcp_host import MCPServerManager, VectorToolSelector, ContextManager
import asyncio

async def main():
    # Create components
    mcp_manager = MCPServerManager()
    tool_selector = VectorToolSelector(top_k=5)
    context_manager = ContextManager(max_turns=5)

    # Connect to MCP servers
    await mcp_manager.add_server("my_server", {
        "type": "sse",
        "url": "http://server/mcp",
        "headers": {"Authorization": "your-token"}
    })

    # Get and index tools
    tools = await mcp_manager.get_all_tools()
    tool_selector.build_index(tools)

    # Use tool selector
    relevant_tools = tool_selector.search("控制灯光")

if __name__ == "__main__":
    asyncio.run(main())
```

## Feature Details

### 1. Vector-based Tool Selection

Uses BGE-M3 embeddings to intelligently select the most relevant tools for each query:

**Key Features:**
- **Embedding API Integration**: Uses SiliconFlow's BAAI/bge-m3 model for embeddings
- **Cosine Similarity**: Calculates similarity between user query and tool descriptions
- **Tool Name Bonus**: Additional scoring for tools with matching names
- **Fallback Mechanism**: Falls back to frequency-based search if embedding API fails
- **Query Caching**: Caches embedding vectors for repeated queries

**Implementation:**

```python
from src.llm_mcp_host import VectorToolSelector, ToolInfo

# Initialize selector
selector = VectorToolSelector(top_k=5, config={
    'embedding': {
        'url': 'https://api.siliconflow.cn/v1/embeddings',
        'model': 'BAAI/bge-m3',
        'api_key': 'your-api-key',
        'dimensions': 1024
    }
})

# Build index with tools
tools = [ToolInfo(...), ...]
selector.build_index(tools)

# Search for relevant tools
relevant = selector.search("打开空调")
```

**Configuration:**

```yaml
tool_selection:
  top_k: 10
  use_vector_search: true
  embedding:
    url: "https://api.siliconflow.cn/v1/embeddings"
    model: "BAAI/bge-m3"
    api_key: "${SILICONFLOW_API_KEY}"
    dimensions: 1024
```

### 2. Context Management

Advanced conversation context with automatic expiration and optional LLM summarization:

**Key Features:**
- **Turn-based Expiration**: Keeps only recent N conversation turns
- **Time-based Expiration**: Automatically expires old messages after N minutes
- **LLM Summarization**: Optionally summarizes old conversation turns to preserve key information
- **System Prompt Preservation**: System prompts are never expired
- **Smart Cleanup**: Automatic cleanup of expired messages while preserving context

**Implementation:**

```python
from src.llm_mcp_host import ContextManager
from openai import AsyncOpenAI

# Initialize with OpenAI client for summarization
openai_client = AsyncOpenAI(api_key="your-key", base_url="your-url")

context = ContextManager(
    max_turns=10,
    max_time_seconds=1800,  # 30 minutes
    system_prompt="You are a helpful assistant.",
    enable_summarization=True,
    summary_role="user",
    max_summary_tokens=200,
    summary_prompt="请用中文简洁总结以下对话历史，保留关键信息，总结长度不超过{max_tokens}个token：",
    openai_client=openai_client
)

# Add messages
context.add_message({"role": "user", "content": "Hello"})
context.add_message({"role": "assistant", "content": "Hi there!"})

# Get current context
messages = context.get_messages()

# Clear context
context.clear(keep_system=True)
```

**Configuration:**

```yaml
context:
  max_turns: 10
  max_time_minutes: 30
  enable_summarization: true
  summary_role: "user"
  summarization:
    max_summary_tokens: 200
    summary_prompt: "请用中文简洁总结以下对话历史，保留关键信息，总结长度不超过{max_tokens}个token："
```

**Summarization Strategy:**

1. Messages exceeding turn limit trigger summarization
2. LLM generates concise summary preserving key information
3. Summary message inserted as a new message in context
4. If LLM summarization fails, falls back to simple text merger

### 3. Multi-MCP Server Support

Connect to multiple MCP servers simultaneously:

**Key Features:**
- **Unified Management**: Connect to multiple servers (SSE or Stdio)
- **Tool Discovery**: Automatic tool discovery from all servers
- **Tool Routing**: Automatic tool call routing to correct server
- **Conflict Resolution**: Handles tools with same names across servers
- **Fault Isolation**: Single server failure doesn't affect others
- **Prompt Discovery**: Discover and use MCP prompts from all servers

**Implementation:**

```python
from src.llm_mcp_host import MCPServerManager
import asyncio

async def main():
    manager = MCPServerManager()

    # Add multiple servers
    await manager.add_server("smart_home", {
        "type": "sse",
        "url": "http://home-server/mcp",
        "headers": {"Authorization": "token1"}
    })

    await manager.add_server("weather", {
        "type": "stdio",
        "command": "python",
        "args": ["-m", "weather_mcp"]
    })

    # Get all tools from all servers
    all_tools = await manager.get_all_tools()

    # Call a tool (automatically routed)
    result = await manager.call_tool("smart_home:turn_on_light", {"room": "living_room"})

    # Get prompts
    prompts = await manager.get_all_prompts()

if __name__ == "__main__":
    asyncio.run(main())
```

**Configuration:**

```yaml
mcp_servers:
  smart_home:
    type: "sse"
    url: "http://server:8123/mcp_server/sse"
    headers:
      Authorization: "${MCP_AUTH_TOKEN}"

  weather_service:
    type: "stdio"
    command: "python"
    args: ["-m", "weather_mcp"]
```

### 4. MCP Prompt Management

Discover and manage MCP prompts from connected servers:

**Key Features:**
- **Prompt Discovery**: Automatic discovery of available prompts
- **Lazy Loading**: Load prompt content on demand
- **Context Integration**: Integrate MCP prompts into system prompt
- **Caching**: Cache loaded prompt content
- **Custom Prompts**: Add custom prompts programmatically

**Implementation:**

```python
from src.llm_mcp_host import PromptManager

# Initialize
prompt_mgr = PromptManager(system_prompt="You are a helpful assistant.")

# Add MCP prompts (automatically done during agent initialization)
prompt_mgr.add_mcp_prompts([
    {"name": "weather_query", "server": "weather", "description": "Query weather", "arguments": {}}
])

# Load prompt content
content = await prompt_mgr.load_prompt("weather_query", mcp_manager)

# Get combined prompt (system + MCP context)
combined = prompt_mgr.get_combined_prompt(include_mcp_context=True)

# Add custom prompt
prompt_mgr.add_custom_prompt(
    name="custom_task",
    content="This is a custom prompt template.",
    description="Custom prompt for specific task",
    server="custom"
)
```

## API Reference

### MCPVoiceAgent Class

Main agent class that integrates all components.

**Initialization:**

```python
MCPVoiceAgent(config=None)
```

**Methods:**

| Method | Description | Returns |
|--------|-------------|---------|
| `async __aenter__()` | Initialize connections and prepare agent | Self |
| `async __aexit__()` | Clean up resources | None |
| `async chat(user_text: str)` | Process user input and return response | str |
| `async load_prompt(prompt_name: str, **kwargs)` | Load MCP prompt | Optional[str] |
| `clear_context()` | Clear conversation context | None |
| `get_context_stats()` | Get context statistics | Dict[str, Any] |
| `get_tool_stats()` | Get tool selection statistics | Dict[str, Any] |
| `get_mcp_stats()` | Get MCP server statistics | Dict[str, Any] |
| `get_prompt_stats()` | Get prompt statistics | Dict[str, Any] |
| `get_agent_stats()` | Get overall agent statistics | Dict[str, Any] |

**Example:**

```python
async with MCPVoiceAgent() as agent:
    response = await agent.chat("打开客厅的灯")
    stats = agent.get_agent_stats()
    print(stats)
```

### VectorToolSelector Class

Vector-based tool selection using embeddings.

**Initialization:**

```python
VectorToolSelector(top_k: int = 3, config: Dict[str, Any] = None)
```

**Methods:**

| Method | Description | Returns |
|--------|-------------|---------|
| `build_index(tools: List[ToolInfo])` | Build vector index for tools | None |
| `search(query: str)` | Search for relevant tools | List[ToolInfo] |
| `search_with_scores(query: str)` | Search with similarity scores | List[Tuple[ToolInfo, float]] |
| `clear_cache()` | Clear query vector cache | None |
| `get_stats()` | Get selector statistics | Dict[str, Any] |

### ContextManager Class

Advanced conversation context management.

**Initialization:**

```python
ContextManager(
    max_turns: int = 3,
    max_time_seconds: int = 1800,
    system_prompt: Optional[str] = None,
    enable_summarization: bool = False,
    summary_role: str = "user",
    max_summary_tokens: int = 200,
    summary_prompt: str = "请用中文简洁总结以下对话历史，保留关键信息，总结长度不超过{max_tokens}个token：",
    openai_client: Optional[Any] = None
)
```

**Methods:**

| Method | Description | Returns |
|--------|-------------|---------|
| `add_message(message: dict, is_system: bool = False)` | Add message to context | None |
| `get_messages()` | Get all current messages | List[ChatCompletionMessageParam] |
| `clear(keep_system: bool = True)` | Clear context | None |
| `get_stats()` | Get context statistics | Dict[str, Any] |

### MCPServerManager Class

Manage multiple MCP servers.

**Initialization:**

```python
MCPServerManager()
```

**Methods:**

| Method | Description | Returns |
|--------|-------------|---------|
| `async add_server(server_name: str, config: Dict[str, Any])` | Connect to MCP server | bool |
| `async get_all_tools()` | Get all tools from all servers | List[ToolInfo] |
| `async get_all_prompts()` | Get all prompts from all servers | List[Dict[str, Any]] |
| `async call_tool(tool_name: str, arguments: Dict[str, Any])` | Execute tool | Any |
| `async get_prompt(prompt_name: str, server_name: Optional[str], **kwargs)` | Get prompt content | Optional[str] |
| `async close()` | Close all connections | None |
| `get_stats()` | Get manager statistics | Dict[str, Any] |

### PromptManager Class

Manage system prompts and MCP prompts.

**Initialization:**

```python
PromptManager(system_prompt: str = "")
```

**Methods:**

| Method | Description | Returns |
|--------|-------------|---------|
| `add_mcp_prompts(prompts: List[Dict[str, Any]])` | Add MCP prompts | None |
| `async load_prompt(prompt_name: str, mcp_manager, **kwargs)` | Load prompt content | Optional[str] |
| `get_combined_prompt(include_mcp_context: bool = True)` | Get combined prompt | str |
| `get_prompt_info(prompt_name: str)` | Get prompt information | Optional[PromptInfo] |
| `get_all_prompt_names()` | Get all prompt names | List[str] |
| `clear_loaded_prompts()` | Clear loaded prompts | None |
| `update_system_prompt(new_prompt: str)` | Update system prompt | None |
| `add_custom_prompt(name, content, description, server)` | Add custom prompt | None |
| `get_stats()` | Get manager statistics | Dict[str, Any] |

### Utility Functions

**mcp_tools_to_openai_tools(tool_result)**

Convert MCP tools to OpenAI tool format.

**parse_server_config(config_dict)**

Parse server configuration (handles backward compatibility).

**create_tool_identifier(server_name, tool_name)**

Create unique tool identifier.

**mcp_transport_factory(config)**

Create MCP transport layer (SSE or Stdio).

## Configuration Reference

### Complete Configuration Example

```yaml
# MCP servers configuration (supports multiple servers)
mcp_servers:
  smart_home:
    type: "sse"
    url: "http://server:8123/mcp_server/sse"
    headers:
      Authorization: "${MCP_AUTH_TOKEN}"

  weather_service:
    type: "stdio"
    command: "python"
    args: ["-m", "weather_mcp"]
    env:
      WEATHER_API_KEY: "${WEATHER_API_KEY}"

# Tool selection configuration
tool_selection:
  top_k: 10  # Number of relevant tools to select
  use_vector_search: true
  embedding:
    url: "https://api.siliconflow.cn/v1/embeddings"
    model: "BAAI/bge-m3"
    api_key: "${SILICONFLOW_API_KEY}"
    dimensions: 1024
    timeout: 10

# Context management configuration
context:
  max_turns: 10  # Maximum conversation turns to keep
  max_time_minutes: 30  # Context expiration time
  enable_summarization: true  # Enable LLM summarization
  summary_role: "user"  # Summary message role
  summarization:
    max_summary_tokens: 200
    summary_prompt: "请用中文简洁总结以下对话历史，保留关键信息，总结长度不超过{max_tokens}个token："

# LLM configuration
llm:
  api_key: "${DEEPSEEK_API_KEY}"
  base_url: "https://api.deepseek.com"
  model: "deepseek-chat"
  temperature: 0.7

# System prompt
system_prompt: "你是一个智能家居语音助手。你的回答必须只有一两句话且口语化，适合语音播报。"
```

### Backward Compatibility

The module supports the old single-server configuration format:

```yaml
mcp_server:
  type: "sse"
  url: "http://server/mcp"
  headers:
    Authorization: "${MCP_AUTH_TOKEN}"
```

This will automatically be converted to multi-server format with server name "default".

## Performance Monitoring

The agent provides detailed performance statistics:

```python
stats = agent.get_agent_stats()
```

**Statistics include:**
- `total_turns`: Total conversation turns
- `total_tool_calls`: Total tool executions
- `total_errors`: Total error count
- `context`: Context usage statistics
- `tools`: Tool selection statistics
- `mcp`: MCP server connection status
- `prompts`: Prompt management statistics

**Statistics are logged every N turns** (configurable via `advanced.monitoring.stats_interval_turns`).

## Troubleshooting

### Common Issues

1. **MCP Server Connection Failed**
   - Check server configuration (URL, command, args)
   - Verify authentication headers/tokens
   - Check network connectivity
   - Ensure MCP server is running

2. **Tool Execution Failed**
   - Check tool parameter format
   - Verify tool permissions
   - Check MCP server logs
   - Ensure tool exists in server

3. **Embedding API Errors**
   - Verify SiliconFlow API key is correct
   - Check API quota and limits
   - Ensure network connectivity to embedding API
   - System will fallback to frequency-based search

4. **Context Summarization Issues**
   - Ensure LLM client is properly configured
   - Check LLM API key and access
   - Verify summary prompt template is valid
   - System will use fallback text merger if LLM fails

### Logging

Adjust log level via configuration:

```yaml
advanced:
  log_level: "DEBUG"  # DEBUG, INFO, WARNING, ERROR
```

## Extension Development

### Custom Tool Selector

Inherit `VectorToolSelector` and override methods:

```python
from src.llm_mcp_host.vector_tool_selector import VectorToolSelector, ToolInfo
from typing import List

class CustomToolSelector(VectorToolboxSelector):
    def search(self, query: str) -> List[ToolInfo]:
        # Implement custom selection logic
        # Use self.tools to access all tools
        # Use self.tool_vectors to access embeddings
        return super().search(query)  # or custom logic
```

### Custom Context Strategy

Inherit `ContextManager` and override methods:

```python
from src.llm_mcp_host.context_manager import ContextManager

class CustomContextManager(ContextManager):
    def _cleanup(self):
        # Implement custom cleanup strategy
        super()._cleanup()
```

### Adding New Features

1. Add new classes/functions to appropriate modules
2. Integrate in `agent.py`
3. Update configuration parsing in `utils.py`
4. Add tests in `tests/` directory
5. Update this documentation

## Architecture Notes

### Async/Await Pattern

The module extensively uses `asyncio` for asynchronous operations:
- MCP server connections are established concurrently
- Tool calls are asynchronous
- LLM calls are asynchronous
- Use `async with` for resource management

### Error Handling

- MCP server failures are isolated (doesn't affect other servers)
- Embedding API failures trigger fallback mechanisms
- LLM summarization failures use text-based fallback
- All errors are logged with context

### Memory Management

- Query embedding vectors are cached (limited cache size)
- Context messages are automatically cleaned up
- MCP connections are properly closed on exit
- Use `clear_cache()` and `clear()` for manual cleanup

## License

Same as the main Hachimi project license.

## Contributing

When contributing to this module:

1. Follow existing code style (see AGENTS.md)
2. Add type hints to all functions and methods
3. Include docstrings for all public APIs
4. Update this README for user-facing changes
5. Add tests for new functionality
6. Ensure backward compatibility when possible
