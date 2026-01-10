"""
聊天上下文管理模块
实现基于时间和回合数限制的上下文过期机制
"""
import time
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
        system_prompt: Optional[str] = None
    ):
        """
        初始化上下文管理器
        
        Args:
            max_turns: 最大保存回合数（用户+助手为一回合）
            max_time_seconds: 最大时间窗口（秒）
            system_prompt: 系统提示词
        """
        self.max_turns = max_turns
        self.max_time_seconds = max_time_seconds
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
        """清理过期消息"""
        if len(self.messages) <= 1:  # 只有系统提示或空列表
            return
        
        current_time = time.time()
        new_messages = []
        
        # 始终保留系统提示
        if self.messages[0].message["role"] == "system":
            new_messages.append(self.messages[0])
            start_index = 1
        else:
            start_index = 0
        
        # 基于回合数清理
        recent_turns = set()
        for msg in reversed(self.messages[start_index:]):
            if msg.turn_count > self.current_turn - self.max_turns:
                recent_turns.add(msg.turn_count)
        
        # 基于时间清理
        for msg in self.messages[start_index:]:
            # 检查是否在最近的回合中且未过期
            time_valid = current_time - msg.timestamp <= self.max_time_seconds
            turn_valid = msg.turn_count in recent_turns
            
            if time_valid and turn_valid:
                new_messages.append(msg)
        
        self.messages = new_messages
    
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
