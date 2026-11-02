"""8 个 GPF 包装器 + 4 个本地算子的导入与实例化测试。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from operators import OperatorRegistry, GPF_OPERATORS, LOCAL_OPERATORS
from core.op_config import LocalConfig


def main():
    print("=" * 72)
    print("GPF 算子包装器清单")
    print("=" * 72)

    groups = {
        "01 星星交叉": ["star_cross_match", "star_cross_cal"],
        "02 星星自交叉": ["self_cross_match", "self_cross_cal"],
        "03 SIG0 交叉": ["sig0_cross_match", "sig0_cross_cal"],
        "04 验潮站": ["ycz_match", "ycz_cal"],
    }

    for group, names in groups.items():
        print(f"\n[{group}]")
        for n in names:
            cls = GPF_OPERATORS.get(n)
            print(f"  {n:22s} -> {cls.__name__ if cls else '缺失'}")

    print("\n[本地算子 (向后兼容)]")
    for n, cls in LOCAL_OPERATORS.items():
        print(f"  {n:22s} -> {cls.__name__}")

    total = len(GPF_OPERATORS) + len(LOCAL_OPERATORS)
    print(f"\n合计: {len(GPF_OPERATORS)} GPF 包装器 + {len(LOCAL_OPERATORS)} 本地算子 = {total}")

    # ---- 实例化测试 ----
    print("\n" + "=" * 72)
    print("实例化测试")
    print("=" * 72)

    # 通用测试配置 (星间交叉)
    cfg_cross = LocalConfig(
        sat_id="S6A",
        aux_data_type="JA3",
        start_date="20230501",
        end_date="20230503",
        input_dir="GPF_test_data/star_cross/input",
    )

    # 验潮站专用配置
    cfg_ycz = LocalConfig(
        sat_id="S6A",
        aux_data_type="YCZ",
        start_date="20230501",
        end_date="20230503",
        input_dir="GPF_test_data/ycz/input",
    )

    ok, fail = 0, []
    for name, cls in GPF_OPERATORS.items():
        try:
            # 根据算子类型选择配置
            config = cfg_ycz if "ycz" in name else cfg_cross
            cls(config)
            ok += 1
            print(f"  ✓ {name:22s} OK")
        except Exception as e:
            fail.append((name, f"{type(e).__name__}: {e}"))
            print(f"  ✗ {name:22s} {e}")

    print(f"\nGPF 包装器实例化: {ok}/{len(GPF_OPERATORS)} 成功")
    for name, err in fail:
        print(f"  ✗ {name}: {err}")

    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())
