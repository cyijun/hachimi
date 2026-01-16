# config.py
import os
import yaml
from typing import Any, Dict, Optional
from pathlib import Path

from logger import logger

class Config:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config.yaml"
        self._config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load YAML configuration file and parse environment variables"""
        if not Path(self.config_path).exists():
            raise FileNotFoundError(f"Configuration file does not exist: {self.config_path}")
            
        with open(self.config_path, 'r', encoding='utf-8') as f:
            raw_config = yaml.safe_load(f)
            
        # Recursively parse environment variables
        return self._resolve_env_vars(raw_config)
    
    def _resolve_env_vars(self, config: Any) -> Any:
        """Recursively parse environment variable placeholders in configuration"""
        if isinstance(config, dict):
            return {k: self._resolve_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._resolve_env_vars(item) for item in config]
        elif isinstance(config, str) and config.startswith("${") and config.endswith("}"):
            # Parse environment variable placeholder: ${VAR_NAME:default_value}
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
                # Environment variable not set and no default value, return empty string with warning
                logger.warning(f"Warning: Environment variable {var_name} not set and no default value, using empty string")
                return ""
        else:
            return config
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value, supports dot-separated paths"""
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

# Global configuration instance
global_config = Config()
