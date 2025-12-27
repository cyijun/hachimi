import asyncio
import json
import os
import sys
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager, AsyncExitStack

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

from config import config


# --- 工具转换逻辑 ---
def mcp_tools_to_openai_tools(mcp_list_tools_result) -> List[ChatCompletionToolParam]:
    openai_tools: List[ChatCompletionToolParam] = []
    for tool in mcp_list_tools_result.tools:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                },
            }
        )
    return openai_tools


# --- 传输层工厂 ---
@asynccontextmanager
async def mcp_transport_factory(config_dict: Dict[str, Any]):
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
        raise ValueError(f"Unsupported MCP server type: {server_type}")


class MCPVoiceAgent:
    def __init__(self):
        self.mcp_config = config.mcp_server
        self.llm_config = config.llm

        # 1. 配置系统提示词 (System Prompt)
        self.system_prompt = config.system_prompt

        self.openai_client = AsyncOpenAI(
            api_key=self.llm_config["api_key"], base_url=self.llm_config.get("base_url")
        )

        # 初始化消息历史
        self.messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": self.system_prompt}
        ]

        self.session: Optional[ClientSession] = None
        self.openai_tools: List[ChatCompletionToolParam] = []
        self._exit_stack = AsyncExitStack()

    # --- 上下文管理器：负责连接的建立与保持 ---
    async def __aenter__(self):
        """初始化 MCP 连接和 Session"""
        print(f"🔌 Connecting to MCP Server...")

        # 使用 ExitStack 管理嵌套的上下文
        read, write = await self._exit_stack.enter_async_context(
            mcp_transport_factory(self.mcp_config)
        )

        self.session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )

        await self.session.initialize()

        # 加载工具
        tools_result = await self.session.list_tools()
        self.openai_tools = mcp_tools_to_openai_tools(tools_result)
        print(f"🛠️  MCP Agent Ready. Loaded {len(self.openai_tools)} tools.")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """清理资源，断开连接"""
        print("🔌 Disconnecting MCP Agent...")
        await self._exit_stack.aclose()

    # --- 核心功能：输入文本 -> 执行操作 -> 输出回复文本 ---
    async def chat(self, user_text: str) -> str:
        """
        对应流程图中的 E -> F -> G 的输入输出接口
        Input: STT 转换后的文本
        Output: 发送给 TTS 的文本
        """
        if not user_text or not user_text.strip():
            return ""

        print(f"\n👂 Hearing: {user_text}")
        self.messages.append({"role": "user", "content": user_text})

        # 进入 LLM 处理循环（处理可能的多次工具调用）
        final_response_text = await self._process_llm_turn()

        print(f"🗣️  Speaking: {final_response_text}")
        return final_response_text

    async def _process_llm_turn(self) -> str:
        """处理单轮对话及多步工具调用，返回最终给用户的文本"""
        while True:
            response = await self.openai_client.chat.completions.create(
                model=self.llm_config["model"],
                messages=self.messages,
                tools=self.openai_tools if self.openai_tools else None,
                temperature=self.llm_config.get("temperature", 0.7),
            )

            response_message = response.choices[0].message
            self.messages.append(response_message)

            # 情况 A: LLM 决定调用工具
            if response_message.tool_calls:
                print(
                    f"🤖 Action required: {[t.function.name for t in response_message.tool_calls]}"
                )

                for tool_call in response_message.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments)

                    try:
                        # 执行 MCP 工具
                        result = await self.session.call_tool(
                            fn_name, arguments=fn_args
                        )

                        # 将工具结果转为字符串供 LLM 理解
                        content_str = ""
                        if result.content:
                            for item in result.content:
                                if item.type == "text":
                                    content_str += item.text
                                else:
                                    content_str += str(item)
                        else:
                            content_str = "Success"
                    except Exception as e:
                        content_str = f"Error executing tool: {str(e)}"

                    # 将工具结果回传给 LLM
                    self.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": content_str,
                        }
                    )
                # 循环继续，LLM 将看到工具结果并生成新的回复

            # 情况 B: LLM 生成了最终文本回复
            else:
                return response_message.content


def process_llm_host(text_queue, tts_queue, interrupt_event):
    """
    作为 MCP Host，接收文本，管理上下文，调用工具，并将生成的文本流式传输给 TTS。
    """
    print("[LLM] 进程启动...")

    async def voice_assistant_loop(text_queue, tts_queue, interrupt_event):
        # 使用 config 模块获取配置
        # 使用 context manager 保持 MCP 连接
        async with MCPVoiceAgent() as agent:
            while True:
                # 1. (流程 D->E) 从 STT 获取文本
                stt_text = text_queue.get()

                # 2. (流程 E->F) 调用 MCP Agent
                tts_text = await agent.chat(stt_text)

                # 3. (流程 F->G) 发送给 TTS
                tts_queue.put(tts_text)

                print("-" * 50)

    try:
        asyncio.run(voice_assistant_loop(text_queue, tts_queue, interrupt_event))
    except Exception as e:
        print(f"运行出错: {e}")
