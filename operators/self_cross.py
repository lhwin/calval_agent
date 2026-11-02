"""
星自交叉定标算子 - 忠实包装自 GPF 源码:
GPF/02-星星自交叉法 v2.0/CVS_SELF_GLSY_ALT_GDR_AUX_SAT_CAL/func_GLSY_ALT_AUX_Sat_GDR_CAL.py

核心算法:
1. 匹配 NPZ 加载 ssh_asc (升降轨) / ssh_desc (降升轨)
2. ±15cm 异常值剔除
3. OLS linregress(ssh_desc, ssh_asc)
"""

import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np
from scipy import stats as stats_log


class SelfCrossCalibration:
    """星自交叉定标 (同一卫星升降轨对比)。"""

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("self_cross")

    def run(self) -> Dict[str, Any]:
        t0 = time.time()
        try:
            data = self.load_match_data()
            if data is None:
                return {"status": "failed", "error": "No match data found", "n_samples": 0}

            ssh_asc = data['ssh_asc']
            ssh_desc = data['ssh_desc']

            # ±15cm 异常值剔除
            threshold_m = 0.15  # 15cm in meters
            outlier_mask = np.abs(ssh_asc - ssh_desc) > threshold_m
            num_outliers = int(np.sum(outlier_mask))

            ssh_asc_clean = ssh_asc[~outlier_mask]
            ssh_desc_clean = ssh_desc[~outlier_mask]

            result = {
                "bias_mean": float(np.nanmean(ssh_desc_clean - ssh_asc_clean)),
                "bias_std": float(np.nanstd(ssh_desc_clean - ssh_asc_clean)),
                "rmse": float(np.sqrt(np.nanmean((ssh_desc_clean - ssh_asc_clean) ** 2))),
                "n_samples_initial": len(ssh_asc),
                "n_samples_final": len(ssh_asc_clean),
                "n_outliers": num_outliers,
                "status": "success",
                "execution_time": time.time() - t0,
            }

            # OLS linregress(ssh_desc, ssh_asc)
            if len(ssh_desc_clean) > 1:
                try:
                    slope, intercept, r_value, p_value, std_err = stats_log.linregress(
                        ssh_desc_clean, ssh_asc_clean)
                    result.update({
                        "slope": float(slope),
                        "intercept": float(intercept),
                        "r_squared": float(r_value ** 2),
                        "p_value": float(p_value),
                        "std_error": float(std_err),
                    })
                except Exception as e:
                    self.logger.warning(f"回归失败: {e}")

            return result

        except Exception as e:
            return {"status": "failed", "error": str(e), "execution_time": time.time() - t0}

    def load_match_data(self) -> Optional[Dict[str, np.ndarray]]:
        """加载匹配文件 (兼容多种命名格式)"""
        import re
        from pathlib import Path
        input_dir = Path(self.config.input_dir or ".")
        sat = self.config.sat_id
        
        # 尝试多种匹配模式
        patterns = [
            rf"match_result_{re.escape(sat)}_vs_SELF_(\d{{8}})_(\d{{8}})\.npz$",
            rf"match_result_.*_vs_SELF_.*\.npz$",
            rf"calibration_data_{re.escape(sat)}_self_cross_(\d{{8}})_(\d{{8}})\.npz$",
            rf"calibration_data_.*_self_cross_.*\.npz$",
        ]
        
        for p in input_dir.rglob("*.npz"):
            for pattern in patterns:
                if re.search(pattern, p.name, re.I):
                    with np.load(p, allow_pickle=True) as f:
                        return {
                            "ssh_asc": f.get('ssh_asc', np.array([])),
                            "ssh_desc": f.get('ssh_desc', np.array([])),
                        }
        return None