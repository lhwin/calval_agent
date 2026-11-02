"""
简化的 GPF XML 工单生成器 - 忠实于原码 MyIPFConfig 期望的格式。

根据真实 template.xml 结构生成，确保与服务器上的 main.py 兼容。
"""

from dataclasses import dataclass
from typing import Optional, List, Dict
import xml.etree.ElementTree as ET


@dataclass
class GPFJobOrder:
    """
    GPF 工单数据类。
    
    对应原码中 MyIPFConfig 解析的 XML 结构:
    - Processor_Name
    - Version  
    - Order_Id
    - Dynamic_Processing_Parameters (Sat_ID, AUX_*, Start_date, End_date, ...)
    - Inputs/Outputs (文件类型→目录映射)
    """
    processor_name: str
    version: str = "1.0"
    order_id: int = 0
    params: Dict[str, str] = None
    input_dirs: Dict[str, str] = None  # File_Type -> Directory
    output_dir: str = "./output"
    
    def __post_init__(self):
        self.params = self.params or {}
        self.input_dirs = self.input_dirs or {}
    
    def to_xml(self) -> str:
        """生成 XML 字符串 (Gpf_Job_Order 格式)"""
        root = ET.Element("Gpf_Job_Order")
        
        # Gpf_Conf 部分
        conf = ET.SubElement(root, "Gpf_Conf")
        ET.SubElement(conf, "Processor_Name").text = self.processor_name
        ET.SubElement(conf, "Version").text = self.version
        ET.SubElement(conf, "Stdout_Log_Level").text = "INFO"
        ET.SubElement(conf, "Stderr_Log_Level").text = "INFO"
        ET.SubElement(conf, "Test").text = "false"
        ET.SubElement(conf, "Order_Id").text = str(self.order_id)
        
        # Dynamic_Processing_Parameters
        dyn_params = ET.SubElement(conf, "Dynamic_Processing_Parameters", count=str(len(self.params)))
        for name, value in self.params.items():
            p_elem = ET.SubElement(dyn_params, "Processing_Parameter")
            ET.SubElement(p_elem, "Name").text = name
            ET.SubElement(p_elem, "Value").text = str(value)
        
        # List_of_Gpf_Procs (单个任务)
        proc_list = ET.SubElement(root, "List_of_Gpf_Procs", count="1")
        proc = ET.SubElement(proc_list, "Gpf_Proc")
        ET.SubElement(proc, "Task_Name").text = self.processor_name
        ET.SubElement(proc, "Task_Version").text = self.version
        
        # Inputs
        if self.input_dirs:
            inputs = ET.SubElement(proc, "List_of_Inputs", count=str(len(self.input_dirs)))
            for file_type, dir_path in self.input_dirs.items():
                inp = ET.SubElement(inputs, "Input")
                ET.SubElement(inp, "File_Type").text = file_type
                ET.SubElement(inp, "File_Name_Type").text = "Directory"
                names = ET.SubElement(inp, "List_of_File_Names", count="1")
                ET.SubElement(names, "File_Name").text = dir_path
        
        # Outputs
        outputs = ET.SubElement(proc, "List_of_Outputs", count="1")
        out = ET.SubElement(outputs, "Output")
        ET.SubElement(out, "File_Type").text = "CALIBRATION_RESULT"
        ET.SubElement(out, "File_Name_Type").text = "Directory"
        ET.SubElement(out, "File_Name").text = self.output_dir
        
        # 美化输出
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode')
    
    @classmethod
    def from_dict(cls, processor_name: str, raw_params: Dict[str, any]) -> "GPFJobOrder":
        """从原始参数字典快速构建工单"""
        # 分离标准参数和自定义参数
        standard = ["Processor_Name", "Version", "Order_Id"]
        params = {k: v for k, v in raw_params.items() if k not in standard}
        
        input_dirs = {}
        if "input_dir" in raw_params:
            input_dirs["AUX_DATA"] = raw_params["input_dir"]
        
        return cls(
            processor_name=processor_name,
            version=raw_params.get("Version", "1.0"),
            order_id=int(raw_params.get("Order_Id", 0)),
            params=params,
            input_dirs=input_dirs,
            output_dir=raw_params.get("output_dir", "./output")
        )


def generate_ycz_match_xml(sat_id: str, aux_ycz: str, start_date: str, end_date: str,
                          input_dir: str = "./input", output_dir: str = "./output") -> str:
    """生成验潮站匹配工单 (Yield 04-MATCH)"""
    job = GPFJobOrder(
        processor_name="gl_ssh_ycz_match_pro",
        params={
            "Sat_ID": sat_id,
            "Data_version": "001",
            "AUX_YCZ": aux_ycz,
            "Product_Type": "SSH",
            "Start_date": start_date,
            "End_date": end_date,
        },
        input_dirs={
            "AUX_H2B_ALT_GDR": input_dir,
            "AUX_WS_YCZ": input_dir,  # 验潮站数据也在同一目录
        },
        output_dir=output_dir,
    )
    return job.to_xml()


def generate_star_cross_match_xml(sat_id: str, aux_sat: str, start_date: str, end_date: str,
                                 input_dir: str = "./input", output_dir: str = "./output") -> str:
    """生成星星交叉匹配工单 (01-MATCH)"""
    job = GPFJobOrder(
        processor_name="gl_ssh_cross_match_pro",
        params={
            "Sat_ID": sat_id,
            "Data_version": "001",
            "AUX_Sat": aux_sat,
            "Product_Type": "L2A_MATCH",
            "Start_date": start_date,
            "End_date": end_date,
            "match_time": "2.0",
        },
        input_dirs={
            "AUX_H2B_ALT_GDR": input_dir,
            "AUX_SAT": input_dir,
        },
        output_dir=output_dir,
    )
    return job.to_xml()


def generate_star_cross_cal_xml(sat_id: str, match_type: str, start_date: str, end_date: str,
                               input_dir: str = "./input", output_dir: str = "./output",
                               match_time: float = 2.0, distance_to_coast: float = 50.0) -> str:
    """生成星星交叉定标工单 (01-CAL)"""
    job = GPFJobOrder(
        processor_name="gl_ssh_cross_cal_pro",
        params={
            "Sat_ID": sat_id,
            "Data_version": "001",
            "Match_Data_Type": match_type,
            "Product_Type": "L2B_ICAL",
            "Start_date": start_date,
            "End_date": end_date,
            "match_time": str(match_time),
            "distance_to_coast": str(distance_to_coast),
        },
        input_dirs={
            "MATCH_DATA": input_dir,  # MATCH 生成的 NPZ
        },
        output_dir=output_dir,
    )
    return job.to_xml()
