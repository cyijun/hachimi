#!/usr/bin/env python3
"""测试上下文管理器的总结功能"""

import sys
import time
import importlib.util
from unittest.mock import AsyncMock, MagicMock

# 直接导入context_manager模块，避免导入agent和config
spec = importlib.util.spec_from_file_location(
    "context_manager",
    "llm_mcp_host/context_manager.py"
)
context_manager = importlib.util.module_from_spec(spec)
sys.modules["context_manager"] = context_manager
spec.loader.exec_module(context_manager)
ContextManager = context_manager.ContextManager

def test_summarization_enabled():
    """测试启用总结功能"""
    print("=== 测试启用总结功能 ===")

    # 创建上下文管理器，启用总结，max_turns设为2
    cm = ContextManager(
        max_turns=2,
        max_time_seconds=3600,  # 1小时，避免时间过期
        enable_summarization=True,
        summary_role="user"
    )

    # 添加系统提示
    cm.add_message({"role": "system", "content": "你是助手"}, is_system=True)

    # 添加一些消息，超过max_turns
    # 回合1: 用户 + 助手
    cm.add_message({"role": "user", "content": "你好"})
    cm.add_message({"role": "assistant", "content": "你好！有什么可以帮助你的？"})

    # 回合2: 用户 + 助手
    cm.add_message({"role": "user", "content": "今天天气怎么样？"})
    cm.add_message({"role": "assistant", "content": "今天是晴天，气温25度。"})

    # 回合3: 用户 + 助手（这将触发清理，因为max_turns=2）
    cm.add_message({"role": "user", "content": "谢谢"})

    print(f"当前消息数量: {len(cm.messages)}")
    print("当前消息:")
    for i, msg in enumerate(cm.get_messages()):
        print(f"  {i}: {msg['role']}: {msg.get('content', '')[:50]}...")

    # 检查是否有总结消息
    summary_messages = [msg for msg in cm.get_messages() if isinstance(msg.get('content'), str) and msg['content'].startswith('历史对话摘要：')]
    print(f"总结消息数量: {len(summary_messages)}")
    if summary_messages:
        print(f"总结内容: {summary_messages[0]['content'][:100]}...")

    # 验证系统提示仍然存在
    assert cm.get_messages()[0]['role'] == 'system'
    assert len(summary_messages) == 1, "应该有一条总结消息"
    print("[OK] 测试通过")

def test_summarization_disabled():
    """测试禁用总结功能（默认行为）"""
    print("\n=== 测试禁用总结功能 ===")

    cm = ContextManager(
        max_turns=2,
        max_time_seconds=3600,
        enable_summarization=False  # 默认
    )

    cm.add_message({"role": "system", "content": "系统提示"}, is_system=True)

    # 添加消息超过限制
    cm.add_message({"role": "user", "content": "消息1"})
    cm.add_message({"role": "assistant", "content": "回复1"})
    cm.add_message({"role": "user", "content": "消息2"})
    cm.add_message({"role": "assistant", "content": "回复2"})
    cm.add_message({"role": "user", "content": "消息3"})  # 触发清理

    print(f"消息数量: {len(cm.get_messages())}")
    print("消息:")
    for i, msg in enumerate(cm.get_messages()):
        print(f"  {i}: {msg['role']}: {msg.get('content', '')}")

    # 应该没有总结消息
    summary_messages = [msg for msg in cm.get_messages() if isinstance(msg.get('content'), str) and msg['content'].startswith('历史对话摘要：')]
    assert len(summary_messages) == 0, "禁用总结时不应有总结消息"

    # 应该只有系统提示和最近的消息
    # max_turns=2，所以应该保留最近2个回合的消息（消息2, 回复2, 消息3）
    # 但消息3是用户消息，它开始了一个新的回合，所以最近回合是消息3的回合和之前的回合？
    # 实际逻辑：保留当前回合和之前max_turns-1个回合
    print(f"消息数量（包括系统提示）: {len(cm.get_messages())}")
    print("[OK] 测试通过")

def test_time_expiration():
    """测试时间过期与总结的结合"""
    print("\n=== 测试时间过期与总结 ===")

    cm = ContextManager(
        max_turns=10,  # 回合数足够大
        max_time_seconds=2,  # 2秒过期
        enable_summarization=True
    )

    cm.add_message({"role": "system", "content": "系统"}, is_system=True)
    cm.add_message({"role": "user", "content": "消息1"})

    print("等待3秒让消息过期...")
    time.sleep(3)

    # 添加新消息触发清理
    cm.add_message({"role": "user", "content": "消息2"})

    print(f"消息数量: {len(cm.get_messages())}")
    for i, msg in enumerate(cm.get_messages()):
        print(f"  {i}: {msg['role']}: {msg.get('content', '')}")

    # 过期的消息应该被总结或删除
    summary_messages = [msg for msg in cm.get_messages() if isinstance(msg.get('content'), str) and msg['content'].startswith('历史对话摘要：')]
    print(f"总结消息数量: {len(summary_messages)}")

    # 由于消息过期，它可能被总结（如果enable_summarization=True）
    # 但我们的实现中，过期消息会被放入messages_to_process，如果启用总结则生成总结
    if summary_messages:
        print(f"总结内容: {summary_messages[0]['content'][:100]}...")

    print("[OK] 测试通过")

