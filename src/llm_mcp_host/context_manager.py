"""
聊天上下文管理模块
实现基于时间和回合数限制的上下文过期机制
"""
import time
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from openai.types.chat import ChatCompletionMessageParam


@dataclass
class TimestampedMessage:
    """带时间戳的消息"""
    message: ChatCompletionMessageParam
    timestamp: float = field(default_factory=time.time)
    turn_count: int = 0  # 消息所在的回合数


class ContextManager:
    """上下文管理器，支持基于时间和回合数的过期机制"""

    def __init__(
        self,
        max_turns: int = 3,
        max_time_seconds: int = 1800,  # 30分钟
        system_prompt: Optional[str] = None,
        enable_summarization: bool = False,
        summary_role: str = "user",
        max_summary_tokens: int = 200,
        summary_prompt: str = "请用中文简洁总结以下对话历史，保留关键信息，总结长度不超过{max_tokens}个token：",
        openai_client: Optional[Any] = None
    ):
        """
        初始化上下文管理器

        Args:
            max_turns: 最大保存回合数（用户+助手为一回合）
            max_time_seconds: 最大时间窗口（秒）
            system_prompt: 系统提示词
            enable_summarization: 是否启用总结机制，当上下文超过回合数时生成总结
            summary_role: 总结消息的角色，默认为"user"
            max_summary_tokens: 总结的最大token数
            summary_prompt: 总结提示词模板，{max_tokens}会被替换为实际值
            openai_client: OpenAI客户端实例，用于生成LLM总结
        """
        self.max_turns = max_turns
        self.max_time_seconds = max_time_seconds
        self.enable_summarization = enable_summarization
        self.summary_role = summary_role
        self.max_summary_tokens = max_summary_tokens
        self.summary_prompt = summary_prompt
        self.openai_client = openai_client
        self.messages: List[TimestampedMessage] = []
        self.current_turn = 0

        # 添加系统提示（如果有）
        if system_prompt:
            self.add_message({"role": "system", "content": system_prompt}, is_system=True)
    
    def add_message(self, message: dict, is_system: bool = False):
        """
        添加消息到上下文
        
        Args:
            message: 消息内容
            is_system: 是否为系统提示（系统提示不过期）
        """
        if is_system:
            # 系统提示放在开头，且不参与回合计数
            timestamped_msg = TimestampedMessage(message=message, turn_count=0)
            # 如果已有系统提示，替换它
            if self.messages and self.messages[0].message["role"] == "system":
                self.messages[0] = timestamped_msg
            else:
                self.messages.insert(0, timestamped_msg)
        else:
            # 用户或助手消息
            if message['role'] in ["user", "assistant"]:
                self.current_turn += 1 if message["role"] == "user" else 0
            
            timestamped_msg = TimestampedMessage(
                message=message,
                turn_count=self.current_turn
            )
            self.messages.append(timestamped_msg)
        
        # 触发清理
        self._cleanup()
    
    def get_messages(self) -> List[ChatCompletionMessageParam]:
        """获取当前所有消息（不含时间戳）"""
        return [msg.message for msg in self.messages]
    
    def clear(self, keep_system: bool = True):
        """清空上下文，可选保留系统提示"""
        if keep_system and self.messages and self.messages[0].message["role"] == "system":
            system_msg = self.messages[0]
            self.messages = [system_msg]
        else:
            self.messages = []
        self.current_turn = 0
    
    def _cleanup(self):
        """清理过期消息，支持总结机制"""
        if len(self.messages) <= 1:  # 只有系统提示或空列表
            return

        current_time = time.time()

        # 分离系统提示和其他消息
        if self.messages[0].message["role"] == "system":
            system_msg = self.messages[0]
            other_msgs = self.messages[1:]
        else:
            system_msg = None
            other_msgs = self.messages[:]

        # 计算最近的回合
        recent_turns = set()
        for msg in reversed(other_msgs):
            if msg.turn_count > self.current_turn - self.max_turns:
                recent_turns.add(msg.turn_count)

        # 分离需要保留的消息和需要处理的消息
        messages_to_keep = []
        messages_to_process = []

        for msg in other_msgs:
            # 跳过总结消息，它们会被特殊处理
            if self._is_summary_message(msg):
                continue

            time_valid = current_time - msg.timestamp <= self.max_time_seconds
            turn_valid = msg.turn_count in recent_turns

            if time_valid and turn_valid:
                messages_to_keep.append(msg)
            else:
                messages_to_process.append(msg)

        # 从保留消息中移除任何现有的总结消息（避免重复）
        messages_to_keep = [msg for msg in messages_to_keep if not self._is_summary_message(msg)]

        # 处理需要处理的消息（过期或超出回合数）
        if messages_to_process and self.enable_summarization:
            # 过滤掉已经是总结的消息（理论上不会有，但为了安全）
            non_summary_messages = [msg for msg in messages_to_process if not self._is_summary_message(msg)]
            if non_summary_messages:
                # 生成总结
                summary_text = self._generate_summary(non_summary_messages)
                if summary_text:
                    # 创建总结消息
                    summary_msg = {
                        "role": self.summary_role,
                        "content": f"历史对话摘要：{summary_text}"
                    }
                    # 将总结消息添加到保留消息之前
                    summary_timestamped = TimestampedMessage(
                        message=summary_msg,
                        turn_count=0  # 总结消息不计入回合
                    )
                    messages_to_keep.insert(0, summary_timestamped)

        # 重新组合消息列表
        new_messages = []
        if system_msg:
            new_messages.append(system_msg)
        new_messages.extend(messages_to_keep)

        self.messages = new_messages

    def _generate_summary(self, messages: List[TimestampedMessage]) -> str:
        """
        生成消息的总结文本，使用LLM生成智能总结

        Args:
            messages: 需要总结的消息列表

        Returns:
            总结文本，如果生成失败则返回空字符串
        """
        if not messages:
            return ""

        # 如果没有LLM客户端，使用简单的回退方案
        if not self.openai_client:
            return self._generate_fallback_summary(messages)

        try:
            # 准备对话历史
            conversation_history = []
            for msg in messages:
                role = msg.message.get("role", "unknown")
                content = msg.message.get("content", "")
                if content:
                    conversation_history.append(f"{role}: {content}")

            if not conversation_history:
                return ""

            # 构建完整的对话历史
            full_conversation = "\n".join(conversation_history)

            # 准备提示词，替换max_tokens占位符
            prompt = self.summary_prompt.format(max_tokens=self.max_summary_tokens)
            full_prompt = f"{prompt}\n\n{full_conversation}"

            # 使用LLM生成总结（同步调用异步方法）
            summary = asyncio.run(self._generate_summary_with_llm(full_prompt))

            # 如果总结超过最大长度，进行截断
            if len(summary) > self.max_summary_tokens * 4:  # 粗略估计：1个token≈4个字符
                summary = summary[:self.max_summary_tokens * 4] + "..."

            return summary

        except Exception as e:
            # 如果LLM总结失败，使用回退方案
            print(f"LLM总结生成失败: {e}")
            return self._generate_fallback_summary(messages)

    def _generate_fallback_summary(self, messages: List[TimestampedMessage]) -> str:
        """
        回退方案：简单的消息合并

        Args:
            messages: 需要总结的消息列表

        Returns:
            简单的合并文本
        """
        summary_parts = []
        for msg in messages:
            role = msg.message.get("role", "unknown")
            content = msg.message.get("content", "")
            if content:
                # 简化内容：只取前100个字符
                truncated = content[:100] + ("..." if len(content) > 100 else "")
                summary_parts.append(f"{role}: {truncated}")

        return "；".join(summary_parts)

    async def _generate_summary_with_llm(self, prompt: str) -> str:
        """
        使用LLM生成总结

        Args:
            prompt: 完整的提示词

        Returns:
            LLM生成的总结文本
        """
        try:
            # 使用LLM生成总结
            response = await self.openai_client.chat.completions.create(
                model="deepseek-chat",  # 使用默认模型
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_summary_tokens,
                temperature=0.3,  # 较低的温度以获得更确定的总结
            )

            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content.strip()
            else:
                return ""

        except Exception as e:
            print(f"LLM调用失败: {e}")
            return ""

    def _is_summary_message(self, message: TimestampedMessage) -> bool:
        """
        检查是否为总结消息

        Args:
            message: 带时间戳的消息

        Returns:
            如果是总结消息返回True
        """
        content = message.message.get("content", "")
        return isinstance(content, str) and content.startswith("历史对话摘要：")

    def get_stats(self) -> Dict[str, Any]:
        """获取上下文统计信息"""
        user_msgs = sum(1 for msg in self.messages if msg.message["role"] == "user")
        assistant_msgs = sum(1 for msg in self.messages if msg.message["role"] == "assistant")
        tool_msgs = sum(1 for msg in self.messages if msg.message["role"] == "tool")
        
        oldest_time = min((msg.timestamp for msg in self.messages), default=time.time())
        age_seconds = time.time() - oldest_time
        
        return {
            "total_messages": len(self.messages),
            "user_messages": user_msgs,
            "assistant_messages": assistant_msgs,
            "tool_messages": tool_msgs,
            "current_turn": self.current_turn,
            "context_age_seconds": age_seconds,
            "max_turns": self.max_turns,
            "max_time_seconds": self.max_time_seconds,
        }
