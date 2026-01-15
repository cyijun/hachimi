"""
主Agent模块
整合所有功能模块，提供完整的MCP语音代理功能
"""
import asyncio
import json
import traceback
from typing import List, Dict, Any, Optional

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam
from config import config as global_config
from logger import logger

from .utils import parse_server_config, mcp_tools_to_openai_tools
from .context_manager import ContextManager
from .vector_tool_selector import VectorToolSelector as ToolSelector, ToolInfo
from .mcp_manager import MCPServerManager
from .prompt_manager import PromptManager


class MCPVoiceAgent:
    """增强的MCP语音代理，支持多服务器、向量搜索、上下文管理等"""
    
    def __init__(self, config=None):
        """
        初始化MCP语音代理
        
        Args:
            config: 配置对象，如果为None则使用全局配置
        """
        self.config = config or global_config
        
        # 解析配置
        self.llm_config = self.config.llm
        self.system_prompt = self.config.system_prompt
        
        # 工具选择配置
        self.tool_selection_config = self.config.get('tool_selection', {})
        self.top_k = self.tool_selection_config.get('top_k', 3)
        
        # 上下文配置
        self.context_config = self.config.get('context', {})
        self.max_turns = self.context_config.get('max_turns', 3)
        self.max_time_minutes = self.context_config.get('max_time_minutes', 30)
        self.enable_summarization = self.context_config.get('enable_summarization', False)
        self.summary_role = self.context_config.get('summary_role', 'user')

        # 总结配置
        self.summarization_config = self.context_config.get('summarization', {})
        self.max_summary_tokens = self.summarization_config.get('max_summary_tokens', 200)
        self.summary_prompt = self.summarization_config.get('summary_prompt',
            "请用中文简洁总结以下对话历史，保留关键信息，总结长度不超过{max_tokens}个token：")
        
        # 初始化组件
        self.openai_client = AsyncOpenAI(
            api_key=self.llm_config["api_key"],
            base_url=self.llm_config.get("base_url")
        )
        
        self.context_manager = ContextManager(
            max_turns=self.max_turns,
            max_time_seconds=self.max_time_minutes * 60,
            system_prompt=self.system_prompt,
            enable_summarization=self.enable_summarization,
            summary_role=self.summary_role,
            max_summary_tokens=self.max_summary_tokens,
            summary_prompt=self.summary_prompt,
            openai_client=self.openai_client  # 传递LLM客户端用于生成总结
        )
        
        self.tool_selector = ToolSelector(top_k=self.top_k, config=self.tool_selection_config)
        self.mcp_manager = MCPServerManager()
        self.prompt_manager = PromptManager(system_prompt=self.system_prompt)
        
        # 工具列表（OpenAI格式）
        self.openai_tools: List[ChatCompletionToolParam] = []
        
        # 性能统计
        self.stats = {
            "total_turns": 0,
            "total_tool_calls": 0,
            "total_errors": 0,
        }
    
    async def __aenter__(self):
        """初始化连接"""
        logger.info("🚀 初始化增强版MCP语音代理...")
        
        # 解析服务器配置
        server_configs = parse_server_config({
            "mcp_server": self.config.mcp_server,
            "mcp_servers": self.config.get("mcp_servers", {})
        })
        
        # 连接所有服务器
        connection_tasks = []
        for server_name, server_config in server_configs.items():
            task = self.mcp_manager.add_server(server_name, server_config)
            connection_tasks.append(task)
        
        # 等待所有连接完成
        results = await asyncio.gather(*connection_tasks, return_exceptions=True)
        
        # 统计成功连接的服务器
        successful_connections = sum(1 for r in results if r is True)
        logger.info(f"✅ 成功连接 {successful_connections}/{len(server_configs)} 个MCP服务器")
        
        # 获取所有工具
        all_tools = await self.mcp_manager.get_all_tools()
        logger.info(f"🛠️  总共加载 {len(all_tools)} 个工具")
        
        # 构建工具索引
        self.tool_selector.build_index(all_tools)
        
        # 转换为OpenAI工具格式
        self._update_openai_tools(all_tools)
        
        # 获取MCP提示
        mcp_prompts = await self.mcp_manager.get_all_prompts()
        if mcp_prompts:
            self.prompt_manager.add_mcp_prompts(mcp_prompts)
            logger.info(f"📝 加载 {len(mcp_prompts)} 个MCP提示")
        
        # 更新系统提示以包含MCP上下文
        combined_prompt = self.prompt_manager.get_combined_prompt(include_mcp_context=True)
        self.context_manager.clear()
        self.context_manager.add_message(
            {"role": "system", "content": combined_prompt},
            is_system=True
        )
        
        logger.info("🎉 增强版MCP语音代理就绪")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """清理资源"""
        logger.info("🔌 关闭增强版MCP语音代理...")
        await self.mcp_manager.close()
        logger.info("👋 增强版MCP语音代理已关闭")
    
    async def chat(self, user_text: str) -> str:
        """
        处理用户输入，返回助手响应
        
        Args:
            user_text: 用户输入文本
            
        Returns:
            助手响应文本
        """
        if not user_text or not user_text.strip():
            return ""
        
        logger.info(f"👂 听到: {user_text}")
        self.stats["total_turns"] += 1
        
        # 添加到上下文
        self.context_manager.add_message({"role": "user", "content": user_text})
        
        # 处理LLM回合
        final_response = await self._process_llm_turn(user_text)
        
        logger.info(f"🗣️  回复: {final_response}")
        return final_response
    
    async def _process_llm_turn(self, user_query: str) -> str:
        """处理单个LLM回合，支持多步工具调用"""
        # 根据用户查询选择最相关的工具
        relevant_tools = self.tool_selector.search(user_query)
        
        # 如果找到相关工具，使用它们；否则使用所有工具
        tools_to_use = self.openai_tools
        if relevant_tools:
            # 只使用相关工具
            relevant_tool_names = [tool.name for tool in relevant_tools]
            tools_to_use = [
                tool for tool in self.openai_tools
                if tool["function"]["name"] in relevant_tool_names
            ]
            logger.info(f"🔍 选择了 {len(tools_to_use)} 个相关工具: {relevant_tool_names}")
        
        while True:
            # 获取当前消息
            messages = self.context_manager.get_messages()
            
            # 调用LLM
            response = await self.openai_client.chat.completions.create(
                model=self.llm_config["model"],
                messages=messages,
                tools=tools_to_use if tools_to_use else None,
                temperature=self.llm_config.get("temperature", 0.7),
            )
            
            response_message = response.choices[0].message
            self.context_manager.add_message(response_message.to_dict())
            
            # 情况A: LLM决定调用工具
            if response_message.tool_calls:
                logger.info(
                    f"🤖 需要执行动作: {[t.function.name for t in response_message.tool_calls]}"
                )
                self.stats["total_tool_calls"] += len(response_message.tool_calls)
                
                for tool_call in response_message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        fn_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError as e:
                        content_str = f"参数解析错误: {str(e)}"
                        self.stats["total_errors"] += 1
                    else:
                        try:
                            # 执行MCP工具
                            result = await self.mcp_manager.call_tool(tool_name, fn_args)
                            
                            # 转换工具结果为字符串
                            content_str = ""
                            if result.content:
                                for item in result.content:
                                    if item.type == "text":
                                        content_str += item.text
                                    else:
                                        content_str += str(item)
                            else:
                                content_str = "成功"
                        except Exception as e:
                            content_str = f"工具执行错误: {str(e)}"
                            self.stats["total_errors"] += 1
                            logger.error(f"❌ 工具执行失败 {tool_name}: {e}")
                    
                    # 将工具结果返回给LLM
                    self.context_manager.add_message({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": content_str,
                    })
                
                # 循环继续，LLM将看到工具结果并生成新响应
            
            # 情况B: LLM生成最终文本响应
            else:
                return response_message.content or ""
    
    def _update_openai_tools(self, tools: List[ToolInfo]):
        """更新OpenAI工具列表"""
        # 创建模拟的MCP工具结果
        class MockTool:
            def __init__(self, name, description, inputSchema):
                self.name = name
                self.description = description
                self.inputSchema = inputSchema
        
        class MockToolsResult:
            def __init__(self, tools):
                self.tools = tools
        
        # 构建模拟工具列表
        mock_tools = []
        for tool in tools:
            mock_tool = MockTool(
                name=tool.name,
                description=tool.description,
                inputSchema=tool.parameters
            )
            mock_tools.append(mock_tool)
        
        # 转换为OpenAI格式
        mock_result = MockToolsResult(mock_tools)
        self.openai_tools = mcp_tools_to_openai_tools(mock_result)
    
    async def load_prompt(self, prompt_name: str, **kwargs) -> Optional[str]:
        """加载MCP提示"""
        return await self.prompt_manager.load_prompt(prompt_name, self.mcp_manager, **kwargs)
    
    def get_context_stats(self) -> Dict[str, Any]:
        """获取上下文统计信息"""
        return self.context_manager.get_stats()
    
    def get_tool_stats(self) -> Dict[str, Any]:
        """获取工具统计信息"""
        return self.tool_selector.get_stats()
    
    def get_mcp_stats(self) -> Dict[str, Any]:
        """获取MCP统计信息"""
        return self.mcp_manager.get_stats()
    
    def get_prompt_stats(self) -> Dict[str, Any]:
        """获取提示统计信息"""
        return self.prompt_manager.get_stats()
    
    def get_agent_stats(self) -> Dict[str, Any]:
        """获取代理整体统计信息"""
        return {
            **self.stats,
            "context": self.get_context_stats(),
            "tools": self.get_tool_stats(),
            "mcp": self.get_mcp_stats(),
            "prompts": self.get_prompt_stats(),
        }
    
    def clear_context(self):
        """清空对话上下文"""
        self.context_manager.clear()
        logger.info("🧹 对话上下文已清空")


