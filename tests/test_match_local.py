"""本地执行 01-MATCH 和 02-MATCH 的集成测试"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from operators.star_cross_match import StarCrossMatchOperator
from operators.self_cross_match import SelfCrossMatchOperator
from core.op_config import LocalConfig


def test_star_cross_match():
    """测试 01 星星交叉 MATCH"""
    print("=" * 72)
    print("测试 01-MATCH: 星星交叉匹配 (Star Cross Match)")
    print("=" * 72)
    
    cfg = LocalConfig(
        sat_id="S6A",
        aux_data_type="JA3",
        start_date="20230501",
        end_date="20230503",
        input_dir="./GPF_test_data/star_cross/input/NC",
        aux_input_dir="./GPF_test_data/self_cross/input/NC",  # 使用本地 NC 文件
        output_dir="./output_local_test/star_cross",
        data_version="V001",
        order_id=1001,
    )
    
    print(f"\n[配置]")
    print(f"  卫星：{cfg.sat_id} vs {cfg.aux_data_type}")
    print(f"  日期：{cfg.start_date} → {cfg.end_date}")
    print(f"  输入 (主): {cfg.input_dir}")
    print(f"  输入 (辅): {cfg.aux_input_dir}")
    print(f"  输出：{cfg.output_dir}")
    
    # 检查文件
    nc_files_s = list(Path(cfg.input_dir).glob("*.nc"))
    nc_files_a = list(Path(cfg.aux_input_dir).glob("*.nc"))
    print(f"\n[数据检查]")
    print(f"  S6A NC 文件：{len(nc_files_s)} 个")
    print(f"  JA3 NC 文件：{len(nc_files_a)} 个")
    
    if not nc_files_s or not nc_files_a:
        print("  ⚠ 缺少 NC 文件，跳过测试")
        return False
    
    # 执行 MATCH
    print(f"\n[执行] StarCrossMatchOperator.run_local()")
    op = StarCrossMatchOperator(cfg)
    result = op.run_local(cfg.input_dir)
    
    print(f"\n[结果]")
    print(f"  Status: {result.get('status')}")
    if result.get('status') == 'success':
        print(f"  Function: {result.get('function')}")
        print(f"  Time: {result.get('execution_time', 0):.2f}s")
        print(f"  Output Dir: {result.get('output_dir')}")
        
        # 检查输出文件
        out_path = Path(result.get('output_dir', ''))
        if out_path.exists():
            npz_files = list(out_path.glob("**/*.npz"))
            xml_files = list(out_path.glob("**/*.xml"))
            print(f"\n  生成文件:")
            print(f"    NPZ: {len(npz_files)} 个")
            for f in npz_files[:3]:
                print(f"      - {f.relative_to(out_path)} ({f.stat().st_size / 1024:.1f} KB)")
            print(f"    XML: {len(xml_files)} 个")
            return True
    else:
        print(f"  Error: {result.get('error')}")
        if result.get('traceback'):
            print(f"  Traceback:\n{result['traceback'][:500]}...")
    
    return False


def test_self_cross_match():
    """测试 02 星星自交叉 MATCH"""
    print("\n" + "=" * 72)
    print("测试 02-MATCH: 星星自交叉匹配 (Self Cross Match)")
    print("=" * 72)
    
    cfg = LocalConfig(
        sat_id="JA3",
        aux_data_type="S6A",  # 自交叉也需要辅助数据用于对比
        start_date="20230501",
        end_date="20230503",
        input_dir="./GPF_test_data/self_cross/input/NC",
        output_dir="./output_local_test/self_cross",
        data_version="V001",
        order_id=1002,
    )
    
    print(f"\n[配置]")
    print(f"  卫星：{cfg.sat_id} (自交叉)")
    print(f"  日期：{cfg.start_date} → {cfg.end_date}")
    
    # 执行 MATCH
    print(f"\n[执行] SelfCrossMatchOperator.run_local()")
    op = SelfCrossMatchOperator(cfg)
    result = op.run_local(cfg.input_dir)
    
    print(f"\n[结果]")
    print(f"  Status: {result.get('status')}")
    if result.get('status') == 'success':
        print(f"  Output Dir: {result.get('output_dir')}")
        return True
    else:
        print(f"  Error: {result.get('error')}")
        return False


def main():
    print("=" * 72)
    print("本地 MATCH 算子测试")
    print("=" * 72)
    
    results = {}
    
    # 测试 01
    results['01-MATCH'] = test_star_cross_match()
    
    # 测试 02
    results['02-MATCH'] = test_self_cross_match()
    
    # 汇总
    print("\n" + "=" * 72)
    print("测试汇总")
    print("=" * 72)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n通过：{passed}/{total}")
    for name, ok in results.items():
        status = "✓" if ok else "✗"
        print(f"  {status} {name}")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
