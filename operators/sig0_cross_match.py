"""
03 SIG0 交叉匹配算子包装器 (03-MATCH)
输入: 两颗卫星的 NC 数据 (JA3, S6A 等)
输出: HDF5 交叉点文件 (XOver_data_*.h5)
依赖: CrossOverCalibration.py, XOver.py
"""

from typing import Dict, Any, Optional
import os
import numpy as np
from pathlib import Path
import re

from core.base_operator import BaseOperator
from core.op_config import LocalConfig


class Sig0CrossMatchOperator(BaseOperator):
    """SIG0 交叉匹配算子 (03-MATCH)"""
    
    def __init__(self, config: LocalConfig):
        super().__init__(config)
        
    @property
    def supported_sats(self):
        return {"JA3", "S6A", "S3A", "S3B", "HY-1D"}
        
    def validate_config(self) -> None:
        if not self.config.sat_id or self.config.sat_id not in self.supported_sats:
            raise ValueError(f"不支持的主卫星：{self.config.sat_id}")
        if not self.config.aux_data_type or self.config.aux_data_type not in self.supported_sats:
            raise ValueError(f"不支持的辅助卫星：{self.config.aux_data_type}")
            
    def run_local(self, local_input_dir: str) -> Dict[str, Any]:
        """本地执行 SIG0 MATCH - 忠实源码：XML → MyIPFConfig → func_cross_matching_pro"""
        import sys
        import time
        from pathlib import Path
        
        src_dir = Path(__file__).parent / "gpf_src" / "03_sig0_cross" / "match"
        sys.path.insert(0, str(src_dir))
        
        try:
            from IPFUtils import MyIPFConfig, Logger
            import importlib
            sys.modules.pop("func_GLSY_ALT_GDR_AUX_SAT_SIG0_MATCH", None)
            sys.modules.pop("IPFUtils", None)
            mod = importlib.import_module("func_GLSY_ALT_GDR_AUX_SAT_SIG0_MATCH")
            
            if not hasattr(mod, "func_cross_matching_pro"):
                raise AttributeError(f"未找到 func_cross_matching_pro，可用：{[n for n in dir(mod) if n.startswith('func_')]}")
            
            func = getattr(mod, "func_cross_matching_pro")
            
            # 生成 XML (Gpf_Job_Order 格式)
            job_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Gpf_Job_Order>
    <Gpf_Conf>
        <Processor_Name>gl_sig0_cross_match_pro</Processor_Name>
        <Version>{self.config.version}</Version>
        <Order_Id>{self.config.order_id or 0}</Order_Id>
        <Dynamic_Processing_Parameters count="6">
            <Processing_Parameter><Name>Sat_ID</Name><Value>{self.config.sat_id}</Value></Processing_Parameter>
            <Processing_Parameter><Name>AUX_Sat</Name><Value>{self.config.aux_data_type}</Value></Processing_Parameter>
            <Processing_Parameter><Name>Data_version</Name><Value>{self.config.data_version.lstrip('V')}</Value></Processing_Parameter>
            <Processing_Parameter><Name>Product_Type</Name><Value>SIG0</Value></Processing_Parameter>
            <Processing_Parameter><Name>Start_date</Name><Value>{self.config.start_date}</Value></Processing_Parameter>
            <Processing_Parameter><Name>End_date</Name><Value>{self.config.end_date}</Value></Processing_Parameter>
        </Dynamic_Processing_Parameters>
    </Gpf_Conf>
    <List_of_Gpf_Procs count="1">
        <Gpf_Proc>
            <Task_Name>gl_sig0_cross_match_pro</Task_Name>
            <Task_Version>1.0</Task_Version>
            <List_of_Inputs count="2">
                <Input>
                    <File_Type>AUX_{self.config.aux_data_type}_ALT_L2_GDR</File_Type>
                    <File_Name_Type>Directory</File_Name_Type>
                    <List_of_File_Names count="1"><File_Name>{local_input_dir}</File_Name></List_of_File_Names>
                </Input>
                <Input>
                    <File_Type>AUX_{self.config.sat_id}_ALT_L2_GDR</File_Type>
                    <File_Name_Type>Directory</File_Name_Type>
                    <List_of_File_Names count="1"><File_Name>{self.config.aux_input_dir or local_input_dir}</File_Name></List_of_File_Names>
                </Input>
            </List_of_Inputs>
            <List_of_Outputs count="1">
                <Output>
                    <File_Type>GL_S6_SIG0_CROSS_MATCH_RESULT</File_Type>
                    <File_Name_Type>Directory</File_Name_Type>
                    <File_Name>{self.config.output_dir or "./output"}</File_Name>
                </Output>
            </List_of_Outputs>
        </Gpf_Proc>
    </List_of_Gpf_Procs>
</Gpf_Job_Order>'''
            
            out_dir = Path(self.config.output_dir or "./output")
            out_dir.mkdir(parents=True, exist_ok=True)
            xml_file = out_dir / f"job_sig0_match_{self.config.sat_id}_{self.config.start_date}_{int(time.time())}.xml"
            xml_file.write_text(job_xml, encoding="utf-8")
            
            # 初始化日志
            str_order_id = "%010d" % int(self.config.order_id or 0)
            log_file = out_dir / f"log_gl_sig0_cross_match_pro_{self.config.version}_{str_order_id}.txt"
            os.makedirs(out_dir, exist_ok=True)
            Logger(str(log_file), "gl_sig0_cross_match_pro", self.config.version)
            
            t0 = time.time()
            func(MyIPFConfig(str(xml_file)))
            elapsed = time.time() - t0
            
            # 检查输出 (HDF5 文件)
            h5_files = list(out_dir.glob("**/*.h5"))
            
            return {
                "status": "success",
                "function": "func_cross_matching_pro",
                "execution_time": elapsed,
                "job_xml": str(xml_file),
                "log_file": str(log_file),
                "output_dir": str(out_dir),
                "n_h5_files": len(h5_files),
                "h5_files": [str(f) for f in h5_files[:10]]
            }
        except Exception as e:
            import traceback
            return {
                "status": "failed",
                "error": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc()[-3000:]
            }
        finally:
            if str(src_dir) in sys.path:
                sys.path.remove(str(src_dir))
    
    def load_output(self, output_dir: str) -> Dict[str, Any]:
        """加载 HDF5 交叉点结果"""
        import h5py
        from pathlib import Path
        
        output_path = Path(output_dir)
        
        h5_files = list(output_path.glob("XOver_data_*.h5"))
        if not h5_files:
            return {"status": "empty", "message": "未找到 HDF5 文件"}
        
        results = []
        for h5_file in h5_files:
            try:
                with h5py.File(str(h5_file), 'r') as f:
                    # 列出所有 dataset 名称
                    datasets = list(f.keys())
                    results.append({
                        "file": str(h5_file),
                        "size_mb": h5_file.stat().st_size / 1024 / 1024,
                        "datasets": datasets[:10],  # 只显示前 10 个
                        "n_datasets": len(datasets)
                    })
            except Exception as e:
                results.append({"file": str(h5_file), "error": str(e)})
        
        return {"status": "loaded", "files": results}
