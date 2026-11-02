"""
03/04 MATCH 算子测试脚本
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.op_config import LocalConfig

ROOT = Path(__file__).parent.parent


def test_03_match():
    """03-MATCH: SIG0 交叉匹配 - SKIP (需要分离的卫星目录)"""
    print("=" * 72)
    print("03-MATCH: SIG0 交叉匹配 (JA3 vs S6A)")
    print("=" * 72)
    
    print("\n[SKIP] 需要两颗卫星的独立 H5/NC 目录结构")
    print("  当前测试数据只有混合后的 3 个 H5 文件，不符合 03-MATCH 要求")
    return {"name": "03-MATCH", "status": "skipped", "reason": "需要独立的卫星目录"}


def test_04_match():
    """04-MATCH: 验潮站匹配"""
    print("\n" + "=" * 72)
    print("04-MATCH: 验潮站匹配 (H2B vs YCZ)")
    print("=" * 72)

    from operators.ycz_match import YczMatchOperator

    base = ROOT / "GPF_test_data" / "tide_ext" / "input"
    nc_dir = base / "HY-2BGDR"
    wstg_dir = base / "WSTG"
    mss_file = base / "DTU18MSS_1min.nc"

    nc_files = sorted(nc_dir.glob("*.nc"))
    txt_files = list(wstg_dir.rglob("*.txt"))

    print(f"\n[数据]")
    print(f"  主数据 (HY-2BGDR): {len(nc_files)} NC 文件")
    print(f"  辅数据 (WSTG):     {len(txt_files)} TXT 文件")
    print(f"  MSS 模型:          {'✓' if mss_file.exists() else '✗'} {mss_file.name}")

    if not nc_files or not txt_files:
        print("  ✗ 数据不全，跳过")
        return {"name": "04-MATCH", "status": "skipped", "reason": "数据不全"}

    cfg = LocalConfig(
        sat_id="H2B", aux_data_type="YCZ",
        start_date="20190610", end_date="20241017",
        input_dir=str(nc_dir),
        output_dir=str(ROOT / "output_local_test" / "ycz_match"),
    )
    cfg.ycz_data_dir = str(wstg_dir)
    cfg.mss_path = str(mss_file)
    cfg.fes2014_path = str(ROOT / "operators" / "gpf_src" / "04_ycz" / "match" / "data" / "input" / "FES2014" / "ocean_tide")

    try:
        op = YczMatchOperator(cfg)
        res = op.run_local(str(base))
        status = res.get("status")
        print(f"\n[结果] Status: {status}")
        if status == "success":
            print(f"  Output: {res.get('output_dir')}")
            npz = res.get("npz_files", []) or []
            print(f"  NPZ 文件: {len(npz)}")
            for f in npz[:3]:
                print(f"    - {Path(f).name}")
        else:
            print(f"  Error: {str(res.get('error'))[:300]}")
        return {"name": "04-MATCH", "status": status, "result": res}
    except Exception as e:
        print(f"\n[异常] {e}")
        return {"name": "04-MATCH", "status": "error", "reason": str(e)}


if __name__ == "__main__":
    results = [test_03_match(), test_04_match()]

    print("\n" + "=" * 72)
    print("测试汇总")
    print("=" * 72)
    ok = sum(1 for r in results if r["status"] == "success")
    for r in results:
        mark = "✓" if r["status"] == "success" else "✗"
        print(f"  {mark} {r['name']}: {r['status']}")
    print(f"\n通过: {ok}/{len(results)}")
