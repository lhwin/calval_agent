"""
01 星星交叉 - CAL 算子包装器
输入：MATCH 生成的 NPZ 文件
输出：定标结果 JSON/图表
"""

from typing import Dict, Any, Optional
import numpy as np
from pathlib import Path
import re

from core.base_operator import BaseOperator
from core.op_config import LocalConfig


class StarCrossCalOperator(BaseOperator):
    """星星交叉定标算子 (01-CAL)"""
    
    def __init__(self, config: LocalConfig):
        super().__init__(config)
        
    def validate_config(self) -> None:
        if not self.config.sat_id:
            raise ValueError("必须指定 sat_id")
        if not self.config.aux_data_type:
            raise ValueError("必须指定 aux_data_type (辅助卫星 ID)")
        if not self.config.start_date or not self.config.end_date:
            raise ValueError("必须指定 start_date 和 end_date")
            
        from data_adapter.xml_generator import generate_star_cross_cal_xml
        
        
        xml_content = generate_star_cross_cal_xml(
            sat_id=self.config.sat_id,
            match_type=self.config.aux_data_type,
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            input_dir=self.config.input_dir,
            output_dir=self.config.output_dir or "./output"
        )
        
        remote_job_path = f"/tmp/job_cal_{self.config.sat_id}_{self.config.start_date}.xml"
        result = executor.execute_xml_job(
            ssh_client=ssh_client,
            xml_content=xml_content,
            module_name="gl_ssh_cross_cal_pro",
            remote_workdir="/home/leehir/GPF/01-星星交叉法v2.0/csv_glsy_alt_gdr_aux_sat_cal"
        )
        
        return result
    
    def load_output(self, output_dir: str) -> Dict[str, Any]:
        """加载定标结果"""
        from pathlib import Path
        import json
        
        output_path = Path(output_dir)
        sat = self.config.sat_id
        match_type = self.config.aux_data_type
        
        # 查找 calibration_data_*.npz
        cal_pattern = rf"calibration_data_{sat}_vs_{match_type}_(\d{{8}})_(\d{{8}})\.npz$"
        
        results = []
        for p in output_path.glob("**/*.npz"):
            if re.search(cal_pattern, p.name, re.I):
                with np.load(str(p), allow_pickle=True) as f:
                    results.append({
                        "slope": float(f.get('slope', 0)),
                        "intercept": float(f.get('intercept', 0)),
                        "r_squared": float(f.get('r_squared', 0)),
                        "rmse": float(f.get('rmse', 0)),
                        "bias_mean": float(f.get('bias_mean', 0)),
                        "bias_std": float(f.get('bias_std', 0)),
                        "n_samples": int(f.get('n_samples', 0)),
                        "percent01_percent06": [str(f.get(k, '')) for k in ['percent01','percent02','percent03','percent04','percent05','percent06']],
                        "file": str(p)
                    })
        
        # 查找 JSON 结果文件
        json_pattern = rf"calibration_result_{sat}_vs_{match_type}_(\d{{8}})_(\d{{8}})\.json$"
        for p in output_path.glob("**/*.json"):
            if re.search(json_pattern, p.name, re.I):
                with open(p, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                    results[-1]["json_report"] = json_data
        
        return results[0] if results else {}

    def run_local(self, local_input_dir: str) -> Dict[str, Any]:
        """本地执行 01-CAL - XML → MyIPFConfig → func_cross_cal_pro"""
        import sys
        import time
        from pathlib import Path
        
        # 临时添加源码目录到 Python 路径
        src_dir = Path(__file__).parent / "gpf_src" / "01_star_cross" / "cal"
        sys.path.insert(0, str(src_dir))
        
        try:
            # 导入源文件
            from func_GLSY_ALT_AUX_Sat_GDR_CAL import func_cross_cal_pro
            
            # 01-CAL 需要这些属性（即使 IPFUtils 不解析，func 也需要）
            required_attrs = {
                'Sat_ID': self.config.sat_id,
                'AUX_Sat': self.config.aux_data_type,
                'Data_version': self.config.data_version.lstrip('V'),
                'order_id': self.config.order_id or 0,
                'Order_Id': self.config.order_id or 0,
                'Start_date': self.config.start_date,
                'End_date': self.config.end_date,
                'output': str(Path(self.config.output_dir or './output').resolve()),
                'input': str(Path(local_input_dir).resolve()),
                'Match_Data_Type': self.config.aux_data_type,
                'Select_Area': str(self.config.select_area) if self.config.select_area else None,
                'distance_to_coast': int(self.config.distance_to_coast),
                'ocean_depth': int(self.config.ocean_depth),
                'wind_speed': str(self.config.wind_speed) if self.config.wind_speed else '[0,40]',
                'match_time': '24',
                'Match_time': '24',
                'Template_docx': '',  # 可选，没有就留空
            }
            
            # 创建 ipf_config 对象
            class SimpleConfig:
                pass
            
            ipf_config = SimpleConfig()
            for k, v in required_attrs.items():
                setattr(ipf_config, k, v)
            
            # 设置 SimHei 字体路径（如果存在）
            font_ttf = str(src_dir / 'conf' / 'SimHei.ttf')
            if not Path(font_ttf).exists():
                import matplotlib
                matplotlib.use('Agg')  # 非交互式后端
                
            import matplotlib.pyplot as plt
            from matplotlib.font_manager import FontProperties
            plt.rcParams['font.sans-serif'] = ['DejaVu Sans']  # 后备字体
            plt.rcParams['axes.unicode_minus'] = False
            
            # 执行 CAL 函数
            t0 = time.time()
            func_cross_cal_pro(ipf_config)
            elapsed = time.time() - t0
            
            # 检查输出
            out_dir = Path(self.config.output_dir or './output')
            cal_npz = list(out_dir.glob('calibration_data_*.npz'))
            cal_png = list(out_dir.glob('**/*.png'))
            cal_txt = list(out_dir.glob('**/*.txt'))
            
            return {
                'status': 'success',
                'function': 'func_cross_cal_pro',
                'execution_time': elapsed,
                'output_dir': str(out_dir),
                'npz_files': [str(f) for f in cal_npz],
                'png_files': [str(f) for f in cal_png],
                'txt_files': [str(f) for f in cal_txt],
            }
        except Exception as e:
            import traceback
            return {
                'status': 'failed',
                'error': str(e),
                'traceback': traceback.format_exc()[-2000:],
            }
        finally:
            if str(src_dir) in sys.path:
                sys.path.remove(str(src_dir))
