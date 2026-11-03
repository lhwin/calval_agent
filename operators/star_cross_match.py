"""
01 星星交叉 - MATCH 算子包装器
输出：NPZ 匹配文件 (match_result_*.npz)
"""

from typing import Dict, Any, Optional
import numpy as np
from pathlib import Path
import tempfile
import shutil

from core.base_operator import BaseOperator
from core.op_config import LocalConfig


class StarCrossMatchOperator(BaseOperator):
    """星星交叉匹配算子 (01-MATCH)"""
    
    def __init__(self, config: LocalConfig):
        super().__init__(config)
        
    @property
    def supported_sats(self):
        return {"S6A", "JA3", "HY-1D", "HY-2A", "HY-2B", "S3A", "S3B"}
        
    def validate_config(self) -> None:
        """校验配置"""
        if not self.config.sat_id or self.config.sat_id not in self.supported_sats:
            raise ValueError(f"不支持的主卫星：{self.config.sat_id}")
        if not self.config.aux_data_type or self.config.aux_data_type not in self.supported_sats:
            raise ValueError(f"不支持的辅助卫星：{self.config.aux_sat}")
        if not self.config.input_dir:
            raise ValueError("必须指定 input_dir")
            
    def run_local(self, local_input_dir: str) -> Dict[str, Any]:
        """本地执行 MATCH 流程 - 使用标准 XML 生成器"""
        import sys
        import time
        from pathlib import Path
        
        src_dir = Path(__file__).parent / "gpf_src" / "01_star_cross" / "match"
        sys.path.insert(0, str(src_dir))
        
        xml_file = None
        try:
            from func_GLSY_ALT_GDR_AUX_SAT_MATCH import func_cross_matching_pro
            from IPFUtils import MyIPFConfig
            
            # 1. 使用标准 XML 生成器生成工单
            from data_adapter.xml_generator import generate_star_cross_match_xml
            xml_content = generate_star_cross_match_xml(
                sat_id=self.config.sat_id,
                aux_sat=self.config.aux_data_type,
                start_date=self.config.start_date,
                end_date=self.config.end_date,
                input_dir=local_input_dir,
                aux_input_dir=self.config.aux_input_dir or local_input_dir,
                output_dir=self.config.output_dir or "./output"
            )
            
            out_dir = Path(self.config.output_dir or "./output")
            out_dir.mkdir(parents=True, exist_ok=True)
            xml_file = out_dir / f"job_match_{self.config.sat_id}_{self.config.start_date}_{int(time.time())}.xml"
            xml_file.write_text(xml_content, encoding="utf-8")
            
            # 2. 构建配置对象 (与 main.py 完全相同的调用方式)
            ipf_config = MyIPFConfig(str(xml_file))
            ipf_config.input = str(Path(local_input_dir))
            if self.config.aux_input_dir:
                ipf_config.input_AUX = str(Path(self.config.aux_input_dir))
            
            # 补充动态参数 (01/02-MATCH 必需)
            ipf_config.Select_Area = self.config.select_area  # 可选区域 [min_lat,max_lat,min_lon,max_lon]
            ipf_config.distance_to_coast = self.config.distance_to_coast  # km
            ipf_config.ocean_depth = self.config.ocean_depth  # m
            ipf_config.wind_speed = self.config.wind_speed  # range [min, max]
            
            # 3. 执行匹配 (原函数)
            t0 = time.time()
            func_cross_matching_pro(ipf_config)
            elapsed = time.time() - t0
            
            return {
                "status": "success",
                "function": "func_cross_matching_pro",
                "execution_time": elapsed,
                "job_xml": str(xml_file),
                "output_dir": str(out_dir),
            }
        except Exception as e:
            import traceback
            return {
                "status": "failed",
                "error": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc()[-3000:],
            }
        finally:
            if str(src_dir) in sys.path:
                sys.path.remove(str(src_dir))
    
    def load_output(self, output_dir: str) -> Dict[str, np.ndarray]:
        """加载匹配结果 NPZ 文件"""
        from pathlib import Path
        import re
        
        input_path = Path(output_dir)
        sat = self.config.sat_id
        aux = self.config.aux_data_type
        
        # 匹配模式：match_result_S6A_vs_JA3_20230501_20230503.npz
        pattern = rf"match_result_{sat}_vs_{aux}_(\d{{8}})_(\d{{8}})\.npz$"
        
        for p in input_path.glob("**/*.npz"):
            if re.search(pattern, p.name, re.I):
                with np.load(str(p), allow_pickle=True) as f:
                    return {
                        "lon": f.get('lon', np.array([])),
                        "lat": f.get('lat', np.array([])),
                        "time_primary": f.get('time_primary', np.array([])),
                        "time_aux": f.get('time_aux', np.array([])),
                        "ssh_primary": f.get('ssh_primary', np.array([])),
                        "ssh_aux": f.get('ssh_aux', np.array([])),
                        "ssh_diff": f.get('ssh_diff', np.array([])),
                        "distance": f.get('distance', np.array([])),
                        "distance_to_coast": f.get('distance_to_coast', np.array([])),
                        "depth": f.get('depth', np.array([])),
                        "wind_speed": f.get('wind_speed', np.array([])),
                        "match_stats": f.get('match_stats', {})
                    }
        
        raise FileNotFoundError(f"未找到匹配的 NPZ 文件：{pattern}")
