"""
04 验潮站外推 - CAL 算子包装器 (04-CAL)
输入：验潮站 MATCH 生成的 NPZ 文件
输出：定标 JSON/DOCX 报告/PNG 图表
"""

from typing import Dict, Any, Optional
import os
import numpy as np
from pathlib import Path
import re

from core.base_operator import BaseOperator
from core.op_config import LocalConfig


class YczCalOperator(BaseOperator):
    """验潮站定标算子 (04-CAL)"""
    
    def __init__(self, config: LocalConfig):
        super().__init__(config)
        
    def validate_config(self) -> None:
        if not self.config.sat_id:
            raise ValueError("必须指定 sat_id")
            
    def run_local(self, local_input_dir: str) -> Dict[str, Any]:
        """本地执行 04-CAL (验潮站) - XML → MyIPFConfig → func_ycz_cal_pro"""
        import sys
        import time
        from pathlib import Path
        
        src_dir = Path(__file__).parent / "gpf_src" / "04_ycz" / "cal"
        sys.path.insert(0, str(src_dir))
        
        try:
            from IPFUtils import MyIPFConfig, Logger
            import importlib
            sys.modules.pop("func_GLSY_ALT_AUX_YCZ_GDR_CAL", None)
            sys.modules.pop("IPFUtils", None)
            mod = importlib.import_module("func_GLSY_ALT_AUX_YCZ_GDR_CAL")
            
            if not hasattr(mod, "func_ycz_cal_pro"):
                raise AttributeError(f"未找到 func_ycz_cal_pro，可用：{[n for n in dir(mod) if n.startswith('func_')]}")
            
            func = getattr(mod, "func_ycz_cal_pro")
            
            job_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Gpf_Job_Order>
    <Gpf_Conf>
        <Processor_Name>gl_ssh_ycz_cal_pro</Processor_Name>
        <Version>{self.config.version}</Version>
        <Order_Id>{self.config.order_id or 0}</Order_Id>
        <Dynamic_Processing_Parameters count="9">
            <Processing_Parameter><Name>Sat_ID</Name><Value>{self.config.sat_id}</Value></Processing_Parameter>
            <Processing_Parameter><Name>Data_version</Name><Value>{self.config.data_version.lstrip('V')}</Value></Processing_Parameter>
            <Processing_Parameter><Name>Match_Data_Type</Name><Value>GL_SSH_YCZ_MATCH_RESULT</Value></Processing_Parameter>
            <Processing_Parameter><Name>Product_Type</Name><Value>SSH</Value></Processing_Parameter>
            <Processing_Parameter><Name>Start_date</Name><Value>{self.config.start_date}</Value></Processing_Parameter>
            <Processing_Parameter><Name>End_date</Name><Value>{self.config.end_date}</Value></Processing_Parameter>
            <Processing_Parameter><Name>Template_docx</Name><Value>{self.config.template_docx or "./data/input/MCS_GL_ALT_YCZ.docx"}</Value></Processing_Parameter>
            <Processing_Parameter><Name>AUX_YCZ</Name><Value>{self.config.aux_ycz or "YCZ"}</Value></Processing_Parameter>
            <Processing_Parameter><Name>MSS_PATH</Name><Value>{self.config.mss_path or "./data/input/DTU18MSS_1min.nc"}</Value></Processing_Parameter>
            <Processing_Parameter><Name>FES2014_PATH</Name><Value>{self.config.fes2014_path or "./data/input/FES2014/ocean_tide"}</Value></Processing_Parameter>
        </Dynamic_Processing_Parameters>
    </Gpf_Conf>
    <List_of_Gpf_Procs count="1">
        <Gpf_Proc>
            <Task_Name>gl_ssh_ycz_cal_pro</Task_Name>
            <Task_Version>1.0</Task_Version>
            <List_of_Inputs count="2">
                <Input>
                    <File_Type>GL_SSH_YCZ_MATCH_RESULT</File_Type>
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
                    <File_Type>GL_SSH_YCZ_CAL_RESULT</File_Type>
                    <File_Name_Type>Directory</File_Name_Type>
                    <File_Name>{self.config.output_dir or "./output"}</File_Name>
                </Output>
            </List_of_Outputs>
        </Gpf_Proc>
    </List_of_Gpf_Procs>
