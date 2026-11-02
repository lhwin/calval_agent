"""
8 个 GPF 算子包装器统一导出。

分组:

原有本地算子保持向后兼容:
- tide_ext, tide_ext_full, star_cross, self_cross
"""

from typing import Dict, Any

# ===== 新的 8 个 GPF 包装器 =====
# 01 星星交叉
from .star_cross_match import StarCrossMatchOperator
from .star_cross_cal import StarCrossCalOperator

# 02 星星自交叉
from .self_cross_match import SelfCrossMatchOperator
from .self_cross_cal import SelfCrossCalOperator

# 03 SIG0 交叉
from .sig0_cross_match import Sig0CrossMatchOperator
from .sig0_cross_cal import Sig0CrossCalOperator

# 04 验潮站
from .ycz_match import YczMatchOperator
from .ycz_cal import YczCalOperator

# ===== 原有本地算子 (向后兼容) =====
from .star_cross import StarCrossCalibration
from .self_cross import SelfCrossCalibration
from .tide_ext import TideStationExtension
from .tide_ext_full import TideStationExtensionFull


# 统一注册表 (新旧混合)
GPF_OPERATORS = {
    # 01 星星交叉
    "star_cross_match": StarCrossMatchOperator,
    "star_cross_cal": StarCrossCalOperator,
    
    # 02 星星自交叉
    "self_cross_match": SelfCrossMatchOperator,
    "self_cross_cal": SelfCrossCalOperator,
    
    # 03 SIG0 交叉
    "sig0_cross_match": Sig0CrossMatchOperator,
    "sig0_cross_cal": Sig0CrossCalOperator,
    
    # 04 验潮站
    "ycz_match": YczMatchOperator,
    "ycz_cal": YczCalOperator,
}

LOCAL_OPERATORS = {
    "star_cross": StarCrossCalibration,
    "self_cross": SelfCrossCalibration,
    "tide_ext": TideStationExtension,
    "tide_ext_full": TideStationExtensionFull,
}

ALL_OPERATORS = {**GPF_OPERATORS, **LOCAL_OPERATORS}


class OperatorRegistry:
    """算子注册表"""
    
    @classmethod
    def get(cls, name: str):
        return ALL_OPERATORS.get(name)
    
    @classmethod
    def run(cls, name: str, config) -> Dict[str, Any]:
        """运行指定算子"""
        op_cls = ALL_OPERATORS.get(name)
        if op_cls is None:
            return {"status": "failed", "error": f"未知算子：{name}. 可用：{list(ALL_OPERATORS.keys())}"}
        return op_cls(config).run()
    
    @classmethod
    def list_gpf_operators(cls):
        """列出所有 GPF 包装器"""
        return list(GPF_OPERATORS.keys())
    
    @classmethod
    def list_local_operators(cls):
        """列出所有本地算子"""
        return list(LOCAL_OPERATORS.keys())


__all__ = list(ALL_OPERATORS.keys()) + ["OperatorRegistry", "GPF_OPERATORS", "LOCAL_OPERATORS"]

