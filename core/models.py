"""
Data models for Cal/Val Agent based on GPF original structures.
Respects original IPFConfig and output formats.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pathlib import Path


@dataclass
class TaskRequest:
    """Parsed task request from natural language or explicit config."""
    
    primary_sat: str
    aux_data_type: str  # Could be satellite ID, "YCZ" for tide station, "SELF" for self-cross
    method: Literal[
        "star_cross_calibration", 
        "self_cross_calibration", 
        "tide_station_extension"
    ]
    start_date: str  # YYYYMMDD
    end_date: str  # YYYYMMDD
    data_version: str = "V001"
    
    # Optional filters
    lat_range: Optional[List[float]] = None  # [min_lat, max_lat]
    lon_range: Optional[List[float]] = None  # [min_lon, max_lon]
    match_time_hours: Optional[float] = None
    distance_to_coast_km: Optional[float] = None
    wind_speed_range: Optional[List[float]] = None
    
    # Metadata
    order_id: Optional[int] = None
    template_docx: Optional[str] = None


@dataclass
class DatasetInfo:
    """Information about available datasets on remote server."""
    
    path: str
    file_type: str  # "npz", "nc", "csv"
    date_range: tuple[str, str]  # (start, end)
    sat_ids: List[str]
    sample_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CalibrationResult:
    """Standardized output from calibration operators."""
    
    # Statistics (in meters, consistent with GPF original)
    bias_mean: float
    bias_std: float
    rmse: float
    bias_median: float
    
    # Regression results
    slope: Optional[float] = None
    intercept: Optional[float] = None  # in meters
    r_squared: Optional[float] = None
    
    # Sample info
    n_samples_initial: int
    n_samples_final: int
    outlier_count: int
    
    # QC statistics (percentages)
    qc_pass_area: Optional[float] = None
    qc_pass_coast: Optional[float] = None
    qc_pass_depth: Optional[float] = None
    qc_pass_wind: Optional[float] = None
    
    # Output file paths
    output_dir: Optional[str] = None
    json_path: Optional[str] = None
    txt_path: Optional[str] = None
    plot_path: Optional[str] = None
    npz_path: Optional[str] = None
    docx_path: Optional[str] = None
    product_xml: Optional[str] = None
    
    # Execution info
    status: Literal["success", "partial", "failed"] = "success"
    error_message: Optional[str] = None
    execution_time_seconds: Optional[float] = None


@dataclass
class FallbackDecision:
    """Fallback strategy decision when primary fails."""
    
    triggered: bool
    reason: str  # "low_sample_count", "high_outlier_ratio", etc.
    suggested_action: Optional[str] = None
    new_params: Dict[str, Any] = field(default_factory=dict)
    max_retries: int = 3
    current_retry: int = 0


@dataclass
class AgentState:
    """LangGraph state for the calibration workflow."""
    
    # Input
    task_request: Optional[TaskRequest] = None
    
    # Discovered data
    available_datasets: List[DatasetInfo] = field(default_factory=list)
    
    # Processing state
    current_branch: Optional[str] = None  # Which calibration path selected
    intermediate_results: Dict[str, CalibrationResult] = field(default_factory=dict)
    
    # Fallback state
    fallback_decision: Optional[FallbackDecision] = None
    
    # Final outputs
    final_results: List[CalibrationResult] = field(default_factory=list)
    
    # Execution metadata
    execution_log: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "pending"  # pending, running, success, failed
    errors: List[str] = field(default_factory=list)
    
    def add_log(self, event: str, details: Dict[str, Any]):
        """Add an execution log entry."""
        self.execution_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "event": event,
            "details": details
        })


class GPFConfigAdapter:
    """
    Adapter to convert TaskRequest to original GPF IPFConfig format.
    Respects the exact XML structure expected by GPF operators.
    """
    
    @staticmethod
    def to_xml_template(task: TaskRequest, output_dir: str) -> str:
        """
        Generate XML template compatible with GPF original main.py.
        Matches the structure expected by MyIPFConfig class.
        """
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<Processor_Config>
    <Processor_Name>{task.method}</Processor_Name>
    <Version>V01</Version>
    <Order_Id>{task.order_id or 0}</Order_Id>
    <Input>
        <File_Name>{task.aux_data_type}</File_Name>
    </Input>
    <Output>
        <File_Type>calibration_result</File_Type>
        <File_Name>{output_dir}</File_Name>
    </Output>
    <Processing_Parameters>
        <Processing_Parameter>
            <Name>Sat_ID</Name>
            <Value>{task.primary_sat}</Value>
        </Processing_Parameter>
        <Processing_Parameter>
            <Name>Data_version</Name>
            <Value>{task.data_version}</Value>
        </Processing_Parameter>
        <Processing_Parameter>
            <Name>Match_Data_Type</Name>
            <Value>{task.aux_data_type}</Value>
        </Processing_Parameter>
        <Processing_Parameter>
            <Name>Product_Type</Name>
            <Value>L2B_ICAL</Value>
        </Processing_Parameter>
        <Processing_Parameter>
            <Name>Start_date</Name>
            <Value>{task.start_date}</Value>
        </Processing_Parameter>
        <Processing_Parameter>
            <Name>End_date</Name>
            <Value>{task.end_date}</Value>
        </Processing_Parameter>
        <Processing_Parameter>
            <Name>match_time</Name>
            <Value>{task.match_time_hours or 2.0}</Value>
        </Processing_Parameter>
        {GPFConfigAdapter._format_optional_params(task)}
    </Processing_Parameters>
</Processor_Config>
'''
    
    @staticmethod
    def _format_optional_params(task: TaskRequest) -> str:
        """Format optional parameters for XML."""
        params = []
        
        if task.lat_range:
            params.append(f'''<Processing_Parameter>
            <Name>Select_Area</Name>
            <Value>[{task.lat_range[0]}, {task.lat_range[1]}, {task.lon_range[0] if task.lon_range else '-180'}, {task.lon_range[1] if task.lon_range else '180'}]</Value>
        </Processing_Parameter>''')
        
        if task.distance_to_coast_km:
            params.append(f'''<Processing_Parameter>
            <Name>distance_to_coast</Name>
            <Value>{task.distance_to_coast_km}</Value>
        </Processing_Parameter>''')
        
        if task.wind_speed_range:
            params.append(f'''<Processing_Parameter>
            <Name>wind_speed</Name>
            <Value>[{task.wind_speed_range[0]}, {task.wind_speed_range[1]}]</Value>
        </Processing_Parameter>''')
        
        if task.template_docx:
            params.append(f'''<Processing_Parameter>
            <Name>Template_docx</Name>
            <Value>{task.template_docx}</Value>
        </Processing_Parameter>''')
        
        return "\n        ".join(params)
