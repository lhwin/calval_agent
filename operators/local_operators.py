"""
Local GPF Operators - Wrapped from original source code.
Located in C:/GPF/*.py files.
"""

import os
import sys
import json
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

import numpy as np
from scipy import stats as stats_lib

# Add GPF operator paths to sys.path
GPF_BASE = Path("C:/GPF")
OPERATOR_PATHS = {
    "star_cross": GPF_BASE / "01-星星交叉法 v2.0" / "csv_glsy_alt_gdr_aux_sat_cal",
    "self_cross": GPF_BASE / "02-星星自交叉法 v2.0" / "CVS_SELF_GLSY_ALT_GDR_AUX_SAT_CAL",
    "tide_ext": GPF_BASE / "04-验潮站外推 v1.0" / "CVS_GLSY_ALT_GDR_AUX_YCZ_CAL"
}


@dataclass
class LocalConfig:
    """Local configuration for operator execution."""
    sat_id: str
    aux_data_type: str
    start_date: str  # YYYYMMDD
    end_date: str  # YYYYMMDD
    data_version: str = "V001"
    match_time: float = 2.0
    output_dir: str = ""
    input_dir: str = ""
    
    # Optional QC parameters
    select_area: Optional[List[float]] = None  # [min_lat, max_lat, min_lon, max_lon]
    distance_to_coast: Optional[float] = None
    ocean_depth: Optional[float] = None
    wind_speed: Optional[List[float]] = None
    
    order_id: int = 0
    proc_name: str = "calibration"
    version: str = "V01"


