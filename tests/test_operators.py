"""
算子冒烟测试 - 用远程拷回的真实 NPZ 数据验证三个算子。
运行: python tests/test_operators.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.op_config import LocalConfig
from operators import OperatorRegistry

DATA = Path(__file__).resolve().parent.parent / "GPF_test_data"


def run_case(name, cfg, expect_keys):
    print("=" * 72)
    print(f"[{name}]  input_dir = {cfg.input_dir}")
    res = OperatorRegistry.run(name, cfg)
    print(f"  status          : {res.get('status')}")
    print(f"  error           : {res.get('error')}")
    print(f"  n_samples_init  : {res.get('n_samples_initial')}")
    print(f"  n_samples_final : {res.get('n_samples_final')}")
    print(f"  n_outliers      : {res.get('n_outliers')}")
    for k in ("bias_mean", "bias_std", "rmse", "bias_median"):
        v = res.get(k)
        print(f"  {k:15s} : {v if v is None else round(v, 6)}")
    for k in ("slope", "intercept", "r_squared"):
        v = res.get(k)
        if v is not None:
            print(f"  {k:15s} : {round(v, 6)}")
    missing = [k for k in expect_keys if res.get(k) is None]
    ok = res.get("status") == "success" and not missing
    print(f"  --> {'PASS' if ok else 'FAIL'}  (missing={missing})")
    return ok, res


def main():
    results = {}

    # 1) 星星交叉: S6A vs JA3, 20230501-20230504
    ok1, r1 = run_case(
        "star_cross",
        LocalConfig(
            sat_id="S6A", aux_data_type="JA3",
            start_date="20230501", end_date="20230504",
            input_dir=str(DATA / "star_cross"),
        ),
        ["bias_mean", "bias_std", "rmse", "slope", "r_squared"],
    )
    results["star_cross"] = ok1

    # 2) 星自交叉: JA3 自交叉
    ok2, r2 = run_case(
        "self_cross",
        LocalConfig(
            sat_id="JA3", aux_data_type="SELF",
            start_date="20230401", end_date="20230411",
            input_dir=str(DATA / "self_cross"),
        ),
        ["bias_mean", "bias_std", "rmse", "slope"],
    )
    results["self_cross"] = ok2

    # 3) 验潮站外推: JA3 vs YCZ
    ok3, r3 = run_case(
        "tide_ext",
        LocalConfig(
            sat_id="JA3", aux_data_type="YCZ",
            start_date="20190610", end_date="20241017",
            input_dir=str(DATA / "tide_ext"),
        ),
        ["bias_mean", "rmse"],
    )
    results["tide_ext"] = ok3

    print("=" * 72)
    print("汇总:", json.dumps(results, ensure_ascii=False))
    print("全部通过" if all(results.values()) else "存在失败项")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
