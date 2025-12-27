# config.py
import os
import yaml
from typing import Any, Dict, Optional
from pathlib import Path

class Config:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config.yaml"
        self._config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """加载YAML配置文件并解析环境变量"""
        if not Path(self.config_path).exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
            
        with open(self.config_path, 'r', encoding='utf-8') as f:
            raw_config = yaml.safe_load(f)
            
        # 递归解析环境变量
        return self._resolve_env_vars(raw_config)
    
    def _resolve_env_vars(self, config: Any) -> Any:
        """递归解析配置中的环境变量占位符"""
        if isinstance(config, dict):
            return {k: self._resolve_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._resolve_env_vars(item) for item in config]
        elif isinstance(config, str) and config.startswith("${") and config.endswith("}"):
            # 解析环境变量占位符: ${VAR_NAME:default_value}
            var_part = config[2:-1]
            if ":" in var_part:
                var_name, default_value = var_part.split(":", 1)
            else:
                var_name, default_value = var_part, None
            
            env_value = os.getenv(var_name)
            if env_value is not None:
                return env_value
            elif default_value is not None:
                return default_value
            else:
                # 环境变量未设置且无默认值，返回空字符串并警告
                print(f"警告: 环境变量 {var_name} 未设置且无默认值，使用空字符串")
                return ""
        else:
            return config
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点分隔符路径"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    @property
    def mcp_server(self) -> Dict[str, Any]:
        return self.get('mcp_server', {})
    
    @property
    def llm(self) -> Dict[str, Any]:
        return self.get('llm', {})
    
    @property
    def stt(self) -> Dict[str, Any]:
        return self.get('stt', {})
    
    @property
    def tts(self) -> Dict[str, Any]:
        return self.get('tts', {})
    
    @property
    def voice_listener(self) -> Dict[str, Any]:
        return self.get('voice_listener', {})
    
    @property
    def system_prompt(self) -> str:
        return self.get('system_prompt', '')
    
    @property
    def process(self) -> Dict[str, Any]:
        return self.get('process', {})

# 全局配置实例
config = Config()
