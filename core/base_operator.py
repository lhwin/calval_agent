"""
BaseOperator - 所有算子的基类
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BaseOperator(ABC):
    """算子抽象基类"""
    
    def __init__(self, config):
        self.config = config
        self.validate_config()
        
    @abstractmethod
    def validate_config(self) -> None:
        """校验配置，抛出 ValueError 如果无效"""
        pass
    
    def run_local(self, local_input_dir: str) -> Dict[str, Any]:
        """本地执行（可选实现）"""
        logger.warning(f"{self.__class__.__name__}: 本地执行未实现")
        return {"status": "pending", "message": "本地执行待实现"}
    
    def run_ssh(self, ssh_client) -> Dict[str, Any]:
        """SSH 远程执行（可选实现）"""
        logger.warning(f"{self.__class__.__name__}: SSH 执行未实现")
        return {"status": "pending", "message": "SSH 执行待实现"}
    
    def load_output(self, output_dir: str) -> Dict[str, Any]:
        """加载输出结果（可选实现）"""
        logger.warning(f"{self.__class__.__name__}: 输出加载未实现")
        return {}
    
    def run(self) -> Dict[str, Any]:
        """默认运行入口：优先本地，否则返回 SSH 指引"""
        if hasattr(self.config, 'input_dir') and self.config.input_dir:
            return self.run_local(self.config.input_dir)
        else:
            return {
                "status": "requires_ssh",
                "message": "请配置 input_dir 或使用 SSH 执行器",
                "suggestion": "通过 SSHExecutor 调用远程 main.py"
            }