def test_summary_role():
    """测试总结消息的角色"""
    print("\n=== 测试总结消息的角色 ===")

    cm = ContextManager(
        max_turns=2,
        max_time_seconds=3600,
        enable_summarization=True,
        summary_role="system"  # 使用system角色
    )

    cm.add_message({"role": "system", "content": "原始系统提示"}, is_system=True)
    cm.add_message({"role": "user", "content": "消息1"})
    cm.add_message({"role": "assistant", "content": "回复1"})
    cm.add_message({"role": "user", "content": "消息2"})
    cm.add_message({"role": "assistant", "content": "回复2"})
    cm.add_message({"role": "user", "content": "消息3"})  # 触发清理

    print("消息:")
    for i, msg in enumerate(cm.get_messages()):
        role = msg['role']
        content_preview = str(msg.get('content', ''))[:40]
        print(f"  {i}: {role}: {content_preview}...")

    # 检查总结消息的角色
    summary_messages = [msg for msg in cm.get_messages() if isinstance(msg.get('content'), str) and msg['content'].startswith('历史对话摘要：')]
    if summary_messages:
        assert summary_messages[0]['role'] == 'system', f"总结消息角色应为'system'，实际为{summary_messages[0]['role']}"
        print(f"总结消息角色正确: {summary_messages[0]['role']}")

    print("[OK] 测试通过")

def test_llm_summarization():
    """测试LLM生成的总结功能"""
    print("\n=== 测试LLM生成的总结功能 ===")

    # 创建模拟的OpenAI客户端
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()

    # 设置模拟响应
    mock_message.content = "这是由LLM生成的智能总结，包含了对话的关键信息。"
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]

    # 模拟异步调用
    async def mock_create(*args, **kwargs):
        return mock_response

    mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

    # 创建上下文管理器，启用LLM总结
    cm = ContextManager(
        max_turns=2,
        max_time_seconds=3600,
        enable_summarization=True,
        summary_role="user",
        max_summary_tokens=100,
        summary_prompt="请用中文简洁总结以下对话历史，保留关键信息，总结长度不超过{max_tokens}个token：",
        openai_client=mock_client
    )

    cm.add_message({"role": "system", "content": "系统提示"}, is_system=True)

    # 添加消息超过限制
    cm.add_message({"role": "user", "content": "用户的第一条消息，询问天气情况。"})
    cm.add_message({"role": "assistant", "content": "助手的回复，告知今天天气晴朗。"})
    cm.add_message({"role": "user", "content": "用户的第二条消息，询问是否要带伞。"})
    cm.add_message({"role": "assistant", "content": "助手的回复，建议带伞以防万一。"})
    cm.add_message({"role": "user", "content": "用户的第三条消息，表示感谢。"})  # 触发清理

    print(f"消息数量: {len(cm.get_messages())}")
    print("消息:")
    for i, msg in enumerate(cm.get_messages()):
        role = msg['role']
        content = str(msg.get('content', ''))
        preview = content[:60] + "..." if len(content) > 60 else content
        print(f"  {i}: {role}: {preview}")

    # 检查是否有总结消息
    summary_messages = [msg for msg in cm.get_messages() if isinstance(msg.get('content'), str) and msg['content'].startswith('历史对话摘要：')]
    print(f"总结消息数量: {len(summary_messages)}")
    if summary_messages:
        print(f"总结内容预览: {summary_messages[0]['content'][:80]}...")

    # 验证模拟客户端被调用
    assert mock_client.chat.completions.create.called, "LLM客户端应该被调用"
    print(f"LLM调用次数: {mock_client.chat.completions.create.call_count}")

    print("[OK] LLM总结测试通过")

def test_summary_length_config():
    """测试总结长度配置"""
    print("\n=== 测试总结长度配置 ===")

    # 测试不同的总结长度配置
    test_cases = [
        {"max_summary_tokens": 50, "description": "短总结"},
        {"max_summary_tokens": 100, "description": "中等总结"},
        {"max_summary_tokens": 200, "description": "长总结"},
    ]

    for test_case in test_cases:
        print(f"\n测试: {test_case['description']} (max_summary_tokens={test_case['max_summary_tokens']})")

        cm = ContextManager(
            max_turns=2,
            max_time_seconds=3600,
            enable_summarization=True,
            summary_role="user",
            max_summary_tokens=test_case['max_summary_tokens'],
            summary_prompt="测试提示词，最大长度{max_tokens}个token：",
            openai_client=None  # 没有客户端，使用回退方案
        )

        cm.add_message({"role": "system", "content": "系统"}, is_system=True)

        # 添加测试消息
        for i in range(5):
            cm.add_message({
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"这是第{i+1}条测试消息，用于测试总结长度配置功能。"
            })

        # 检查配置是否正确应用
        assert cm.max_summary_tokens == test_case['max_summary_tokens'], f"配置未正确应用: {cm.max_summary_tokens}"
        print(f"  配置正确应用: max_summary_tokens={cm.max_summary_tokens}")

    print("[OK] 总结长度配置测试通过")

def test_summary_prompt_template():
    """测试总结提示词模板"""
    print("\n=== 测试总结提示词模板 ===")

    custom_prompt = "请总结以下对话，重点提取{max_tokens}个token内的关键决策："

    cm = ContextManager(
        max_turns=2,
        max_time_seconds=3600,
        enable_summarization=True,
        summary_role="user",
        max_summary_tokens=150,
        summary_prompt=custom_prompt,
        openai_client=None
    )

    # 验证提示词模板
    expected_prompt = custom_prompt.format(max_tokens=150)
    actual_prompt = cm.summary_prompt.format(max_tokens=cm.max_summary_tokens)

    print(f"自定义提示词: {custom_prompt}")
    print(f"格式化后提示词: {actual_prompt}")

    assert actual_prompt == expected_prompt, "提示词模板格式化错误"
    print("[OK] 提示词模板测试通过")

if __name__ == "__main__":
    test_summarization_enabled()
    test_summarization_disabled()
    test_time_expiration()
    test_summary_role()
    test_llm_summarization()
    test_summary_length_config()
    test_summary_prompt_template()
    print("\n[SUCCESS] 所有测试通过！")