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
from logger import logger


# --- Tool conversion logic ---
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


# --- Transport layer factory ---
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

        # 1. Configure system prompt (System Prompt)
        self.system_prompt = config.system_prompt

        self.openai_client = AsyncOpenAI(
            api_key=self.llm_config["api_key"], base_url=self.llm_config.get("base_url")
        )

        # Initialize message history
        self.messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": self.system_prompt}
        ]

        self.session: Optional[ClientSession] = None
        self.openai_tools: List[ChatCompletionToolParam] = []
        self._exit_stack = AsyncExitStack()

    # --- Context manager: responsible for establishing and maintaining connections ---
    async def __aenter__(self):
        """Initialize MCP connection and Session"""
        logger.info("🔌 Connecting to MCP Server...")

        # Use ExitStack to manage nested contexts
        read, write = await self._exit_stack.enter_async_context(
            mcp_transport_factory(self.mcp_config)
        )

        self.session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )

        await self.session.initialize()

        # Load tools
        tools_result = await self.session.list_tools()
        self.openai_tools = mcp_tools_to_openai_tools(tools_result)
        logger.info(f"🛠️  MCP Agent Ready. Loaded {len(self.openai_tools)} tools.")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources, disconnect"""
        logger.info("🔌 Disconnecting MCP Agent...")
        await self._exit_stack.aclose()

    # --- Core functionality: input text -> execute actions -> output response text ---
    async def chat(self, user_text: str) -> str:
        """
        Corresponds to the input/output interface E -> F -> G in the flowchart
        Input: STT converted text
        Output: Text sent to TTS
        """
        if not user_text or not user_text.strip():
            return ""

        logger.info(f"👂 Hearing: {user_text}")
        self.messages.append({"role": "user", "content": user_text})

        # Enter LLM processing loop (handling possible multiple tool calls)
        final_response_text = await self._process_llm_turn()

        logger.info(f"🗣️  Speaking: {final_response_text}")
        return final_response_text

    async def _process_llm_turn(self) -> str:
        """Process single conversation turn and multi-step tool calls, return final text for user"""
        while True:
            response = await self.openai_client.chat.completions.create(
                model=self.llm_config["model"],
                messages=self.messages,
                tools=self.openai_tools if self.openai_tools else None,
                temperature=self.llm_config.get("temperature", 0.7),
            )

            response_message = response.choices[0].message
            self.messages.append(response_message)

            # Case A: LLM decides to call tools
            if response_message.tool_calls:
                logger.info(
                    f"🤖 Action required: {[t.function.name for t in response_message.tool_calls]}"
                )

                for tool_call in response_message.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments)

                    try:
                        # Execute MCP tool
                        result = await self.session.call_tool(
                            fn_name, arguments=fn_args
                        )

                        # Convert tool result to string for LLM understanding
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

                    # Pass tool result back to LLM
                    self.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": content_str,
                        }
                    )
                # Loop continues, LLM will see tool results and generate new response

            # Case B: LLM generated final text response
            else:
                return response_message.content


def process_llm_host(text_queue, tts_queue, interrupt_event):
    """
    As MCP Host, receive text, manage context, call tools, and stream generated text to TTS.
    """
    logger.info("[LLM] Process starting...")

    async def voice_assistant_loop(text_queue, tts_queue, interrupt_event):
        # Use config module to get configuration
        # Use context manager to maintain MCP connection
        async with MCPVoiceAgent() as agent:
            while True:
                # 1. (Process D->E) Get text from STT
                stt_text = text_queue.get()

                # 2. (Process E->F) Call MCP Agent
                tts_text = await agent.chat(stt_text)

                # 3. (Process F->G) Send to TTS
                tts_queue.put(tts_text)

                logger.info("-" * 50)

    try:
        asyncio.run(voice_assistant_loop(text_queue, tts_queue, interrupt_event))
    except Exception as e:
        logger.error(f"Runtime error: {e}")
