"""
04 验潮站外推 - MATCH 算子包装器 (04-MATCH)
输入：NC 卫星数据 + TXT 验潮站数据
输出：NPZ 匹配文件 (MATCHED_*.npz)
"""

from typing import Dict, Any, Optional
import os
import numpy as np
from pathlib import Path
import re

from core.base_operator import BaseOperator
from core.op_config import LocalConfig


class YczMatchOperator(BaseOperator):
    """验潮站匹配算子 (04-MATCH)"""
    
    def __init__(self, config: LocalConfig):
        super().__init__(config)
        
    @property
    def supported_sats(self):
        return {"S6A", "JA3", "HY-1D", "HY-2A", "HY-2B", "H2B", "S3A", "S3B"}
        
    def validate_config(self) -> None:
        if not self.config.sat_id or self.config.sat_id not in self.supported_sats:
            raise ValueError(f"不支持的卫星：{self.config.sat_id}")
        if not self.config.aux_data_type or self.config.aux_data_type not in ["YCZ", "验潮站"]:
            raise ValueError("辅卫星必须指定为 YCZ 或 验潮站")
            
    def run_local(self, local_input_dir: str) -> Dict[str, Any]:
        """本地执行验潮站 MATCH - XML → MyIPFConfig → func_ycz_matching_pro"""
        import sys
        import time
        from pathlib import Path
        
        src_dir = Path(__file__).parent / "gpf_src" / "04_ycz" / "match"
        
        try:
            import importlib
            # 清理同名模块缓存，避免与其他算子冲突
            _keys_to_remove = [k for k in sys.modules.keys() if k == "IPFUtils" or k.startswith("func_")]
            for _k in _keys_to_remove:
                del sys.modules[_k]
            # 移除其他 gpf_src 路径，防止串味
            sys.path[:] = [p for p in sys.path if "/gpf_src/" not in p.replace("\\", "/")]
            sys.path.insert(0, str(src_dir))
            
            from IPFUtils import MyIPFConfig, Logger
            mod = importlib.import_module("func_GLSY_ALT_GDR_AUX_YCZ_MATCH")
            
            if not hasattr(mod, "func_ycz_matching_pro"):
                raise AttributeError(f"未找到 func_ycz_matching_pro，可用：{[n for n in dir(mod) if n.startswith('func_')]}")
            
            func = getattr(mod, "func_ycz_matching_pro")
            
            # 生成 XML (Gpf_Job_Order 格式，带 MSS_PATH/FES2014_PATH)
            job_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Gpf_Job_Order>
    <Gpf_Conf>
        <Processor_Name>gl_ssh_ycz_match_pro</Processor_Name>
        <Version>{self.config.version}</Version>
        <Order_Id>{self.config.order_id or 0}</Order_Id>
        <Dynamic_Processing_Parameters count="8">
            <Processing_Parameter><Name>Sat_ID</Name><Value>{self.config.sat_id}</Value></Processing_Parameter>
            <Processing_Parameter><Name>AUX_YCZ</Name><Value>{self.config.aux_ycz or "WS_YCZ"}</Value></Processing_Parameter>
            <Processing_Parameter><Name>Data_version</Name><Value>{self.config.data_version.lstrip('V')}</Value></Processing_Parameter>
            <Processing_Parameter><Name>Product_Type</Name><Value>SSH</Value></Processing_Parameter>
            <Processing_Parameter><Name>Start_date</Name><Value>{self.config.start_date}</Value></Processing_Parameter>
            <Processing_Parameter><Name>End_date</Name><Value>{self.config.end_date}</Value></Processing_Parameter>
            <Processing_Parameter><Name>MSS_PATH</Name><Value>{self.config.mss_path or "./data/input/DTU18MSS_1min.nc"}</Value></Processing_Parameter>
            <Processing_Parameter><Name>FES2014_PATH</Name><Value>{self.config.fes2014_path or "./data/input/FES2014/ocean_tide"}</Value></Processing_Parameter>
        </Dynamic_Processing_Parameters>
    </Gpf_Conf>
    <List_of_Gpf_Procs count="1">
        <Gpf_Proc>
            <Task_Name>gl_ssh_ycz_match_pro</Task_Name>
            <Task_Version>1.0</Task_Version>
            <List_of_Inputs count="2">
                <Input>
                    <File_Type>AUX_{self.config.sat_id.upper()}_ALT_GDR</File_Type>
                    <File_Name_Type>Directory</File_Name_Type>
                    <List_of_File_Names count="1"><File_Name>{local_input_dir}</File_Name></List_of_File_Names>
                </Input>
                <Input>
                    <File_Type>AUX_WS_YCZ</File_Type>
                    <File_Name_Type>Directory</File_Name_Type>
                    <List_of_File_Names count="1"><File_Name>{self.config.ycz_data_dir or "./data/input/WSTG"}</File_Name></List_of_File_Names>
                </Input>
            </List_of_Inputs>
            <List_of_Outputs count="1">
                <Output>
                    <File_Type>GL_SSH_YCZ_MATCH_RESULT</File_Type>
                    <File_Name_Type>Directory</File_Name_Type>
                    <File_Name>{self.config.output_dir or "./output"}</File_Name>
                </Output>
            </List_of_Outputs>
        </Gpf_Proc>
    </List_of_Gpf_Procs>
</Gpf_Job_Order>'''
            
            out_dir = Path(self.config.output_dir or "./output")
            out_dir.mkdir(parents=True, exist_ok=True)
            xml_file = out_dir / f"job_ycz_match_{self.config.sat_id}_{self.config.start_date}_{int(time.time())}.xml"
            xml_file.write_text(job_xml, encoding="utf-8")
            
            # 初始化日志
            str_order_id = "%010d" % int(self.config.order_id or 0)
            log_file = out_dir / f"log_gl_ssh_ycz_match_pro_{self.config.version}_{str_order_id}.txt"
            os.makedirs(out_dir, exist_ok=True)
            Logger(str(log_file), "gl_ssh_ycz_match_pro", self.config.version)
            
            t0 = time.time()
            func(MyIPFConfig(str(xml_file)))
            elapsed = time.time() - t0
            
            # 检查输出 (MATCHED_*.npz)
            npz_files = list(out_dir.glob("**/MATCHED_*.npz"))
            
            return {
                "status": "success",
                "function": "func_ycz_matching_pro",
                "execution_time": elapsed,
                "job_xml": str(xml_file),
                "log_file": str(log_file),
                "output_dir": str(out_dir),
                "n_matched_files": len(npz_files),
                "matched_files": [str(f) for f in npz_files[:10]]
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
        """加载验潮站匹配结果"""
        from pathlib import Path
        
        output_path = Path(output_dir)
        sat = self.config.sat_id
        
        # 查找 MATCHED_*.npz 文件
        npz_files = list(output_path.glob("MATCHED_*.npz"))
        if not npz_files:
            return {"status": "empty", "message": "未找到 MATCHED 文件"}
        
        results = []
        for npz_file in npz_files:
            with np.load(str(npz_file), allow_pickle=True) as f:
                records = f.get('match_records', np.array([]))
                if len(records) > 0:
                    rec = records[0] if isinstance(records[0], np.ndarray) else records
                    results.append({
                        "file": str(npz_file),
                        "n_records": len(records),
                        "sample_record_keys": list(rec.dtype.names) if hasattr(rec, 'dtype') and rec.dtype.names else list(rec.keys()) if isinstance(rec, dict) else None,
                        "shape": records.shape
                    })
        
        return {"status": "loaded", "files": results}
