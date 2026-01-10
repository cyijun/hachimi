"""
工具选择器模块
实现向量搜索mock功能，根据用户查询选择最相关的工具
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from collections import Counter
import math


@dataclass
class ToolInfo:
    """工具信息"""
    name: str  # 工具唯一标识符（server:tool格式）
    original_name: str  # 原始工具名
    server_name: str  # 服务器名称
    description: str  # 工具描述
    parameters: Dict[str, Any]  # 工具参数
    metadata: Dict[str, Any] = None  # 额外元数据
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ToolSelector:
    """工具选择器，实现向量搜索mock功能"""
    
    def __init__(self, top_k: int = 3):
        """
        初始化工具选择器
        
        Args:
            top_k: 返回最相关工具的数量
        """
        self.top_k = top_k
        self.tools: List[ToolInfo] = []
        self._word_freq: Dict[str, Dict[str, float]] = {}  # 工具ID -> 词频向量
        
    def build_index(self, tools: List[ToolInfo]):
        """
        构建工具索引（mock向量库）
        
        Args:
            tools: 工具列表
        """
        self.tools = tools
        self._word_freq = {}
        
        # 为每个工具构建词频向量
        for tool in tools:
            # 合并名称和描述作为文本
            text = f"{tool.name} {tool.description}".lower()
            words = self._tokenize(text)
            
            # 计算词频
            word_counts = Counter(words)
            total_words = len(words)
            
            # 转换为频率
            word_freq = {word: count / total_words for word, count in word_counts.items()}
            self._word_freq[tool.name] = word_freq
    
    def search(self, query: str) -> List[ToolInfo]:
        """
        搜索最相关的工具（mock向量搜索）
        
        Args:
            query: 用户查询
            
        Returns:
            最相关的工具列表，按相关性排序
        """
        if not self.tools:
            return []
        
        # 对查询进行分词
        query_words = self._tokenize(query.lower())
        if not query_words:
            return self.tools[:self.top_k]
        
        # 计算查询词频
        query_counts = Counter(query_words)
        total_query_words = len(query_words)
        query_freq = {word: count / total_query_words for word, count in query_counts.items()}
        
        # 计算每个工具与查询的相似度
        scored_tools = []
        for tool in self.tools:
            tool_freq = self._word_freq.get(tool.name, {})
            
            # 计算余弦相似度（mock）
            similarity = self._cosine_similarity(query_freq, tool_freq)
            
            # 添加额外加分项：名称完全匹配或部分匹配
            name_match_bonus = 0.0
            if query.lower() in tool.original_name.lower():
                name_match_bonus = 0.3
            elif any(word in tool.original_name.lower() for word in query_words):
                name_match_bonus = 0.1
            
            final_score = similarity + name_match_bonus
            scored_tools.append((final_score, tool))
        
        # 按分数排序
        scored_tools.sort(reverse=True, key=lambda x: x[0])
        
        # 返回top_k个工具
        return [tool for score, tool in scored_tools[:self.top_k]]
    
    def get_all_tools(self) -> List[ToolInfo]:
        """获取所有工具"""
        return self.tools
    
    def get_tool_by_name(self, tool_name: str) -> Optional[ToolInfo]:
        """根据工具名获取工具"""
        for tool in self.tools:
            if tool.name == tool_name:
                return tool
        return None
    
    def _tokenize(self, text: str) -> List[str]:
        """简单分词函数"""
        # 移除标点符号，转换为小写，分割单词
        text = re.sub(r'[^\w\s]', ' ', text)
        words = text.split()
        
        # 移除停用词（简单版本）
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        return [word for word in words if word not in stop_words]
    
    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """计算两个词频向量的余弦相似度"""
        # 获取所有单词
        all_words = set(vec1.keys()) | set(vec2.keys())
        
        # 计算点积
        dot_product = sum(vec1.get(word, 0) * vec2.get(word, 0) for word in all_words)
        
        # 计算模长
        norm1 = math.sqrt(sum(v * v for v in vec1.values()))
        norm2 = math.sqrt(sum(v * v for v in vec2.values()))
        
        # 避免除零
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取选择器统计信息"""
        return {
            "total_tools": len(self.tools),
            "top_k": self.top_k,
            "tool_names": [tool.name for tool in self.tools],
        }
