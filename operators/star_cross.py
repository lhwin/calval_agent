"""
星星交叉定标算子 - 忠实包装自 GPF 源码:
GPF/csv_glsy_alt_gdr_aux_sat_cal/func_GLSY_ALT_AUX_Sat_GDR_CAL.py

核心算法 (保持原实现):
1. 多日期 NPZ 文件读取、合并、去重 (lexsort 按空间距离/时间差优先)
2. match_time 时间窗口筛选
3. ±15cm 异常值剔除
4. 统计量: mean/std/rmse/median (nan-aware)
5. OLS 线性回归: linregress(ssh_aux, ssh_primary)  [原码用 OLS, 非 ODR]
"""

import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import numpy as np
from scipy import stats as stats_lib


class StarCrossCalibration:
    """星星交叉定标 (GL-SY vs 参考卫星)。"""

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("star_cross")

    def run(self) -> Dict[str, Any]:
        t0 = time.time()
        try:
            data = self.load_and_merge_match_data()
            if data is None:
                return {"status": "failed", "error": "No match data found", "n_samples": 0}

            # ---- 原码: match_time 时间窗筛选 ----
            match_time = float(self.config.match_time)
            mask = np.abs(data['time_primary'] - data['time_aux']) < match_time * 3600

            ssh_diff = data['ssh_diff'][mask]
            ssh_primary = data['ssh_primary'][mask]
            ssh_aux = data['ssh_aux'][mask]

            total_match_points = len(data['ssh_diff'])

            # ---- 原码: ±15cm 异常值剔除 ----
            threshold_cm = 15
            threshold_m = threshold_cm / 100
            outlier_mask = np.abs(ssh_diff) > threshold_m
            num_outliers = int(np.sum(outlier_mask))

            ssh_diff_clean = ssh_diff[~outlier_mask]
            ssh_primary_clean = ssh_primary[~outlier_mask]
            ssh_aux_clean = ssh_aux[~outlier_mask]

            # ---- 原码: 统计量 (nan-mean/std/rmse/median) ----
            result = {
                "bias_mean": float(np.nanmean(ssh_diff_clean)),
                "bias_std": float(np.nanstd(ssh_diff_clean)),
                "rmse": float(np.sqrt(np.nanmean(ssh_diff_clean ** 2))),
                "bias_median": float(np.nanmedian(ssh_diff_clean)),
                "n_samples_initial": total_match_points,
                "n_samples_final": len(ssh_diff_clean),
                "n_outliers": num_outliers,
                "outlier_threshold_cm": threshold_cm,
                "match_time_hours": match_time,
                "status": "success",
                "execution_time": time.time() - t0,
            }

            # ---- 原码: OLS 回归 linregress(ssh_aux, ssh_primary) ----
            if len(ssh_aux_clean) > 1:
                try:
                    slope, intercept, r_value, p_value, std_err = stats_lib.linregress(
                        ssh_aux_clean, ssh_primary_clean
                    )
                    result.update({
                        "slope": float(slope),
                        "intercept": float(intercept),
                        "r_squared": float(r_value ** 2),
                        "p_value": float(p_value),
                        "std_error": float(std_err),
                    })
                except Exception as e:
                    self.logger.warning(f"线性回归失败: {e}")

            return result

        except Exception as e:
            return {"status": "failed", "error": str(e), "execution_time": time.time() - t0}

    def load_and_merge_match_data(self) -> Optional[Dict[str, np.ndarray]]:
        """
        原码逻辑: 找到日期范围有交集的
        match_result_{Sat_ID}_vs_{Match_Data_Type}_{start}_{end}.npz
        合并后按 (time_primary, lon, lat) 去重, 空间距离小者优先。
        """
        fields = ('ssh_diff', 'ssh_primary', 'ssh_aux', 'lon', 'lat',
                  'time_primary', 'time_aux', 'distance')

        # 搜索匹配文件 (原码用正则 fullmatch)
        import re
        input_dir = Path(self.config.input_dir or ".")
        prefix = f"match_result_{self.config.sat_id}_vs_{self.config.aux_data_type}_"
        name_re = re.compile(
            rf"^{re.escape(prefix)}(\d{{8}})_(\d{{8}})\.npz$", re.IGNORECASE
        )

        files = []
        for p in input_dir.rglob("*.npz"):
            m = name_re.fullmatch(p.name)
            if m and self._date_overlap(m.group(1), m.group(2)):
                files.append(p)
        files.sort()

        if not files:
            self.logger.warning(f"未找到匹配 NPZ: {input_dir}/{prefix}*")
            return None

        collected = {k: [] for k in fields}
        for fp in files:
            with np.load(fp, allow_pickle=True) as f:
                n = len(f['ssh_diff'])
                for key in fields:
                    arr = np.asarray(f[key], dtype=float) if key in f.files \
                        else np.full(n, np.nan)
                    collected[key].append(arr)

        data = {k: np.concatenate(v) for k, v in collected.items()}

        # ---- 原码去重: 按 (time, lon, lat) 分组, distance 小者优先 ----
        tk = np.round(data['time_primary'], 3)
        xk = np.round(data['lon'], 7)
        yk = np.round(data['lat'], 7)
        distances = np.nan_to_num(data['distance'], nan=np.inf,
                                 posinf=np.inf, neginf=np.inf)
        time_gaps = np.nan_to_num(np.abs(data['time_primary'] - data['time_aux']),
                                  nan=np.inf)
        order = np.lexsort((time_gaps, distances, yk, xk, tk))
        first = np.r_[True,
                      (tk[order][1:] != tk[order][:-1])
                      | (xk[order][1:] != xk[order][:-1])
                      | (yk[order][1:] != yk[order][:-1])]
        keep = np.sort(order[first])

        self.logger.info(
            f"合并 {len(files)} 文件, 去重 {len(tk) - len(keep)}, 保留 {len(keep)} 点")
        return {k: v[keep] for k, v in data.items()}

    def _date_overlap(self, file_start: str, file_end: str) -> bool:
        """原码: 文件日期范围与 CAL 日期范围存在交集。"""
        return file_start <= self.config.end_date and file_end >= self.config.start_date