def process_llm_host(text_queue, tts_queue, interrupt_event):
    """
    MCP Host主进程函数
    保持与原有接口兼容
    
    Args:
        text_queue: 文本输入队列（STT -> LLM）
        tts_queue: 文本输出队列（LLM -> TTS）
        interrupt_event: 中断事件
    """
    logger.info("[LLM] 增强版MCP Host进程启动...")
    
    async def voice_assistant_loop(text_queue, tts_queue, interrupt_event):
        async with MCPVoiceAgent() as agent:
            while not interrupt_event.is_set():
                try:
                    # 1. 从STT获取文本
                    stt_text = text_queue.get()
                    if interrupt_event.is_set():
                        break
                    
                    # 2. 调用MCP代理
                    tts_text = await agent.chat(stt_text)
                    
                    # 3. 发送到TTS
                    tts_queue.put(tts_text)
                    
                    # 记录统计信息（每5轮）
                    if agent.stats["total_turns"] % 5 == 0:
                        stats = agent.get_agent_stats()
                        logger.info(f"📊 代理统计: {stats}")
                    
                    logger.info("-" * 50)
                    
                except Exception as e:
                    logger.error(f"❌ 处理循环错误: {e}")
                    print(traceback.format_exc())
                    if interrupt_event.is_set():
                        break
    
    try:
        asyncio.run(voice_assistant_loop(text_queue, tts_queue, interrupt_event))
    except KeyboardInterrupt:
        logger.info("🛑 收到中断信号，停止LLM Host进程")
    except Exception as e:
        logger.error(f"❌ LLM Host运行时错误: {e}")
    finally:
        logger.info("[LLM] 增强版MCP Host进程结束")
