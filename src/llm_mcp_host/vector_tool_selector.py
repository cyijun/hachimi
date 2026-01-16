"""
向量搜索工具选择器
基于embedding API实现真正的向量搜索
"""
import numpy as np
import requests
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from logger import logger
from .tool_selector import ToolSelector as BaseToolSelector
from .tool_selector import ToolInfo


class VectorToolSelector(BaseToolSelector):
    """基于向量搜索的工具选择器"""
    
    def __init__(self, top_k: int = 3, config: Dict[str, Any] = None):
        """
        初始化向量工具选择器
        
        Args:
            top_k: 返回最相关工具的数量
            config: 配置字典，包含embedding相关配置
        """
        super().__init__(top_k)
        self.config = config or {}
        
        # Embedding配置
        self.embedding_config = self.config.get('embedding', {})
        self.embedding_url = self.embedding_config.get('url', 'https://api.siliconflow.cn/v1/embeddings')
        self.embedding_model = self.embedding_config.get('model', 'BAAI/bge-m3')
        self.embedding_api_key = self.embedding_config.get('api_key', '')
        self.embedding_dimensions = self.embedding_config.get('dimensions', 1024)
        
        # 工具向量存储
        self.tool_vectors: Dict[str, np.ndarray] = {}
        self.tool_descriptions: Dict[str, str] = {}
        
        # 缓存已计算的查询向量
        self.query_vector_cache: Dict[str, np.ndarray] = {}
        
    def _get_embedding(self, text: str, use_cache: bool = True) -> np.ndarray:
        """
        获取文本的embedding向量
        
        Args:
            text: 输入文本
            use_cache: 是否使用缓存
            
        Returns:
            embedding向量
        """
        if not text:
            return np.zeros(self.embedding_dimensions)
        
        # 检查缓存
        cache_key = text[:200]  # 使用前200字符作为缓存键
        if use_cache and cache_key in self.query_vector_cache:
            return self.query_vector_cache[cache_key]
        
        try:
            headers = {
                "Authorization": f"Bearer {self.embedding_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.embedding_model,
                "input": text,
                "encoding_format": "float",
                "dimensions": self.embedding_dimensions
            }
            
            response = requests.post(
                self.embedding_url,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'data' in result and len(result['data']) > 0:
                    embedding = np.array(result['data'][0]['embedding'], dtype=np.float32)
                    
                    # 归一化向量（余弦相似度需要归一化向量）
                    if np.linalg.norm(embedding) > 0:
                        embedding = embedding / np.linalg.norm(embedding)
                    
                    # 缓存结果
                    if use_cache:
                        self.query_vector_cache[cache_key] = embedding
                    
                    return embedding
                else:
                    logger.warning(f"Embedding API返回数据格式错误: {result}")
            else:
                logger.error(f"Embedding API调用失败: {response.status_code}, {response.text}")
                
        except requests.exceptions.Timeout:
            logger.error(f"Embedding API请求超时")
        except requests.exceptions.RequestException as e:
            logger.error(f"Embedding API请求错误: {e}")
        except Exception as e:
            logger.error(f"获取embedding时发生错误: {e}")
        
        # 如果API调用失败，返回零向量并回退到基类的搜索
        return np.zeros(self.embedding_dimensions)
    
    def build_index(self, tools: List[ToolInfo]):
        """
        构建工具向量索引
        
        Args:
            tools: 工具列表
        """
        self.tools = tools
        self.tool_vectors = {}
        self.tool_descriptions = {}
        
        logger.info(f"开始构建 {len(tools)} 个工具的向量索引...")
        
        for tool in tools:
            # 为每个工具生成描述文本
            description_text = self._create_tool_description(tool)
            self.tool_descriptions[tool.name] = description_text
            
            # 获取embedding向量
            embedding = self._get_embedding(description_text, use_cache=False)
            
            # 存储向量
            if embedding is not None:
                self.tool_vectors[tool.name] = embedding
        
        logger.info(f"工具向量索引构建完成，成功生成 {len(self.tool_vectors)} 个向量")
        
        # 调用基类的build_index以保持兼容性
        super().build_index(tools)
    
    def _create_tool_description(self, tool: ToolInfo) -> str:
        """
        为工具创建用于embedding的描述文本
        
        Args:
            tool: 工具信息
            
        Returns:
            描述文本
        """
        # 提取参数信息
        params_desc = ""
        if tool.parameters and 'properties' in tool.parameters:
            properties = tool.parameters['properties']
            params_list = []
            for param_name, param_info in properties.items():
                param_type = param_info.get('type', 'string')
                param_desc = param_info.get('description', '')
                params_list.append(f"{param_name}({param_type}): {param_desc}")
            params_desc = "参数: " + ", ".join(params_list)
        
        # 构建完整的描述文本
        description = f"""
        工具名称: {tool.original_name}
        工具描述: {tool.description}
        {params_desc}
        服务器: {tool.server_name}
        """
        
        return description.strip()
    
    def search(self, query: str) -> List[ToolInfo]:
        """
        使用向量搜索最相关的工具
        
        Args:
            query: 用户查询
            
        Returns:
            最相关的工具列表，按相关性排序
        """
        if not self.tools or not self.tool_vectors:
            return super().search(query)
        
        # 获取查询的embedding向量
        query_vector = self._get_embedding(query)
        
        # 如果获取embedding失败（返回零向量），回退到基类的搜索
        if np.all(query_vector == 0):
            logger.warning("获取查询embedding失败，回退到基于词频的搜索")
            return super().search(query)
        
        # 计算查询与每个工具的余弦相似度
        similarities = []
        for tool in self.tools:
            if tool.name in self.tool_vectors:
                tool_vector = self.tool_vectors[tool.name]
                
                # 计算余弦相似度
                if np.all(tool_vector == 0):
                    similarity = 0.0
                else:
                    similarity = np.dot(query_vector, tool_vector) / (
                        np.linalg.norm(query_vector) * np.linalg.norm(tool_vector)
                    )
            else:
                # 如果工具没有向量，使用基类的相似度计算
                similarity = 0.0
            
            # 添加名称匹配的额外加分
            name_match_bonus = 0.0
            query_lower = query.lower()
            tool_name_lower = tool.original_name.lower()
            
            if query_lower in tool_name_lower:
                name_match_bonus = 0.3
            elif any(word in tool_name_lower for word in query_lower.split()):
                name_match_bonus = 0.1
            
            final_score = similarity + name_match_bonus
            similarities.append((final_score, tool))
        
        # 按分数排序
        similarities.sort(reverse=True, key=lambda x: x[0])
        
        # 返回top_k个工具
        top_tools = [tool for score, tool in similarities[:self.top_k]]
        
        # 记录调试信息
        if top_tools and similarities[0][0] > 0:
            logger.debug(f"向量搜索结果: 查询='{query}', 最高分={similarities[0][0]:.3f}, 工具={top_tools[0].original_name}")
        
        return top_tools
    
    def search_with_scores(self, query: str) -> List[Tuple[ToolInfo, float]]:
        """
        搜索工具并返回带分数的结果
        
        Args:
            query: 用户查询
            
        Returns:
            工具和分数的列表
        """
        if not self.tools or not self.tool_vectors:
            # 回退到基类搜索，返回模拟分数
            tools = super().search(query)
            return [(tool, 0.8 - i * 0.1) for i, tool in enumerate(tools)]
        
        query_vector = self._get_embedding(query)
        
        results = []
        for tool in self.tools:
            if tool.name in self.tool_vectors:
                tool_vector = self.tool_vectors[tool.name]
                
                if np.all(query_vector) == 0 or np.all(tool_vector) == 0:
                    similarity = 0.0
                else:
                    similarity = np.dot(query_vector, tool_vector) / (
                        np.linalg.norm(query_vector) * np.linalg.norm(tool_vector)
                    )
                
                # 确保分数在合理范围内
                similarity = max(0.0, min(1.0, similarity))
                results.append((tool, similarity))
        
        # 按分数排序
        results.sort(reverse=True, key=lambda x: x[1])
        
        return results[:self.top_k]
    
    def clear_cache(self):
        """清空查询向量缓存"""
        self.query_vector_cache.clear()
        logger.info("已清空向量缓存")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取选择器统计信息"""
        base_stats = super().get_stats()
        vector_stats = {
            "embedding_model": self.embedding_model,
            "vector_dimensions": self.embedding_dimensions,
            "cached_queries": len(self.query_vector_cache),
            "tool_vectors": len(self.tool_vectors),
        }
        
        return {**base_stats, **vector_stats}