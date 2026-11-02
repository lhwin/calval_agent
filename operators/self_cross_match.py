"""
02 星星自交叉 - MATCH 算子包装器
输入：单颗卫星的多段 NC 数据 (同一颗卫星不同轨道方向)
输出：NPZ 匹配文件 + 每日统计 JSON
"""

from typing import Dict, Any, Optional
import numpy as np
from pathlib import Path
import re

from core.base_operator import BaseOperator
from core.op_config import LocalConfig


class SelfCrossMatchOperator(BaseOperator):
    """星星自交叉匹配算子 (02-MATCH)"""
    
    def __init__(self, config: LocalConfig):
        super().__init__(config)
        
    @property
    def supported_sats(self):
        return {"S6A", "JA3", "HY-1D", "HY-2A", "HY-2B", "S3A", "S3B"}
        
    def validate_config(self) -> None:
        if not self.config.sat_id or self.config.sat_id not in self.supported_sats:
            raise ValueError(f"不支持的卫星：{self.config.sat_id}")
        if not self.config.input_dir:
            raise ValueError("必须指定 input_dir")
            
    def run_local(self, local_input_dir: str) -> Dict[str, Any]:
        """本地执行自交叉 MATCH - 忠实源码: 生成 XML → MyIPFConfig → func_self_cross_matching_pro"""
        import sys
        import time
        from pathlib import Path
        
        src_dir = Path(__file__).parent / "gpf_src" / "02_self_cross" / "match"
        sys.path.insert(0, str(src_dir))
        
        try:
            from IPFUtils import MyIPFConfig
            
            # 找到原函数 (模块名与 01 相同, 需先清缓存避免串味)
            import importlib
            sys.modules.pop("func_GLSY_ALT_GDR_AUX_SAT_MATCH", None)
            sys.modules.pop("IPFUtils", None)
            mod = importlib.import_module("func_GLSY_ALT_GDR_AUX_SAT_MATCH")
            fn = None
            for cand in ("func_self_cross_matching_pro", "func_cross_matching_pro"):
                if hasattr(mod, cand):
                    fn = getattr(mod, cand)
                    break
            if fn is None:
                raise AttributeError(f"未找到匹配函数，模块内可用: {[n for n in dir(mod) if n.startswith('func_')]}")
            
            # 生成 XML 工单
            job_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Processor_Config>
    <Processor_Name>gl_ssh_self_cross_match_pro</Processor_Name>
    <Version>{self.config.version}</Version>
    <Order_Id>{self.config.order_id or 0}</Order_Id>
    <Input>
        <File_Name>{local_input_dir}</File_Name>
    </Input>
    <Input>
        <File_Name>{local_input_dir}</File_Name>
    </Input>
    <Output>
        <File_Type>product</File_Type>
        <File_Name>{self.config.output_dir or "./output"}</File_Name>
    </Output>
    <Processing_Parameters>
        <Processing_Parameter><Name>Sat_ID</Name><Value>{self.config.sat_id}</Value></Processing_Parameter>
        <Processing_Parameter><Name>Data_version</Name><Value>{self.config.data_version.lstrip('V')}</Value></Processing_Parameter>
        <Processing_Parameter><Name>AUX_Sat</Name><Value>{self.config.sat_id}</Value></Processing_Parameter>
        <Processing_Parameter><Name>Start_date</Name><Value>{self.config.start_date}</Value></Processing_Parameter>
        <Processing_Parameter><Name>End_date</Name><Value>{self.config.end_date}</Value></Processing_Parameter>
    </Processing_Parameters>
</Processor_Config>'''
            
            out_dir = Path(self.config.output_dir or "./output")
            out_dir.mkdir(parents=True, exist_ok=True)
            xml_file = out_dir / f"job_self_match_{self.config.sat_id}_{self.config.start_date}_{int(time.time())}.xml"
            xml_file.write_text(job_xml, encoding="utf-8")
            
            ipf_config = MyIPFConfig(str(xml_file))
            ipf_config.input = str(Path(local_input_dir))
            ipf_config.input_AUX = str(Path(local_input_dir))
            
            # 补充动态参数 (01/02-MATCH 必需)
            ipf_config.Select_Area = self.config.select_area
            ipf_config.distance_to_coast = self.config.distance_to_coast
            ipf_config.ocean_depth = self.config.ocean_depth
            ipf_config.wind_speed = self.config.wind_speed
            
            t0 = time.time()
            fn(ipf_config)
            elapsed = time.time() - t0
            
            return {
                "status": "success",
                "function": fn.__name__,
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
    
        # TODO: 需要专门生成自交叉的 XML (Sat_ID 和 AUX_Sat 相同)
        from data_adapter.xml_generator import GPFJobOrder
        
        job = GPFJobOrder(
            processor_name="gl_ssh_self_cross_match_pro",
            params={
                "Sat_ID": self.config.sat_id,
                "Data_version": "001",
                "Product_Type": "L2A_SELF_MATCH",
                "Start_date": self.config.start_date,
                "End_date": self.config.end_date,
            },
            input_dirs={
                "AUX_H2B_ALT_GDR": self.config.input_dir,
            },
            output_dir=self.config.output_dir or "./output",
        )
        
        
        remote_job_path = f"/tmp/job_self_{self.config.sat_id}_{self.config.start_date}.xml"
        result = executor.execute_xml_job(
            ssh_client=ssh_client,
            xml_content=job.to_xml(),
            module_name="gl_ssh_self_cross_match_pro",
            remote_workdir="/home/leehir/GPF/02-星星自交叉法v2.0/CVS_SELF_GLSY_ALT_GDR_AUX_SAT_MATCH"
        )
        
        return result
    
    def load_output(self, output_dir: str) -> Dict[str, Any]:
        """加载自交叉匹配结果"""
        from pathlib import Path
        import json
        
        output_path = Path(output_dir)
        sat = self.config.sat_id
        
        # 查找匹配 CSV 文件
        csv_pattern = rf"{sat}_self_cross_match_\d{{8}}_\d{{8}}\.csv$"
        json_pattern = rf"{sat}_self_cross_match_stats_\d{{8}}_\d{{8}}\.json$"
        npz_pattern = rf"calibration_data_{sat}_self_cross_\d{{8}}_\d{{8}}\.npz$"
        
        results = []
        
        for p in output_path.glob("**/*.csv"):
            if re.search(csv_pattern, p.name, re.I):
                import pandas as pd
                df = pd.read_csv(str(p))
                results.append({
                    "csv_file": str(p),
                    "records": len(df),
                    "columns": list(df.columns)
                })
        
        for p in output_path.glob("**/*.json"):
            if re.search(json_pattern, p.name, re.I):
                with open(p, 'r', encoding='utf-8') as f:
                    stats = json.load(f)
                    results.append({"stats": stats})
        
        return results if results else {}
