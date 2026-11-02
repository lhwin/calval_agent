"""调试 tide_ext_full 的记录解析循环。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from operators.tide_ext_full import TideStationExtensionFull
from core.op_config import LocalConfig

cfg = LocalConfig(sat_id="H2B", aux_data_type="YCZ",
                  start_date="20190610", end_date="20241017",
                  input_dir="GPF_test_data/tide_ext")

op = TideStationExtensionFull(cfg)
data = op.load_tide_match_data()
print("records:", len(data))

site_counts = {}
errors = {}
ok = 0

for i, record in enumerate(data):
    try:
        site_name = str(record.get("site_name", "")).lower()
        cycle = record.get("cycle", 0)
        pass_time_str = record.get("pass_time_str", "")
        sshalt = record.get("sshalt", np.array([]))
        tide001 = float(record.get("tide001", 0))
        lat_p = record.get("lat_p", None)

        if not isinstance(sshalt, np.ndarray) or len(sshalt) == 0:
            errors.setdefault("empty_sshalt", 0)
            errors["empty_sshalt"] += 1
            continue

        jd = op._jd_from_datetime(pass_time_str) if pass_time_str else 0
        lat_p_arr = float(lat_p[0]) if isinstance(lat_p, np.ndarray) and len(lat_p) > 0 else lat_p

        tidecons_tg = record.get("tidecons_tg", {})
        tidecons_alt = record.get("tidecons_alt", {})

        tidetg = op._compute_tide_one(tidecons_tg, jd, lat_p_arr) * 0.01
        tidealt = op._compute_tide_one(tidecons_alt, jd, lat_p_arr) * 0.01
        dtide = tidealt - tidetg

        mss_raw_tg = record.get("mss_raw_tg", 0)
        mss_raw_alt = record.get("mss_raw_alt", np.array([0]))
        if isinstance(mss_raw_alt, np.ndarray) and len(mss_raw_alt) > 0:
            mss_raw_alt = mss_raw_alt[0]

        geoidtg = op._apply_ellipsoid(mss_raw_tg, lat_p_arr)
        geoid01 = op._apply_ellipsoid(mss_raw_alt, lat_p_arr)
        dgeoid1 = geoid01 - geoidtg

        bias01 = np.asarray(sshalt, dtype=float) - (tide001 + dgeoid1 + dtide)
        outlier_mask = np.abs(bias01) > 0.15
        bias01_clean = bias01[~outlier_mask]

        if i < 3:
            print(f"  rec{i}: site={site_name} cyc={cycle} sshalt={sshalt} tide001={tide001:.3f} "
                  f"dtide={dtide:.4f} dgeoid={dgeoid1:.4f} bias={bias01} clean_n={len(bias01_clean)}")

        if len(bias01_clean) > 0:
            ok += 1
            site_counts[site_name] = site_counts.get(site_name, 0) + 1
        else:
            errors["all_outlier"] = errors.get("all_outlier", 0) + 1
    except Exception as e:
        key = type(e).__name__ + ": " + str(e)[:60]
        errors[key] = errors.get(key, 0) + 1

print("\nOK records:", ok)
print("site_counts:", site_counts)
print("errors:")
for k, v in sorted(errors.items(), key=lambda x: -x[1]):
    print(f"   {v:5d}  {k}")
