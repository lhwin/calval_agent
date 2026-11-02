"""本地包装器执行测试 - 01 MATCH (不依赖 SSH)"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from operators.star_cross_match import StarCrossMatchOperator
from core.op_config import LocalConfig


def main():
    print("=" * 72)
    print("本地执行测试：01-MATCH (Star Cross Match)")
    print("=" * 72)
    
    # 准备配置
    cfg = LocalConfig(
        sat_id="S6A",
        aux_data_type="JA3",
        start_date="20230501",
        end_date="20230503",
        input_dir="./GPF_test_data/star_cross/input",
        output_dir="./output_local_test",
        data_version="V001",
        order_id=999,
    )
    
    print(f"\n[配置]")
    print(f"  卫星：{cfg.sat_id} vs {cfg.aux_data_type}")
    print(f"  日期：{cfg.start_date} → {cfg.end_date}")
    print(f"  输入：{cfg.input_dir}")
    print(f"  输出：{cfg.output_dir}")
    
    # 检查输入目录
    input_path = Path(cfg.input_dir)
    if not input_path.exists():
        print(f"  ⚠ 输入目录不存在，跳过执行")
        print(f"\n  说明：本地执行需要有 NC 文件作为输入")
        print(f"  解决方案:")
        print(f"    1. 从服务器拷回 NC 数据到 {input_path}")
        print(f"    2. 或使用已生成的 NPZ 直接测试 01-CAL")
        return 0
    
    npz_files = list(input_path.glob("*.npz"))
    nc_files = list(input_path.glob("*.nc"))
    print(f"  NPZ 文件：{len(npz_files)}")
    print(f"  NC 文件：{len(nc_files)}")
    
    # 尝试本地执行
    print(f"\n[执行] 调用 func_cross_matching_pro()")
    
    op = StarCrossMatchOperator(cfg)
    result = op.run_local(cfg.input_dir)
    
    print(f"\n[结果]")
    print(f"  Status: {result.get('status')}")
    
    if result.get("status") == "success":
        print(f"  Function: {result.get('function')}")
        print(f"  Execution Time: {result.get('execution_time', 0):.2f}s")
        print(f"  Job XML: {result.get('job_xml')}")
        print(f"  Output Dir: {result.get('output_dir')}")
        
        # 检查输出
        out_dir = Path(result.get("output_dir", ""))
        if out_dir.exists():
            output_files = list(out_dir.glob("*.npz")) + list(out_dir.glob("*.xml"))
            print(f"  Generated Files: {len(output_files)}")
            for f in output_files[:3]:
                print(f"    - {f.name}")
    else:
        print(f"  Error: {result.get('error')}")
        if result.get("traceback"):
            print(f"  Traceback:\n{result['traceback'][:500]}...")
    
    print("\n" + "=" * 72)
    print("测试完成")
    print("=" * 72)
    
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
