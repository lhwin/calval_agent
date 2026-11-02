# Cal/Val Agent — 卫星高度计定标验证智能体

**LangGraph 驱动的多算子自动化工作流**，支持星间交叉、星自交叉、SIG0 交叉和验潮站参考四种定标方法。

---

## 🚀 快速开始

### 环境准备

```bash
# 安装依赖 (推荐 conda/virtualenv)
pip install -r requirements.txt

# 额外依赖（可选，根据算子需求）
pip install netCDF4 h5py python-docx openpyxl cartopy seaborn tables
```

### 运行示例

```bash
# 星间交叉定标
python main.py "用 S6A 和 JA3 做 2023 年 5 月的星间交叉"

# 星自交叉定标
python main.py "用 JA3 做自交叉监测漂移"

# 验潮站参考
python main.py "用验潮站做绝对基准参考"
```

---

## 📐 支持的算子

| 编号 | 名称 | 类型 | 输入 | 输出 |
|------|------|------|------|------|
| **01** | 星间交叉 (Star Cross) | MATCH + CAL | 两星 NC 文件 | `match_result_*.npz`, 偏差统计 |
| **02** | 星自交叉 (Self Cross) | MATCH + CAL | 同星 NC 文件 | `match_result_*.npz`, 漂移检测 |
| **03** | SIG0 交叉 | MATCH + CAL | 双星 H5/NC 文件 | `XOver_data_*.h5`, DOCX 报告 |
| **04** | 验潮站参考 (Tide Gauge) | MATCH + CAL | NC + 验潮 TXT | `MATCHED_*.npz`, 绝对偏差 |

---

## 🏗️ 架构概览

```
calval_agent/
├── agents/
│   ├── workflow.py           # LangGraph 工作流 (6 个节点)
│   ├── task_parser.py        # 自然语言解析器
│   └── state.py              # Agent 状态定义
├── operators/
│   ├── gpf_src/              # GPF 原始源码 (从服务器拷贝)
│   ├── star_cross_match.py   # 01-MATCH 包装器
│   ├── star_cross_cal.py     # 01-CAL 包装器
│   ├── self_cross_match.py   # 02-MATCH
│   ├── self_cross_cal.py     # 02-CAL
│   ├── sig0_cross_match.py   # 03-MATCH
│   ├── sig0_cross_cal.py     # 03-CAL
│   ├── ycz_match.py          # 04-MATCH
│   └── ycz_cal.py            # 04-CAL
├── core/
│   ├── base_operator.py      # 算子基类
│   └── op_config.py          # LocalConfig 配置类
├── data_adapter/
│   ├── explorer.py           # 本地数据扫描器
│   ├── xml_generator.py      # XML 工单生成器
│   └── ssh_executor.py       # SSH 远程执行器
├── GPF_test_data/            # 本地测试数据
│   ├── star_cross/
│   │   ├── input/S6A_20230501_20230503/   # S6A NC (66 个)
│   │   ├── input/NC/                      # 合并 NC 目录
│   │   └── match_result_S6A_vs_JA3_*.npz  # 已有匹配结果
│   ├── self_cross/
│   │   ├── input/NC/                      # 自交叉 NC
│   │   └── calibration_data_JA3_self_cross_*.npz
│   ├── sig0_cross/
│   │   └── XOver_data_*.h5                # SIG0 交叉数据
│   └── tide_ext/
│       ├── input/{DTU18MSS_1min.nc, WSTG/, HY-2BGDR/}
│       └── input_npz/MATCHED_H2B_YCZ_*.npz
├── output_local_test/        # 本地输出
├── config/                   # 配置文件
│   └── config_JA3_S6A_1hz.json
├── configs/settings.yaml     # 全局设置
├── main.py                   # 入口
└── requirements.txt
```

---

## 🔄 工作流逻辑

