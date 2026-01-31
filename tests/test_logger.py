#!/usr/bin/env python3
"""测试日志模块"""

import logging
import tempfile
import os

# 直接导入logger模块
import sys; sys.path.insert(0, "src"); import logger

def test_logger_creation():
    """测试日志器创建"""
    print("=== 测试日志器创建 ===")
    
    # 检查全局日志器
    assert hasattr(logger, 'logger'), "logger模块应该有logger实例"
    assert isinstance(logger.logger, logging.Logger), "logger应该是Logger实例"
    
    print("[OK] 全局日志器创建成功")

def test_logger_functions():
    """测试便捷函数"""
    print("\n=== 测试便捷函数 ===")
    
    # 测试各种日志级别
    logger.info("测试info消息")
    logger.debug("测试debug消息")
    logger.warning("测试warning消息")
    logger.error("测试error消息")
    
    print("[OK] 所有日志函数调用成功")

def test_setup_logger():
    """测试setup_logger函数"""
    print("\n=== 测试setup_logger函数 ===")
    
    # 创建自定义日志器
    custom_logger = logger.setup_logger(
        name="test_logger",
        level=logging.DEBUG
    )
    
    assert isinstance(custom_logger, logging.Logger), "应该返回Logger实例"
    assert custom_logger.name == "test_logger", "日志器名称应该正确"
    
    # 测试日志输出
    custom_logger.debug("自定义日志器测试")
    
    print("[OK] 自定义日志器创建成功")

if __name__ == "__main__":
    test_logger_creation()
    test_logger_functions()
    test_setup_logger()
    print("\n[SUCCESS] 所有日志测试通过！")
