# LLM MCP Host 重构模块

## 概述

这是对 `llm_mcp_host.py` 的模块化重构版本，提供了以下增强功能：

1. **向量搜索工具匹配** - 基于用户查询选择最相关的工具（mock实现）
2. **聊天上下文管理** - 基于时间和回合数的上下文过期机制
3. **多MCP服务器支持** - 同时连接和管理多个MCP服务器
4. **MCP提示获取** - 从MCP服务器获取和使用提示

## 模块结构

```
llm_mcp_host_refactor/
├── __init__.py              # 模块导出
├── agent.py                 # 主Agent类
├── context_manager.py       # 上下文管理
├── tool_selector.py         # 工具选择器（向量搜索mock）
├── mcp_manager.py           # MCP服务器管理器
├── prompt_manager.py        # 提示管理器
├── utils.py                 # 工具函数
├── config_example.yaml      # 配置示例
└── README.md                # 本文档
```

## 快速开始

### 1. 安装依赖

确保已安装所需依赖：
```bash
pip install openai mcp
```

### 2. 更新配置

更新 `config.yaml` 以支持新功能：

```yaml
# MCP服务器配置（支持多个服务器）
mcp_servers:
  server1:
    type: "sse"
    url: "http://server1/mcp"
    headers:
      Authorization: "${MCP_AUTH_TOKEN}"
  
  server2:
    type: "stdio"
    command: "python"
    args: ["-m", "mcp_server"]

# 工具选择配置
tool_selection:
  top_k: 3

# 上下文管理配置
context:
  max_turns: 3
  max_time_minutes: 30
```

### 3. 使用重构后的模块

#### 方式一：替换原有导入（推荐）

修改 `main.py` 中的导入：

```python
# 原导入
# from llm_mcp_host import process_llm_host

# 新导入
from llm_mcp_host_refactor import process_llm_host
```

#### 方式二：直接使用新Agent类

```python
from llm_mcp_host_refactor import MCPVoiceAgent
import asyncio

async def main():
    async with MCPVoiceAgent() as agent:
        response = await agent.chat("打开客厅的灯")
        print(f"助手回复: {response}")

if __name__ == "__main__":
    asyncio.run(main())
```

## 功能详解

### 1. 向量搜索工具匹配（Mock）

- **build_index()**: 模拟构建工具向量库
- **search()**: 基于简单文本相似度选择topk最相关工具
- 使用词频向量和余弦相似度计算工具相关性
- 支持工具名称匹配加分

### 2. 聊天上下文管理

- **基于回合数**: 默认保存最近3个回合的对话
- **基于时间**: 默认30分钟后过期
- **智能清理**: 自动清理过期消息，保留系统提示
- **统计信息**: 提供详细的上下文统计

### 3. 多MCP服务器支持

- **统一管理**: 同时连接多个MCP服务器
- **工具映射**: 自动处理同名工具冲突
- **调用路由**: 将工具调用路由到正确的服务器
- **故障隔离**: 单个服务器故障不影响其他服务器

### 4. MCP提示获取

- **提示发现**: 自动从所有服务器发现可用提示
- **内容加载**: 按需加载提示内容
- **上下文整合**: 将MCP提示整合到系统提示中
- **缓存机制**: 缓存已加载的提示内容

## 配置说明

### 向后兼容性

重构模块完全兼容原有配置格式。如果使用旧版单服务器配置：

```yaml
mcp_server:
  type: "sse"
  url: "http://server/mcp"
```

模块会自动将其转换为多服务器格式（服务器名为"default"）。

### 新配置项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `mcp_servers` | MCP服务器列表（字典或列表） | - |
| `tool_selection.top_k` | 每次选择的最相关工具数 | 3 |
| `context.max_turns` | 最大保存对话回合数 | 3 |
| `context.max_time_minutes` | 上下文过期时间（分钟） | 30 |

## API参考

### MCPVoiceAgent 类

#### 主要方法

- `__aenter__()`: 初始化连接
- `__aexit__()`: 清理资源
- `chat(user_text: str) -> str`: 处理用户输入
- `load_prompt(prompt_name: str, **kwargs) -> Optional[str]`: 加载MCP提示
- `clear_context()`: 清空对话上下文

#### 统计方法

- `get_context_stats()`: 获取上下文统计
- `get_tool_stats()`: 获取工具统计
- `get_mcp_stats()`: 获取MCP服务器统计
- `get_prompt_stats()`: 获取提示统计
- `get_agent_stats()`: 获取代理整体统计

### process_llm_host 函数

保持与原有接口完全兼容：

```python
def process_llm_host(text_queue, tts_queue, interrupt_event):
    """
    参数:
    - text_queue: 文本输入队列（STT -> LLM）
    - tts_queue: 文本输出队列（LLM -> TTS）
    - interrupt_event: 中断事件
    """
```

## 性能监控

代理提供详细的性能统计：

- 总对话回合数
- 总工具调用次数
- 错误统计
- 上下文使用情况
- 工具选择效果
- 服务器连接状态

统计信息默认每5轮输出一次到日志。

## 故障排除

### 常见问题

1. **服务器连接失败**
   - 检查服务器配置（URL、命令、参数）
   - 验证认证信息
   - 检查网络连接

2. **工具调用失败**
   - 检查工具参数格式
   - 验证工具权限
   - 查看服务器日志

3. **上下文管理异常**
   - 检查系统时钟同步
   - 验证配置参数有效性

### 日志级别

可以通过配置调整日志级别：

```yaml
advanced:
  log_level: "DEBUG"  # DEBUG, INFO, WARNING, ERROR
```

## 扩展开发

### 添加新功能模块

1. 在相应模块中添加新类或函数
2. 在 `agent.py` 中集成新功能
3. 更新配置解析逻辑
4. 添加测试用例

### 自定义工具选择算法

继承 `ToolSelector` 类并重写 `search()` 方法：

```python
class CustomToolSelector(ToolSelector):
    def search(self, query: str) -> List[ToolInfo]:
        # 实现自定义选择逻辑
        pass
```

### 自定义上下文策略

继承 `ContextManager` 类并重写 `_cleanup()` 方法：

```python
class CustomContextManager(ContextManager):
    def _cleanup(self):
        # 实现自定义清理策略
        pass
```

## 许可证

同主项目许可证。