```
用户指令 (NL)
   ↓
[task_parser] → 提取卫星、日期、方法
   ↓
[data_discovery] → 扫描本地/远程数据
   ├─ 发现 NC 目录 → next_step="match" → MATCH 算子
   └─ 发现 NPZ 文件 → next_step="cal" → CAL 算子
   ↓
[branch_decision] → 有数据则执行，无数据则重试
   ├─ 成功 → execute_operator
   └─ 失败 → fallback_relax_params (最多 3 次)
   ↓
[execute_operator] → 调用对应的算子包装器
   ├─ run_local()  ← 本地执行 (优先)
   └─ run_ssh()    ← SSH 远程 (备用)
   ↓
[result_summarizer] → 汇总结果
```

---

## 🛠️ 核心特性

### 1. 智能任务解析

自动识别卫星 ID 和日期范围：

```python
from agents.task_parser import parse_task

parse_task("用 S6A 和 JA3 做 2023 年 5 月的星间交叉")
# → {
#     "primary_sat": "S6A",
#     "aux_data_type": "JA3",
#     "method": "star_cross",
#     "start_date": "20230501",
#     "end_date": "20230531"
#   }
```

支持的卫星格式：
- **3 字母代码**: `S6A`, `JA3`, `HY-1D`, `HY-2B`
- **长名称**: `Sentinel-6`, `Jason-3`, `CryoSat-2`

### 2. 数据发现

自动扫描本地数据：

```python
from data_adapter.explorer import LocalDataExplorer

explorer = LocalDataExplorer("GPF_test_data/star_cross")

# 查找 NC 文件
nc_files = explorer.find_nc_files(sat_id="S6A", date_range=("20230501", "20230531"))
print(f"找到 {len(nc_files)} 个 NC 文件")

# 查找匹配结果
match_results = explorer.find_match_files(sat_id="S6A")
```

### 3. 算子包装器

每个算子提供三种执行模式：

```python
from operators import get_operator
from core.op_config import LocalConfig

# 配置
cfg = LocalConfig(
    sat_id="S6A",
    aux_data_type="JA3",
    start_date="20230501",
    end_date="20230531",
    input_dir="GPF_test_data/star_cross/input/NC",
    output_dir="output_local_test/star_cross"
)

# 创建算子
op_class = get_operator("star_cross_match")
op = op_class(cfg)

# 模式 1: 本地执行 (直接从源码调用)
result = op.run_local(cfg.input_dir)

# 模式 2: SSH 远程执行 (需远程服务器)
# from data_adapter.ssh_executor import SSHExecutor
# result = op.run_ssh(ssh_client)

# 模式 3: 加载已有结果
outputs = op.load_output(cfg.output_dir)
```

---

## 📊 已知问题与解决方案

| 问题 | 原因 | 解决 |
|------|------|------|
| `KeyError: 'AUX_Sat'` | IPFUtils 解析 XML 时缺少参数 | 手动设置 `ipf_config.AUX_Sat` |
| `IndexError: list index out of range` (04-CAL) | XML 只有一个 `<Input>` 节点 | 生成两个 `<Input>` 节点 |
| `AttributeError` (字体相关) | 缺少 SimHei.ttf 字体文件 | 复制到 `operators/gpf_src/<module>/conf/` |
| HDF5 读取失败 (`truncated file`) | NC 文件下载不完整 | 重新下载或使用 SSH 远程执行 |
| `ModuleNotFoundError: No module named 'tables'` | 缺少 PyTables 依赖 | `pip install tables -i https://pypi.tuna.tsinghua.edu.cn/simple` |
| 模块缓存冲突 | 多次运行后 `IPFUtils` 被污染 | 清理 `sys.modules.pop("IPFUtils")` |

---

## 🧪 测试

### 运行算子测试

```bash
# 测试所有包装器实例化
python tests/test_wrappers.py

# 测试本地执行 (01/02-MATCH/CAL)
python tests/test_operators.py

# 测试 SSH 端到端
python tests/test_ssh_e2e.py
```

### 运行主程序

