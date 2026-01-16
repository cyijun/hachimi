#!/usr/bin/env python3
"""测试配置模块"""

import os
import sys
import tempfile
import yaml
from pathlib import Path

# 直接导入config模块
import sys; sys.path.insert(0, "src"); import config

def test_config_loads():
    """测试配置加载"""
    print("=== 测试配置加载 ===")
    
    # 检查全局配置实例
    assert hasattr(config, 'config'), "config模块应该有config实例"
    assert isinstance(config.config, config.Config), "config应该是Config实例"
    
    print(f"[OK] 配置实例创建成功")
    print(f"[OK] 配置路径: {config.config.config_path}")

def test_config_get():
    """测试配置获取"""
    print("\n=== 测试配置获取 ===")
    
    cfg = config.config
    
    # 测试获取嵌套值
    llm_config = cfg.llm
    assert isinstance(llm_config, dict), "llm配置应该是字典"
    
    stt_config = cfg.stt
    assert isinstance(stt_config, dict), "stt配置应该是字典"
    
    print(f"[OK] LLM配置: {llm_config}")
    print(f"[OK] STT配置: {stt_config}")

def test_env_var_substitution():
    """测试环境变量替换"""
    print("\n=== 测试环境变量替换 ===")
    
    # 创建临时配置文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        temp_config_path = f.name
        yaml.dump({
            'test_var': '${TEST_ENV_VAR:default_value}',
            'test_nested': {
                'nested_var': '${TEST_NESTED:123}'
            }
        }, f)
    
    try:
        # 设置环境变量
        os.environ['TEST_ENV_VAR'] = 'test_value_123'
        os.environ['TEST_NESTED'] = '456'
        
        # 加载配置
        test_config = config.Config(temp_config_path)
        
        # 验证环境变量替换
        assert test_config.get('test_var') == 'test_value_123', "环境变量应该被替换"
        assert test_config.get('test_nested.nested_var') == '456', "嵌套环境变量应该被替换"
        
        print(f"[OK] 环境变量替换成功")
        print(f"[OK] test_var: {test_config.get('test_var')}")
        print(f"[OK] nested_var: {test_config.get('test_nested.nested_var')}")
        
    finally:
        # 清理
        os.unlink(temp_config_path)
        if 'TEST_ENV_VAR' in os.environ:
            del os.environ['TEST_ENV_VAR']
        if 'TEST_NESTED' in os.environ:
            del os.environ['TEST_NESTED']

def test_config_properties():
    """测试配置属性"""
    print("\n=== 测试配置属性 ===")
    
    cfg = config.config
    
    # 测试各种属性
    assert hasattr(cfg, 'llm'), "应该有llm属性"
    assert hasattr(cfg, 'stt'), "应该有stt属性"
    assert hasattr(cfg, 'tts'), "应该有tts属性"
    assert hasattr(cfg, 'voice_listener'), "应该有voice_listener属性"
    assert hasattr(cfg, 'system_prompt'), "应该有system_prompt属性"
    assert hasattr(cfg, 'process'), "应该有process属性"
    
    print("[OK] 所有配置属性访问正常")

if __name__ == "__main__":
    test_config_loads()
    test_config_get()
    test_env_var_substitution()
    test_config_properties()
    print("\n[SUCCESS] 所有配置测试通过！")