class StarCrossCalibration:
    """
    Star-cross calibration operator.
    Adapted from original: 01-星星交叉法 v2.0/csv_glsy_alt_gdr_aux_sat_cal/func_GLSY_ALT_AUX_Sat_GDR_CAL.py
    
    Key functions:
    - func_cross_cal_pro: Main calibration routine
    - Reads match_result_*.npz files
    - Outputs: JSON, TXT, PNG plots, NPZ data, DOCX report
    """
    
    def __init__(self, config: LocalConfig):
        self.config = config
        self.logger = self._setup_logger()
        
    def _setup_logger(self):
        logger = logging.getLogger(f"star_cross_{self.config.order_id}")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    def run(self) -> Dict[str, Any]:
        """
        Run star-cross calibration.
        Returns standardized result dict.
        """
        self.logger.info("Starting star-cross calibration")
        start_time = time.time()
        
        try:
            # Step 1: Find and load match data
            data = self._load_match_data()
            
            if data is None or len(data['ssh_diff']) == 0:
                return {
                    "status": "failed",
                    "error": "No match data found",
                    "n_samples": 0
                }
            
            self.logger.info(f"Loaded {len(data['ssh_diff'])} match points")
            
            # Step 2: Apply time filter
            mask = np.abs(data['time_primary'] - data['time_aux']) < self.config.match_time * 3600
            
            # Step 3: Remove outliers (±15cm threshold from original code)
            outlier_mask = np.abs(data['ssh_diff']) > 0.15  # 15cm in meters
            n_outliers = np.sum(outlier_mask)
            clean_mask = ~outlier_mask
            
            # Step 4: Calculate statistics
            ssh_diff_clean = data['ssh_diff'][clean_mask]
            ssh_primary_clean = data['ssh_primary'][clean_mask]
            ssh_aux_clean = data['ssh_aux'][clean_mask]
            
            result = self._calculate_statistics(
                ssh_diff_clean, ssh_primary_clean, ssh_aux_clean,
                data.get('lon', np.array([])),
                data.get('lat', np.array([]))
            )
            
            result["n_outliers"] = int(n_outliers)
            result["status"] = "success"
            
            duration = time.time() - start_time
            result["execution_time"] = duration
            
            self.logger.info(f"Calibration completed in {duration:.2f}s")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Calibration failed: {str(e)}")
            import traceback
            return {
                "status": "failed",
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    def _load_match_data(self) -> Optional[Dict[str, np.ndarray]]:
        """
        Load match_result_*.npz files from input directory.
        Based on original code pattern in func_GLSY_ALT_AUX_Sat_GDR_CAL.py
        """
        input_dir = Path(self.config.input_dir) if self.config.input_dir else GPF_BASE / "target"
        
        # Pattern: match_result_{sat}_vs_{aux}_{start}_{end}.npz
        prefix = f"match_result_{self.config.sat_id}_vs_{self.config.aux_data_type}_"
        pattern = f"{prefix}*.npz"
        
        match_files = list(input_dir.glob(pattern))
        
        if not match_files:
            self.logger.warning(f"No match files found for {prefix}*")
            return None
        
        # Load first matching file (can be extended to merge multiple)
        data_file = match_files[0]
        self.logger.info(f"Loading match data from {data_file.name}")
        
        with np.load(data_file, allow_pickle=True) as f:
            data = {
                'ssh_diff': f.get('ssh_diff', np.array([])),
                'ssh_primary': f.get('ssh_primary', np.array([])),
                'ssh_aux': f.get('ssh_aux', np.array([])),
                'lon': f.get('lon', np.array([])),
                'lat': f.get('lat', np.array([])),
                'time_primary': f.get('time_primary', np.array([])),
                'time_aux': f.get('time_aux', np.array([])),
            }
        
        return data
    
    def _calculate_statistics(
        self,
        ssh_diff: np.ndarray,
        ssh_primary: np.ndarray,
        ssh_aux: np.ndarray,
        lon: np.ndarray,
        lat: np.ndarray
    ) -> Dict[str, Any]:
        """Calculate calibration statistics (same as original code)."""
        result = {}
        
        # Basic statistics (in meters, as in original code)
        result['bias_mean'] = float(np.nanmean(ssh_diff))
        result['bias_std'] = float(np.nanstd(ssh_diff))
        result['rmse'] = float(np.sqrt(np.nanmean(ssh_diff ** 2)))
        result['bias_median'] = float(np.nanmedian(ssh_diff))
        
        result['n_samples'] = len(ssh_diff)
        
        # Linear regression (OLS, same as original - NOT ODR)
        if len(ssh_aux) > 1 and np.all(np.isfinite(ssh_aux)) and np.all(np.isfinite(ssh_primary)):
            try:
                slope, intercept, r_value, p_value, std_err = stats_lib.linregress(ssh_aux, ssh_primary)
                result['slope'] = float(slope)
                result['intercept'] = float(intercept)  # in meters
                result['r_squared'] = float(r_value ** 2)
                result['p_value'] = float(p_value)
                result['std_error'] = float(std_err)
            except Exception as e:
                self.logger.warning(f"Regression failed: {e}")
                result['slope'] = None
                result['intercept'] = None
                result['r_squared'] = None
        
        return result


class SelfCrossCalibration:
    """
    Self-cross calibration operator (ascending vs descending tracks).
    Adapted from original: 02-星星自交叉法 v2.0/CVS_SELF_GLSY_ALT_GDR_AUX_SAT_CAL/func_GLSY_ALT_AUX_Sat_GDR_CAL.py
    """
    
    def __init__(self, config: LocalConfig):
        self.config = config
        self.logger = self._setup_logger()
        
    def _setup_logger(self):
        logger = logging.getLogger(f"self_cross_{self.config.order_id}")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    def run(self) -> Dict[str, Any]:
        """Run self-cross calibration."""
        start_time = time.time()
        
        try:
            # Same loading logic as star-cross
            data = self._load_match_data()
            
            if data is None:
                return {"status": "failed", "error": "No match data found", "n_samples": 0}
            
            # This is a simplified wrapper - original code has more complex track identification
            ssh_diff = data['ssh_diff']
            
            # Filter outliers
            clean_mask = np.abs(ssh_diff) <= 0.15
            ssh_diff_clean = ssh_diff[clean_mask]
            
            # Statistics
            result = {
                'bias_mean': float(np.nanmean(ssh_diff_clean)),
                'bias_std': float(np.nanstd(ssh_diff_clean)),
                'rmse': float(np.sqrt(np.nanmean(ssh_diff_clean ** 2))),
                'n_samples': len(ssh_diff_clean),
                'n_outliers': int(np.sum(~clean_mask)),
                'status': 'success'
            }
            
            result['execution_time'] = time.time() - start_time
            return result
            
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def _load_match_data(self) -> Optional[Dict[str, np.ndarray]]:
        input_dir = Path(self.config.input_dir) if self.config.input_dir else GPF_BASE / "target"
        prefix = f"match_result_{self.config.sat_id}_vs_SELF_"
        pattern = f"{prefix}*.npz"
        
        match_files = list(input_dir.glob(pattern))
        
        if not match_files:
            return None
        
        with np.load(match_files[0], allow_pickle=True) as f:
            return {
                'ssh_diff': f.get('ssh_diff', np.array([])),
                'ssh_primary': f.get('ssh_desc', np.array([])),  # Descending
                'ssh_aux': f.get('ssh_aux', np.array([])),  # Ascending
            }


class TideStationExtension:
    """
    Tide station extension operator.
    Adapted from original: 04-验潮站外推 v1.0/CVS_GLSY_ALT_GDR_AUX_YCZ_CAL/func_GLSY_ALT_AUX_YCZ_GDR_CAL.py
    
    Note: Original code uses custom harmonic tide prediction, NOT T-TIDE or TPXO.
    """
    
    def __init__(self, config: LocalConfig):
        self.config = config
        self.logger = self._setup_logger()
        
    def _setup_logger(self):
        logger = logging.getLogger(f"tide_ext_{self.config.order_id}")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    def run(self) -> Dict[str, Any]:
        """Run tide station extension."""
        start_time = time.time()
        
        try:
            # Load tide station data
            data = self._load_tide_data()
            
            if data is None:
                return {"status": "failed", "error": "No tide station data found"}
            
            # Simplified calculation - original has more complex tidal modeling
            ssh_sat = data.get('ssh_satellite', np.array([]))
            ssh_tide = data.get('ssh_tide_station', np.array([]))
            
            if len(ssh_sat) == 0 or len(ssh_tide) == 0:
                return {"status": "failed", "error": "Empty data arrays"}
            
            # Calculate bias
            diff = ssh_sat - ssh_tide
            result = {
                'bias_mean': float(np.nanmean(diff)),
                'bias_std': float(np.nanstd(diff)),
                'rmse': float(np.sqrt(np.nanmean(diff ** 2))),
                'n_samples': len(diff),
                'status': 'success'
            }
            
            result['execution_time'] = time.time() - start_time
            return result
            
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def _load_tide_data(self) -> Optional[Dict[str, np.ndarray]]:
        """Load tide station data from expected location."""
        # Check for YCZ (验潮站) match files
        input_dir = Path(self.config.input_dir) if self.config.input_dir else GPF_BASE / "target"
        prefix = f"match_result_{self.config.sat_id}_vs_YCZ_"
        pattern = f"{prefix}*.npz"
        
        match_files = list(input_dir.glob(pattern))
        
        if not match_files:
            return None
        
        with np.load(match_files[0], allow_pickle=True) as f:
            return {
                'ssh_satellite': f.get('ssh_diff', np.array([])),
                'ssh_tide_station': f.get('ssh_aux', np.array([])),
            }


def run_calibration(operator_type: str, config: LocalConfig) -> Dict[str, Any]:
    """Factory function to run the appropriate calibration operator."""
    
    if operator_type == "star_cross":
        return StarCrossCalibration(config).run()
    elif operator_type == "self_cross":
        return SelfCrossCalibration(config).run()
    elif operator_type == "tide_ext":
        return TideStationExtension(config).run()
    else:
        return {"status": "failed", "error": f"Unknown operator type: {operator_type}"}