</Gpf_Job_Order>'''
            
            out_dir = Path(self.config.output_dir or "./output")
            out_dir.mkdir(parents=True, exist_ok=True)
            xml_file = out_dir / f"job_ycz_cal_{self.config.sat_id}_{self.config.start_date}_{int(time.time())}.xml"
            xml_file.write_text(job_xml, encoding="utf-8")
            
            str_order_id = "%010d" % int(self.config.order_id or 0)
            log_file = out_dir / f"log_gl_ssh_ycz_cal_pro_{self.config.version}_{str_order_id}.txt"
            os.makedirs(out_dir, exist_ok=True)
            Logger(str(log_file), "gl_ssh_ycz_cal_pro", self.config.version)
            
            # 04-CAL 的 IPFUtils 不解析 Match_Data_Type, 但 func 需要 - 手动补充
            ipf_config = MyIPFConfig(str(xml_file))
            ipf_config.Match_Data_Type = "GL_SSH_YCZ_MATCH_RESULT"
            
            t0 = time.time()
            func(ipf_config)
            elapsed = time.time() - t0
            
            # 检查输出 (JSON + DOCX + PNG)
            json_files = list(out_dir.glob("**/calibration_result_*.json"))
            docx_files = list(out_dir.glob("**/calibration_report_*.docx"))
            png_files = list(out_dir.glob("**/*.png"))
            
            return {
                "status": "success",
                "function": "func_ycz_cal_pro",
                "execution_time": elapsed,
                "job_xml": str(xml_file),
                "log_file": str(log_file),
                "output_dir": str(out_dir),
                "n_json": len(json_files),
                "n_docx": len(docx_files),
                "n_png": len(png_files),
                "json_files": [str(f) for f in json_files[:5]],
                "docx_files": [str(f) for f in docx_files[:3]],
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
        """加载验潮站定标结果"""
        from pathlib import Path
        import json
        
        output_path = Path(output_dir)
        sat = self.config.sat_id
        
        results = {
            "json_report": None,
            "docx_report": None,
            "charts": [],
            "stations": {}
        }
        
        # 查找 JSON 报告
        json_pattern = rf"calibration_result_{sat}_vs_YCZ_\d{{8}}_\d{{8}}\.json$"
        for p in output_path.glob("**/*.json"):
            if re.search(json_pattern, p.name, re.I):
                with open(p, 'r', encoding='utf-8') as f:
                    results["json_report"] = json.load(f)
                
                # 解析各站点统计
                json_data = results["json_report"]
                sites = ["zhiwan", "wailingding", "dangan"]
                for site in sites:
                    site_key = f"${{aft_bias_{site}}}"
                    if site_key in json_data:
                        results["stations"][site] = {
                            "bias_m": float(json_data.get(f"${{aft_bias_{site}}}", 0)),
                            "std_m": float(json_data.get(f"${{aft_std_{site}}}", 0)),
                            "n_cycles": int(json_data.get(f"${{aft_num_{site}}}", 0))
                        }
        
        # 查找 DOCX 报告
        docx_pattern = rf"calibration_report_{sat}_vs_YCZ_\d{{8}}_\d{{8}}\.docx$"
        for p in output_path.glob("**/*.docx"):
            if re.search(docx_pattern, p.name, re.I):
                results["docx_report"] = str(p)
                break
        
        # 查找趋势图/直方图
        for p in output_path.glob("**/*.png"):
            if "CAL_TREND" in p.name or "HIST" in p.name:
                results["charts"].append(str(p))
        
        return results
