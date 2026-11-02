"""
02 星星自交叉 - CAL 算子包装器
输入：自交叉 MATCH 生成的 CSV/NPZ
输出：定标统计 JSON/图表
"""

from typing import Dict, Any, Optional
import numpy as np
import pandas as pd
from pathlib import Path
import re

from core.base_operator import BaseOperator
from core.op_config import LocalConfig


class SelfCrossCalOperator(BaseOperator):
    """星星自交叉定标算子 (02-CAL)"""
    
    def __init__(self, config: LocalConfig):
        super().__init__(config)
        
    def validate_config(self) -> None:
        if not self.config.sat_id:
            raise ValueError("必须指定 sat_id")
    
    def run_local(self, local_input_dir: str) -> Dict[str, Any]:
        """本地执行自交叉定标 - 复用 01-CAL 的实现"""
        # 02-CAL 和 01-CAL 逻辑相似，复用 star_cross_cal 的 run_local
        from .star_cross_cal import StarCrossCalOperator
        return StarCrossCalOperator(self.config).run_local(local_input_dir)
        
    def run_ssh(self, ssh_client) -> Dict[str, Any]:
        """通过 SSH 执行远程自交叉定标"""
        from data_adapter.ssh_executor import SSHExecutor
        
        job_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Gpf_Job_Order>
    <Gpf_Conf>
        <Processor_Name>gl_ssh_self_cross_cal_pro</Processor_Name>
        <Version>1.0</Version>
        <Order_Id>{self.config.order_id or 0}</Order_Id>
        <Dynamic_Processing_Parameters count="5">
            <Processing_Parameter><Name>Sat_ID</Name><Value>{self.config.sat_id}</Value></Processing_Parameter>
            <Processing_Parameter><Name>Data_version</Name><Value>001</Value></Processing_Parameter>
            <Processing_Parameter><Name>Product_Type</Name><Value>L2B_SELF_CAL</Value></Processing_Parameter>
            <Processing_Parameter><Name>Start_date</Name><Value>{self.config.start_date}</Value></Processing_Parameter>
            <Processing_Parameter><Name>End_date</Name><Value>{self.config.end_date}</Value></Processing_Parameter>
        </Dynamic_Processing_Parameters>
        <List_of_Inputs count="1">
            <Input><File_Type>MATCH_DATA</File_Type><File_Name_Type>Directory</File_Name_Type><List_of_File_Names count="1"><File_Name>{self.config.input_dir}</File_Name></List_of_File_Names></Input>
        </List_of_Inputs>
        <List_of_Outputs count="1">
            <Output><File_Type>CALIBRATION_RESULT</File_Type><File_Name_Type>Directory</File_Name_Type><File_Name>{self.config.output_dir or './output'}</File_Name></Output>
        </List_of_Outputs>
    </Gpf_Conf>
    <List_of_Gpf_Procs count="1">
        <Gpf_Proc>
            <Task_Name>gl_ssh_self_cross_cal_pro</Task_Name>
            <Task_Version>1.0</Task_Version>
            <List_of_Inputs count="1">
                <Input><File_Type>MATCH_DATA</File_Type><File_Name_Type>Directory</File_Name_Type><List_of_File_Names count="1"><File_Name>{self.config.input_dir}</File_Name></List_of_File_Names></Input>
            </List_of_Inputs>
            <List_of_Outputs count="1">
                <Output><File_Type>CALIBRATION_RESULT</File_Type><File_Name_Type>Directory</File_Name_Type><File_Name>{self.config.output_dir or './output'}</File_Name></Output>
            </List_of_Outputs>
        </Gpf_Proc>
    </List_of_Gpf_Procs>
</Gpf_Job_Order>'''
        
        executor = SSHExecutor()
        result = executor.execute_xml_job(
            ssh_client=ssh_client,
            xml_content=job_xml,
            module_name="gl_ssh_self_cross_cal_pro",
            remote_workdir="/home/leehir/GPF/02-星星自交叉法v2.0/CVS_SELF_GLSY_ALT_GDR_AUX_SAT_CAL"
        )
        
        return result
    
    def load_output(self, output_dir: str) -> Dict[str, Any]:
        """加载自交叉定标结果"""
        from pathlib import Path
        import json
        
        output_path = Path(output_dir)
        sat = self.config.sat_id
        
        # 查找 NPZ 校准结果
        npz_pattern = rf"calibration_data_{sat}_self_cross_\d{{8}}_\d{{8}}\.npz$"
        
        results = []
        for p in output_path.glob("**/*.npz"):
            if re.search(npz_pattern, p.name, re.I):
                with np.load(str(p), allow_pickle=True) as f:
                    results.append({
                        "n_samples": len(f.get('ssh_asc', [])),
                        "slope": float(f.get('slope', 0)),
                        "intercept": float(f.get('intercept', 0)),
                        "r_squared": float(f.get('r_squared', 0)),
                        "rmse": float(f.get('rmse', 0)),
                        "file": str(p)
                    })
        
        return results if results else {}
