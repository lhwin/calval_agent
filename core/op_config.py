"""
算子运行配置 (对应原 GPF IPFConfig 的关键字段)。
"""

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class LocalConfig:
    """算子运行配置, 字段对应原 GPF 的 ipf_config。"""

    # 必填 (对应 XML 工单)
    sat_id: str
    aux_data_type: str
    start_date: str          # YYYYMMDD
    end_date: str            # YYYYMMDD
    data_version: str = "V001"

    # 路径
    input_dir: str = "GPF"
    output_dir: str = "output"
    aux_input_dir: Optional[str] = None     # 辅助数据目录 (第二颗卫星)
    aux_ycz: Optional[str] = None           # 验潮站标识 (04-MATCH 专用)
    mss_path: Optional[str] = None          # MSS 模型路径 (04-MATCH)
    fes2014_path: Optional[str] = None      # FES2014 潮汐模型路径 (04-MATCH)
    ycz_data_dir: Optional[str] = None      # 验潮站数据目录 (04-MATCH)

    # 处理参数 (原码默认值)
    match_time: float = 2.0                 # 小时
    distance_to_coast: float = 50.0         # km
    ocean_depth: float = 1000.0             # m
    select_area: Optional[List[float]] = None   # [min_lat,max_lat,min_lon,max_lon]
    wind_speed: Optional[List[float]] = None

    # 工单元数据
    order_id: int = 0
    proc_name: str = "calibration"
    version: str = "V01"
    template_docx: Optional[str] = None

    def clone_with(self, **overrides) -> "LocalConfig":
        """生成修改后的副本 (供降级策略使用)。"""
        import dataclasses
        return dataclasses.replace(self, **overrides)
