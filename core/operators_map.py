"""
完整的 8 算子映射表 - 基于 GPF 源码结构。

每个算子 = MATCH(匹配) + CAL(计算), 各自独立 main.py 入口
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class OperatorType(Enum):
    """算子类型枚举"""
    STAR_CROSS_MATCH = "star_cross_match"        # 01-MATCH
    STAR_CROSS_CAL = "star_cross_cal"            # 01-CAL
    SELF_CROSS_MATCH = "self_cross_match"        # 02-MATCH
    SELF_CROSS_CAL = "self_cross_cal"            # 02-CAL
    PARALLEL_CROSS_MATCH = "parallel_cross_match"  # 03-MATCH
    PARALLEL_CROSS_CAL = "parallel_cross_cal"      # 03-CAL
    YCZ_MATCH = "ycz_match"                      # 04-MATCH
    YCZ_CAL = "ycz_cal"                          # 04-CAL


@dataclass
class OperatorInfo:
    """单个算子的元信息"""
    operator_type: OperatorType
    short_name: str  # 显示名
    module_path: str  # GPF 下的相对路径
    main_entry: str  # main.py 文件名
    func_name: str  # 核心函数名
    input_suffix: str  # 输入文件后缀匹配
    output_prefix: str  # 输出文件前缀
    depends_on: Optional[OperatorType] = None  # 依赖的前置算子 (CAL 依赖 MATCH)


# 8 个算子完整映射
OPERATOR_MAP = {
    OperatorType.STAR_CROSS_MATCH: OperatorInfo(
        operator_type=OperatorType.STAR_CROSS_MATCH,
        short_name="星星交叉匹配",
        module_path="01-星星交叉法 v2.0/cvs_glsy_alt_gdr_aux_sat_match",
        main_entry="main.py",
        func_name="func_cross_matching_pro",
        input_suffix=".nc",  # 读取卫星 NC 文件
        output_prefix="match_result_",  # 生成 match_result_*.npz
        depends_on=None,
    ),
    OperatorType.STAR_CROSS_CAL: OperatorInfo(
        operator_type=OperatorType.STAR_CROSS_CAL,
        short_name="星星交叉定标",
        module_path="01-星星交叉法 v2.0/csv_glsy_alt_gdr_aux_sat_cal",
        main_entry="main.py",
        func_name="func_cross_cal_pro",
        input_suffix=".npz",  # 读取 MATCH 生成的 NPZ
        output_prefix="calibration_data_",  # 生成 calibration_data_*.npz
        depends_on=OperatorType.STAR_CROSS_MATCH,
    ),
    OperatorType.SELF_CROSS_MATCH: OperatorInfo(
        operator_type=OperatorType.SELF_CROSS_MATCH,
        short_name="星自交叉匹配",
        module_path="02-星星自交叉法 v2.0/CVS_SELF_GLSY_ALT_GDR_AUX_SAT_MATCH",
        main_entry="main.py",
        func_name="func_self_cross_matching_pro",
        input_suffix=".nc",
        output_prefix="matches_",
        depends_on=None,
    ),
    OperatorType.SELF_CROSS_CAL: OperatorInfo(
        operator_type=OperatorType.SELF_CROSS_CAL,
        short_name="星自交叉定标",
        module_path="02-星星自交叉法 v2.0/CVS_SELF_GLSY_ALT_GDR_AUX_SAT_CAL",
        main_entry="main.py",
        func_name="func_self_cross_cal_pro",
        input_suffix=".npz",
        output_prefix="calibration_data_",
        depends_on=OperatorType.SELF_CROSS_MATCH,
    ),
    OperatorType.PARALLEL_CROSS_MATCH: OperatorInfo(
        operator_type=OperatorType.PARALLEL_CROSS_MATCH,
        short_name="平行交叉匹配",
        module_path="03-星星交叉_烟台/XOver_2026_parallel_v4_match",
        main_entry="main.py",
        func_name="func_cross_matching_pro",
        input_suffix=".h5",  # 烟台算子用 H5 格式
        output_prefix="cross_match_",
        depends_on=None,
    ),
    OperatorType.PARALLEL_CROSS_CAL: OperatorInfo(
        operator_type=OperatorType.PARALLEL_CROSS_CAL,
        short_name="平行交叉定标",
        module_path="03-星星交叉_烟台/XOver_2026_parallel_v5_cal",
        main_entry="main.py",
        func_name="func_cross_cal_pro",
        input_suffix=".npz",
        output_prefix="sig0_calib_",
        depends_on=OperatorType.PARALLEL_CROSS_MATCH,
    ),
    OperatorType.YCZ_MATCH: OperatorInfo(
        operator_type=OperatorType.YCZ_MATCH,
        short_name="验潮站匹配",
        module_path="04-验潮站外推 v1.0/CVS_GLSY_ALT_GDR_AUX_YCZ_MATCH",
        main_entry="main.py",
        func_name="func_ycz_matching_pro",
        input_suffix=".nc",  # 卫星数据
        output_prefix="MATCHED_",  # 生成 MATCHED_*.npz
        depends_on=None,
    ),
    OperatorType.YCZ_CAL: OperatorInfo(
        operator_type=OperatorType.YCZ_CAL,
        short_name="验潮站外推",
        module_path="04-验潮站外推 v1.0/CVS_GLSY_ALT_GDR_AUX_YCZ_CAL",
        main_entry="main.py",
        func_name="func_ycz_cal_pro",
        input_suffix=".npz",  # 读取 MATCHED_*.npz
        output_prefix="ycz_cal_",
        depends_on=OperatorType.YCZ_MATCH,
    ),
}


def get_operator(op_type: OperatorType) -> OperatorInfo:
    """根据类型获取算子信息"""
    return OPERATOR_MAP[op_type]


def get_by_short_name(name: str) -> Optional[OperatorInfo]:
    """根据短名称查找算子"""
    for info in OPERATOR_MAP.values():
        if name in [info.operator_type.value, info.short_name]:
            return info
    return None


def get_dependent_chain(op_type: OperatorType) -> list:
    """获取依赖链（前置算子列表）"""
    chain = []
    info = OPERATOR_MAP[op_type]
    if info.depends_on:
        chain.extend(get_dependent_chain(info.depends_on))
    chain.append(info)
    return chain


# 快捷别名映射
ALIASES = {
    # 常用缩写
    "stars": OperatorType.STAR_CROSS_CAL,
    "star": OperatorType.STAR_CROSS_CAL,
    "cross": OperatorType.STAR_CROSS_CAL,
    "self": OperatorType.SELF_CROSS_CAL,
    "autocal": OperatorType.SELF_CROSS_CAL,
    "parallel": OperatorType.PARALLEL_CROSS_CAL,
    "ycz": OperatorType.YCZ_CAL,
    "tide": OperatorType.YCZ_CAL,
    "验潮": OperatorType.YCZ_CAL,
    "匹配": None,  # 需配合具体算子
    "cal": None,
    "match": None,
}
