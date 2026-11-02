"""
SSH 算子执行器 - 远程调用 GPF main.py

每个算子通过 SSH 执行对应的 main.py，传递 XML 工单或直接参数。
"""

import subprocess
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class SSHExecutionResult:
    """SSH 执行结果"""
    operator_type: str
    status: str  # "success", "failed", "timeout"
    exit_code: Optional[int]
    stdout: str
    stderr: str
    execution_time: float
    output_files: List[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "operator_type": self.operator_type,
            "status": self.status,
            "exit_code": self.exit_code,
            "stdout": self.stdout[-5000:] if len(self.stdout) > 5000 else self.stdout,
            "stderr": self.stderr[-5000:] if len(self.stderr) > 5000 else self.stderr,
            "execution_time": self.execution_time,
            "output_files": self.output_files or []
        }


class SSHExecutor:
    """
    执行远程 GPF 算子 (通过 SSH)。
    
    模式:
    1. XML 工单模式：传 template.xml 文件
    2. 命令行参数模式：直接传参数
    """
    
    def __init__(self, host: str, username: str, key_path: str = None):
        self.host = host
        self.username = username
        self.key_path = key_path or "~/.ssh/id_ed25519"
        
    def _build_ssh_cmd(self, cmd: str) -> List[str]:
        """构建 SSH 命令"""
        ssh_opts = f"-i {self.key_path} -o StrictHostKeyChecking=no"
        if self.key_path == "~/.ssh/id_ed25519":
            # Windows git-bash 路径转换
            key_path_resolved = Path(self.key_path).expanduser()
            if key_path_resolved.exists():
                ssh_opts = f'-i "{key_path_resolved}" -o StrictHostKeyChecking=no'
        
        return [
            "ssh", ssh_opts,
            f"{self.username}@{self.host}",
            cmd
        ]
    
    def execute(
        self,
        operator_info: Dict[str, Any],
        params: Dict[str, Any],
        timeout: int = 300
    ) -> SSHExecutionResult:
        """
        执行远程算子。
        
        Args:
            operator_info: {"type": "star_cross_cal", "path": ".../csv_glsy_alt_gdr_aux_sat_cal"}
            params: {"start_date": "20230501", "end_date": "20230504", "sat_id": "S6A", ...}
            timeout: 超时秒数
        
        Returns:
            SSHExecutionResult
        """
        op_type = operator_info.get("type")
        module_path = operator_info.get("path", "")
        main_py = "main.py"
        
        # 构建 XML 工单内容 (根据参数生成)
        xml_content = self._generate_xml_template(op_type, params)
        
        # 写入临时 XML 文件
        tmp_dir = Path("temp")
        tmp_dir.mkdir(exist_ok=True)
        xml_file = tmp_dir / f"template_{op_type}_{int(time.time())}.xml"
        
        with open(xml_file, "w", encoding="utf-8") as f:
            f.write(xml_content)
        
        # 上传 XML 到服务器 (SCP)
        remote_base = "/home/leehir/GPF"
        remote_tmp = f"{remote_base}/temp_work"
        
        scp_cmd = [
            "scp", f"-i {self.key_path}", "-o", "StrictHostKeyChecking=no",
            str(xml_file),
            f"{self.username}@{self.host}:{remote_tmp}/"
        ]
        
        try:
            result = subprocess.run(
                scp_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return SSHExecutionResult(
                    operator_type=op_type,
                    status="failed",
                    exit_code=result.returncode,
                    stdout="",
                    stderr=f"SCP upload failed: {result.stderr}",
                    execution_time=0
                )
            
            # 执行远程 main.py
            remote_xml = f"{remote_tmp}/{xml_file.name}"
            remote_main = f"{remote_base}/{module_path}/{main_py}"
            
            exec_cmd = f'cd "$(dirname "{remote_main}")" && python3 "{remote_main}" "{remote_xml}"'
            
            start = time.time()
            result = subprocess.run(
                self._build_ssh_cmd(exec_cmd),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            elapsed = time.time() - start
            
            # 下载输出文件 (如果成功)
            output_files = []
            if result.returncode == 0:
                output_files = self._fetch_output_files(remote_base, module_path)
            
            return SSHExecutionResult(
                operator_type=op_type,
                status="success" if result.returncode == 0 else "failed",
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time=elapsed,
                output_files=output_files
            )
            
        except subprocess.TimeoutExpired:
            return SSHExecutionResult(
                operator_type=op_type,
                status="timeout",
                exit_code=None,
                stdout="",
                stderr=f"Execution timeout after {timeout}s",
                execution_time=timeout
            )
        finally:
            # 清理临时文件
            if xml_file.exists():
                xml_file.unlink()
    
    def _generate_xml_template(self, op_type: str, params: Dict[str, Any]) -> str:
        """生成 XML 工单模板"""
        # 根据算子类型填充不同的 XML 结构
        # 这里简化为通用模板
        
        sat_id = params.get("sat_id", "UNKNOWN")
        aux_type = params.get("aux_data_type", "UNKNOWN")
        start = params.get("start_date", "20230101")
        end = params.get("end_date", "20231231")
        
        # 根据算子类型调整 XML 结构
        processor_name = op_type.upper().replace("_", " ")
        
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<Processor_Config>
    <Processor_Name>{processor_name}</Processor_Name>
    <Version>V01</Version>
    <Order_Id>0</Order_Id>
    <Input>
        <File_Name>{params.get("input_dir", "./input")}</File_Name>
        <Sat_ID>{sat_id}</Sat_ID>
        <AUX_Sat>{aux_type}</AUX_Sat>
        <Start_date>{start}</Start_date>
        <End_date>{end}</End_date>
    </Input>
    <Output>
        <File_Type>calibration_result</File_Type>
        <File_Name>{params.get("output_dir", "./output")}</File_Name>
        <outputFileType>product</outputFileType>
    </Output>
    <Processing_Parameters>
        <Processing_Parameter>
            <Name>match_time</Name>
            <Value>{params.get("match_time", 2.0)}</Value>
        </Processing_Parameter>
        <Processing_Parameter>
            <Name>distance_to_coast</Name>
            <Value>{params.get("distance_to_coast", 50.0)}</Value>
        </Processing_Parameter>
        <Processing_Parameter>
            <Name>ocean_depth</Name>
            <Value>{params.get("ocean_depth", 1000.0)}</Value>
        </Processing_Parameter>
    </Processing_Parameters>
</Processor_Config>
'''
    
    def _fetch_output_files(self, base: str, module: str) -> List[str]:
        """抓取生成的输出文件列表"""
        # 简化：列出 output 目录下的文件
        list_cmd = f'find "{base}/{module}/output" -type f \\( -name "*.npz" -o -name "*.xml" -o -name "*.txt" -o -name "*.png" \\) 2>/dev/null | head -20'
        
        try:
            result = subprocess.run(
                self._build_ssh_cmd(list_cmd),
                capture_output=True,
                text=True,
                timeout=10
            )
            files = [f for f in result.stdout.strip().split('\n') if f]
            return files
        except:
            return []
