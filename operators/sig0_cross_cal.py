"""
03 SIG0 交叉定标算子包装器 (03-CAL)
输入：HDF5 交叉点文件 (XOver_data_*.h5)
输出：DOCX 报告 + JSON 统计 + PNG 图表
依赖：CrossOverCalibration.py, XOver.py
"""

from typing import Dict, Any, Optional
import os
import numpy as np
from pathlib import Path
import re

from core.base_operator import BaseOperator
from core.op_config import LocalConfig


class Sig0CrossCalOperator(BaseOperator):
    """SIG0 交叉定标算子 (03-CAL)"""
    
    def __init__(self, config: LocalConfig):
        super().__init__(config)
        
    def validate_config(self) -> None:
        if not self.config.sat_id:
            raise ValueError("必须指定 sat_id")
            
    def run_local(self, local_input_dir: str) -> Dict[str, Any]:
        """本地执行 SIG0 CAL - XML → MyIPFConfig → func_cross_cal_pro"""
        import sys
        import time
        from pathlib import Path
        
        src_dir = Path(__file__).parent / "gpf_src" / "03_sig0_cross" / "cal"
        sys.path.insert(0, str(src_dir))
        
        try:
            from IPFUtils import MyIPFConfig, Logger
            import importlib
            sys.modules.pop("func_GLSY_ALT_AUX_Sat_GDR_SIG0_CAL", None)
            sys.modules.pop("IPFUtils", None)
            mod = importlib.import_module("func_GLSY_ALT_AUX_Sat_GDR_SIG0_CAL")
            
            if not hasattr(mod, "func_cross_cal_pro"):
                raise AttributeError(f"未找到 func_cross_cal_pro，可用：{[n for n in dir(mod) if n.startswith('func_')]}")
            
            func = getattr(mod, "func_cross_cal_pro")
            
            job_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Gpf_Job_Order>
    <Gpf_Conf>
        <Processor_Name>gl_sig0_cross_cal_pro</Processor_Name>
        <Version>{self.config.version}</Version>
        <Order_Id>{self.config.order_id or 0}</Order_Id>
        <Dynamic_Processing_Parameters count="8">
            <Processing_Parameter><Name>Sat_ID</Name><Value>{self.config.sat_id}</Value></Processing_Parameter>
            <Processing_Parameter><Name>AUX_Sat</Name><Value>{self.config.aux_data_type}</Value></Processing_Parameter>
            <Processing_Parameter><Name>Data_version</Name><Value>{self.config.data_version.lstrip('V')}</Value></Processing_Parameter>
            <Processing_Parameter><Name>Match_Data_Type</Name><Value>GL_S6_SIG0_CROSS_MATCH_RESULT</Value></Processing_Parameter>
            <Processing_Parameter><Name>Product_Type</Name><Value>SIG0</Value></Processing_Parameter>
            <Processing_Parameter><Name>Start_date</Name><Value>{self.config.start_date}</Value></Processing_Parameter>
            <Processing_Parameter><Name>End_date</Name><Value>{self.config.end_date}</Value></Processing_Parameter>
            <Processing_Parameter><Name>Template_docx</Name><Value>{self.config.template_docx or "./doc"}</Value></Processing_Parameter>
        </Dynamic_Processing_Parameters>
    </Gpf_Conf>
    <List_of_Gpf_Procs count="1">
        <Gpf_Proc>
            <Task_Name>gl_sig0_cross_cal_pro</Task_Name>
            <Task_Version>1.0</Task_Version>
            <List_of_Inputs count="1">
                <Input>
                    <File_Type>GL_S6_SIG0_CROSS_MATCH_RESULT</File_Type>
                    <File_Name_Type>Directory</File_Name_Type>
                    <List_of_File_Names count="1"><File_Name>{local_input_dir}</File_Name></List_of_File_Names>
                </Input>
            </List_of_Inputs>
            <List_of_Outputs count="1">
                <Output>
                    <File_Type>GL_S6_SIG0_CROSS_CAL_RESULT</File_Type>
                    <File_Name_Type>Directory</File_Name_Type>
                    <File_Name>{self.config.output_dir or "./output"}</File_Name>
                </Output>
            </List_of_Outputs>
        </Gpf_Proc>
    </List_of_Gpf_Procs>
</Gpf_Job_Order>'''
            
            out_dir = Path(self.config.output_dir or "./output")
            out_dir.mkdir(parents=True, exist_ok=True)
            xml_file = out_dir / f"job_sig0_cal_{self.config.sat_id}_{self.config.start_date}_{int(time.time())}.xml"
            xml_file.write_text(job_xml, encoding="utf-8")
            
            str_order_id = "%010d" % int(self.config.order_id or 0)
            log_file = out_dir / f"log_gl_sig0_cross_cal_pro_{self.config.version}_{str_order_id}.txt"
            os.makedirs(out_dir, exist_ok=True)
            Logger(str(log_file), "gl_sig0_cross_cal_pro", self.config.version)
            
            # 03-CAL 的 IPFUtils 不解析 Match_Data_Type, 但 func 需要 - 手动补充
            ipf_config = MyIPFConfig(str(xml_file))
            ipf_config.Match_Data_Type = "GL_S6_SIG0_CROSS_MATCH_RESULT"
            
            t0 = time.time()
            func(ipf_config)
            elapsed = time.time() - t0
            
            # 检查输出 (DOCX + JSON + PNG)
            docx_files = list(out_dir.glob("**/MCS_GL_*.docx"))
            json_files = list(out_dir.glob("**/*.json"))
            png_files = list(out_dir.glob("**/*.png"))
            
            return {
                "status": "success",
                "function": "func_cross_cal_pro",
                "execution_time": elapsed,
                "job_xml": str(xml_file),
                "log_file": str(log_file),
                "output_dir": str(out_dir),
                "n_docx": len(docx_files),
                "n_json": len(json_files),
                "n_png": len(png_files),
                "docx_files": [str(f) for f in docx_files[:5]],
                "json_files": [str(f) for f in json_files[:5]],
                "png_files": [str(f) for f in png_files[:10]]
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
        """加载定标报告结果"""
        from pathlib import Path
        import json
        
        output_path = Path(output_dir)
        
        results = {
            "docx_reports": [],
            "json_results": [],
            "charts": []
        }
        
        # 查找 DOCX 报告
        for p in output_path.glob("**/*.docx"):
            if "MCS_GL_ALT" in p.name:
                results["docx_reports"].append(str(p))
        
        # 查找 JSON 摘要
        for p in output_path.glob("**/*.json"):
            if "summary" in p.name.lower() or "processing" in p.name.lower():
                with open(p, 'r', encoding='utf-8') as f:
                    results["json_results"].append({"file": str(p), "data": json.load(f)})
        
        # 查找 PNG 图表
        for p in output_path.glob("**/*_2h.png"):
            results["charts"].append(str(p))
        
        return results
