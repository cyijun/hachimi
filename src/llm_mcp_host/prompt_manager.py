"""
提示管理器模块
管理MCP提示和系统提示的整合
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class PromptInfo:
    """提示信息"""
    name: str
    server: str
    description: str
    arguments: Dict[str, Any]
    content: Optional[str] = None


class PromptManager:
    """提示管理器，整合系统提示和MCP提示"""
    
    def __init__(self, system_prompt: str = ""):
        """
        初始化提示管理器
        
        Args:
            system_prompt: 系统提示词
        """
        self.system_prompt = system_prompt
        self.mcp_prompts: List[PromptInfo] = []
        self.loaded_prompts: Dict[str, str] = {}  # prompt_name -> content
        
    def add_mcp_prompts(self, prompts: List[Dict[str, Any]]):
        """
        添加MCP提示
        
        Args:
            prompts: MCP提示列表
        """
        for prompt_data in prompts:
            prompt_info = PromptInfo(
                name=prompt_data.get("name", ""),
                server=prompt_data.get("server", ""),
                description=prompt_data.get("description", ""),
                arguments=prompt_data.get("arguments", {}),
            )
            self.mcp_prompts.append(prompt_info)
    
    async def load_prompt(self, prompt_name: str, mcp_manager, **kwargs) -> Optional[str]:
        """
        加载提示内容
        
        Args:
            prompt_name: 提示名称
            mcp_manager: MCP管理器实例
            **kwargs: 提示参数
            
        Returns:
            提示内容，如果未找到则返回None
        """
        # 首先检查是否已加载
        if prompt_name in self.loaded_prompts:
            return self.loaded_prompts[prompt_name]
        
        # 从MCP服务器获取
        content = await mcp_manager.get_prompt(prompt_name, **kwargs)
        if content:
            self.loaded_prompts[prompt_name] = content
        
        return content
    
    def get_combined_prompt(self, include_mcp_context: bool = True) -> str:
        """
        获取组合提示（系统提示 + MCP提示上下文）
        
        Args:
            include_mcp_context: 是否包含MCP提示上下文
            
        Returns:
            组合后的提示
        """
        if not include_mcp_context or not self.mcp_prompts:
            return self.system_prompt
        
        # 构建MCP提示上下文
        mcp_context = "\n\n## 可用的MCP提示:\n"
        for prompt in self.mcp_prompts:
            mcp_context += f"- {prompt.name}"
            if prompt.description:
                mcp_context += f": {prompt.description}"
            if prompt.arguments:
                args_str = ", ".join([f"{k}: {v}" for k, v in prompt.arguments.items()])
                mcp_context += f" (参数: {args_str})"
            mcp_context += f" [来自服务器: {prompt.server}]\n"
        
        # 添加已加载提示的内容
        if self.loaded_prompts:
            mcp_context += "\n## 已加载的提示内容:\n"
            for name, content in self.loaded_prompts.items():
                # 截断过长的内容
                if len(content) > 500:
                    content = content[:500] + "..."
                mcp_context += f"### {name}:\n{content}\n\n"
        
        return self.system_prompt + mcp_context
    
    def get_prompt_info(self, prompt_name: str) -> Optional[PromptInfo]:
        """根据名称获取提示信息"""
        for prompt in self.mcp_prompts:
            if prompt.name == prompt_name:
                return prompt
        return None
    
    def get_all_prompt_names(self) -> List[str]:
        """获取所有提示名称"""
        return [prompt.name for prompt in self.mcp_prompts]
    
    def clear_loaded_prompts(self):
        """清空已加载的提示内容"""
        self.loaded_prompts.clear()
    
    def update_system_prompt(self, new_prompt: str):
        """更新系统提示"""
        self.system_prompt = new_prompt
    
    def add_custom_prompt(self, name: str, content: str, description: str = "", server: str = "custom"):
        """添加自定义提示"""
        prompt_info = PromptInfo(
            name=name,
            server=server,
            description=description,
            arguments={},
            content=content
        )
        self.mcp_prompts.append(prompt_info)
        self.loaded_prompts[name] = content
    
    def get_stats(self) -> Dict[str, Any]:
        """获取管理器统计信息"""
        return {
            "system_prompt_length": len(self.system_prompt),
            "mcp_prompts_count": len(self.mcp_prompts),
            "loaded_prompts_count": len(self.loaded_prompts),
            "mcp_prompt_names": self.get_all_prompt_names(),
        }