```bash
python main.py "用 S6A 和 JA3 做 2023 年 5 月的星间交叉"
```

**注意**: 如果 `GPF_test_data` 中的 NC 文件被截断（如从服务器拷贝不完整），程序会返回空结果但状态仍为 `success`。此时建议使用 SSH 远程执行模式（`run_ssh()`）或重新下载完整数据。

### 直接使用算子 API

```python
from operators import OperatorRegistry
from core.op_config import LocalConfig

# 配置
cfg = LocalConfig(
    sat_id="S6A",
    aux_data_type="JA3",
    start_date="20230501",
    end_date="20230531",
    input_dir="GPF_test_data/star_cross/input/S6A_20230501_20230503",
    output_dir="output_local_test/star_cross"
)

# 运行 MATCH
result = OperatorRegistry.run("star_cross_match", cfg)
print(result["status"])

# 运行 CAL (需要先有 MATCH 结果)
# result = OperatorRegistry.run("star_cross_cal", cfg)
```

### 预期输出

| 算子 | 成功标志 |
|------|---------|
| 01/02-MATCH | 1 个 `match_result_*.npz` |
| 01/02-CAL | 1 个 JSON + 1 个 TXT + 2 个 PNG |
| 03-MATCH | `XOver_data_*.h5` |
| 04-MATCH | `MATCHED_*.npz` |
| 04-CAL | 1 个 JSON + 1 个 TXT (DOCX 需模板) |

---

## 🔧 高级配置

### SSH 远程执行

SSH 配置通过环境变量或代码参数指定：

```python
from operators import get_operator
from data_adapter.ssh_executor import SSHExecutor

# 创建 SSH 客户端 (从参数获取)
ssh = SSHExecutor(host="192.168.240.132", username="leehir", key_path="~/.ssh/id_ed25519")

# 运行算子
op = get_operator("star_cross_cal")(cfg)
result = op.run_ssh(ssh)
```

**注意**: `configs/settings.yaml` 目前不包含 SSH 配置，需要在运行时显式提供主机参数。

### 自定义算子参数

在 `core/op_config.py` 扩展 `LocalConfig`：

```python
@dataclass
class LocalConfig:
    # ... 基础字段 ...
    distance_to_coast: float = 50.0  # km
    ocean_depth: float = 1000.0      # m
    select_area: Optional[List[float]] = None  # [min_lat, max_lat, min_lon, max_lon]
    template_docx: Optional[str] = None  # DOCX 报告模板
```

---

## 📝 开发指南

### 添加新算子

1. 从服务器拷贝源码到 `operators/gpf_src/<module_name>/`
2. 创建包装器 `operators/<module_name>.py` 继承 `BaseOperator`
3. 实现 `run_local()`, `run_ssh()`, `load_output()`
4. 在 `operators/__init__.py` 注册

### 调试技巧

```python
import sys
sys.path.insert(0, "operators/gpf_src/01_star_cross/match")

# 清除缓存
for k in list(sys.modules.keys()):
    if k == "IPFUtils" or k.startswith("func_"):
        del sys.modules[k]

from IPFUtils import MyIPFConfig
from func_GLSY_ALT_GDR_AUX_SAT_MATCH import func_cross_matching_pro

# 运行
func_cross_matching_pro(MyIPFConfig("xml_file.xml"))
```

---

## 🤝 贡献说明

本项目遵循以下原则：

1. **本地优先**: 优先实现本地包装器，SSH 仅作补充
2. **逐层验证**: MATCH → CAL 必须逐个验证，禁止跳步
3. **忠实封装**: 尽量保持 GPF 原始逻辑，最小化修改
4. **可复现**: 所有测试数据和配置应可追溯

---

## 📄 许可证

MIT License
未经允许，不得商用，商用联系作者 1097304039@qq.com (1元/年)
---

## 📞 联系方式

项目维护者: satelite 配置文件
文档地址: `D:\Software\hermes\profiles\satelite\skills\geophysical-data-processing\SKILL.md`
