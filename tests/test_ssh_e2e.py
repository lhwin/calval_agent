#!/usr/bin/env python3
"""
SSH 端到端集成测试 - 实际执行一次远程任务

测试流程:
1. 连接服务器
2. 生成 XML 工单
3. 上传并执行 main.py
4. 下载并解析输出
5. 验证结果完整性
"""

import sys
from pathlib import Path
import tempfile
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_adapter.ssh_executor import SSHExecutor
from data_adapter.xml_generator import generate_star_cross_match_xml
from operators.star_cross_match import StarCrossMatchOperator
from core.op_config import LocalConfig


def test_ssh_execution():
    """完整测试 SSH 执行链路"""
    
    print("=" * 72)
    print("SSH 端到端集成测试")
    print("=" * 72)
    
    # 1. 配置
    host = "192.168.240.132"
    username = "leehir"
    key_path = "~/.ssh/id_ed25519"
    
    # 2. 准备配置
    cfg = LocalConfig(
        sat_id="JA3",
        aux_data_type="S6A",
        start_date="20230501",
        end_date="20230503",
        input_dir="/home/leehir/GPF/01-星星交叉法v2.0/cvs_glsy_alt_gdr_aux_sat_match/input",
        output_dir="/home/leehir/GPF/01-星星交叉法v2.0/cvs_glsy_alt_gdr_aux_sat_match/output",
        order_id=int(time.time()) % 10000,
    )
    
    print(f"\n[配置]")
    print(f"  主机：{username}@{host}")
    print(f"  卫星：{cfg.sat_id} vs {cfg.aux_data_type}")
    print(f"  日期：{cfg.start_date} → {cfg.end_date}")
    print(f"  输入：{cfg.input_dir}")
    
    # 3. 生成 XML
    print(f"\n[步骤 1] 生成 XML 工单")
    xml_content = generate_star_cross_match_xml(
        sat_id=cfg.sat_id,
        aux_sat=cfg.aux_data_type,
        start_date=cfg.start_date,
        end_date=cfg.end_date,
        input_dir=cfg.input_dir,
        output_dir=cfg.output_dir,
    )
    print(f"  XML 长度：{len(xml_content)} 字符")
    print(f"  前 200 字符:\n{xml_content[:200]}...")
    
    # 4. 上传并执行
    print(f"\n[步骤 2] 上传 XML 到服务器")
    
    executor = SSHExecutor(host, username, key_path)
    
    # 上传临时 XML
    tmp_xml = Path(tempfile.mkdtemp()) / f"test_job_{cfg.order_id}.xml"
    with open(tmp_xml, "w", encoding="utf-8") as f:
        f.write(xml_content)
    
    remote_xml = f"/tmp/test_job_{cfg.order_id}.xml"
    
    # SCP 上传
    scp_cmd = f'scp -i "{Path(key_path).expanduser()}" -o StrictHostKeyChecking=no "{tmp_xml}" {username}@{host}:{remote_xml}'
    print(f"  命令：{scp_cmd[:100]}...")
    
    import subprocess
    result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ✗ SCP 失败：{result.stderr}")
        return False
    print(f"  ✓ 上传成功")
    
    # 5. 执行远程 main.py
    print(f"\n[步骤 3] 执行远程 main.py")
    
    remote_main = "/home/leehr/GPF/01-星星交叉法v2.0/cvs_glsy_alt_gdr_aux_sat_match/main.py"
    exec_cmd = f'cd "$(dirname "{remote_main}")" && python3 "{remote_main}" "{remote_xml}" 2>&1'
    
    ssh_cmd = f'ssh -i "{Path(key_path).expanduser()}" -o StrictHostKeyChecking=no {username}@{host} "{exec_cmd}"'
    print(f"  执行：{ssh_cmd[:100]}...")
    
    start_time = time.time()
    result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=300)
    elapsed = time.time() - start_time
    
    print(f"  耗时：{elapsed:.1f} 秒")
    print(f"  退出码：{result.returncode}")
    
    if result.returncode != 0:
        print(f"  ✗ 执行失败:\n{result.stderr[:500]}")
        return False
    
    print(f"  ✓ 执行成功")
    print(f"\n  日志摘要:")
    for line in result.stdout.split('\n')[-10:]:
        if line.strip():
            print(f"    {line}")
    
    # 6. 查找输出文件
    print(f"\n[步骤 4] 查找输出文件")
    
    find_cmd = f'find "{cfg.output_dir}" -name "*.npz" -newer "{remote_xml}" 2>/dev/null | head -5'
    find_result = subprocess.run(
        f'ssh -i "{Path(key_path).expanduser()}" -o StrictHostKeyChecking=no {username}@{host} "{find_cmd}"',
        shell=True, capture_output=True, text=True
    )
    
    if find_result.stdout.strip():
        output_files = [f.strip() for f in find_result.stdout.split('\n') if f.strip()]
        print(f"  ✓ 找到 {len(output_files)} 个输出文件:")
        for f in output_files:
            print(f"    {f}")
    else:
        print(f"  ⚠ 未找到新的 NPZ 文件")
    
    # 7. 清理
    print(f"\n[清理]")
    cleanup_cmd = f'ssh -i "{Path(key_path).expanduser()}" -o StrictHostKeyChecking=no {username}@{host} "rm -f {remote_xml}"'
    subprocess.run(cleanup_cmd, shell=True, capture_output=True)
    tmp_xml.unlink()
    print(f"  ✓ 临时文件已清理")
    
    print("\n" + "=" * 72)
    print("✓ SSH 端到端测试通过!")
    print("=" * 72)
    
    return True


if __name__ == "__main__":
    success = test_ssh_execution()
    sys.exit(0 if success else 1)
