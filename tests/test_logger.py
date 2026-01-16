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

def test_file_logging():
    """测试文件日志"""
    print("\n=== 测试文件日志 ===")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        log_file = f.name
    
    try:
        # 创建文件日志器
        file_logger = logger.setup_logger(
            name="file_logger",
            log_file=log_file
        )
        
        # 写入日志
        file_logger.info("文件日志测试消息")
        
        # 验证文件内容
        with open(log_file, 'r') as f:
            content = f.read()
            assert "文件日志测试消息" in content, "日志应该写入文件"
        
        print(f"[OK] 文件日志写入成功: {log_file}")
        
    finally:
        if os.path.exists(log_file):
            os.unlink(log_file)

if __name__ == "__main__":
    test_logger_creation()
    test_logger_functions()
    test_setup_logger()
    test_file_logging()
    print("\n[SUCCESS] 所有日志测试通过！")
