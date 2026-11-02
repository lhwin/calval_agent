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

## 🏗️ 系统架构

### 层级视图

```
┌─────────────────────────────────────────────────────────────┐
│                     用户界面层                               │
│  python main.py "用 S6A 和 JA3 做 2023 年 5 月的星间交叉"        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              LangGraph 工作流引擎 (7 个节点)                   │
│                                                             │
│  [task_parser] → [data_discovery] → [data_health_check]     │
│                                               ↓             │
│  [result_summarizer] ← [execute_operator] ← [method_recommendation] ← [branch_decision] │
│                                  ↖ [fallback] ↙               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                  核心能力层 (层级 1/层级 2)                     │
│                                                             │
│  ✨ 层级 1 (已完成):                                        │
│  ├─ DataHealthChecker: NC/H5完整性诊断                      │
│  ├─ MethodRecommendation: 方法选择建议                       │
│  └─ BranchDecision: 数据存在性判断                          │
│                                                             │
│  🟡 层级 2 (规划中):                                         │
│  ├─ ParamOptimizer: 自适应参数调整                          │
│  ├─ ChainExecution: MATCH→CAL链式执行                       │
│  ├─ QualityEvaluator: 结果质量评估                          │
│  └─ SmartRetry: 智能失败恢复                                │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    算子包装器层                              │
│                                                             │
│  8 个 GPF 包装器 (每个支持 run_local / run_ssh):               │
│  ├─ StarCross{Match,Cal}Operator                           │
│  ├─ SelfCross{Match,Cal}Operator                           │
│  ├─ Sig0Cross{Match,Cal}Operator                           │
│  └─ Ycz{Match,Cal}Operator                                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    数据适配层                                │
│  ├─ LocalDataExplorer (数据扫描)                            │
│  ├─ XMLGenerator (工单生成)                                 │
│  └─ SSHExecutor (远程执行)                                  │
└─────────────────────────────────────────────────────────────┘
```

### 目录结构

```
calval_agent/
├── agents/                          # LangGraph 工作流
│   ├── workflow.py                  # 8 个节点的图定义
│   ├── state.py                     # Agent 状态 (20+ 字段)
│   ├── task_parser.py               # 自然语言解析
│   └── data_health_check.py         # ✨ 层级 1: 数据健康诊断
├── operators/
│   ├── gpf_src/                     # GPF 原始源码 (外部拷贝)
│   ├── star_cross_match.py          # 01-MATCH 包装器
│   ├── star_cross_cal.py            # 01-CAL 包装器
│   ├── self_cross_match.py          # 02-MATCH
│   ├── self_cross_cal.py            # 02-CAL
│   ├── sig0_cross_match.py          # 03-MATCH
│   ├── sig0_cross_cal.py            # 03-CAL
│   ├── ycz_match.py                 # 04-MATCH
│   └── ycz_cal.py                   # 04-CAL
├── core/
│   ├── base_operator.py             # 算子基类
│   ├── op_config.py                 # LocalConfig
│   ├── config.py                    # 配置加载
│   ├── models.py                    # 数据模型
│   └── operators_map.py             # 算子元信息映射
├── data_adapter/
│   ├── explorer.py                  # 本地数据扫描
│   ├── xml_generator.py             # XML 工单生成
│   └── ssh_executor.py              # SSH 远程执行
├── GPF_test_data/                   # 测试数据 (外部管理)
│   ├── star_cross/                  # 01 测试数据
│   ├── self_cross/                  # 02 测试数据
│   ├── sig0_cross/                  # 03 测试数据
│   └── tide_ext/                    # 04 测试数据
├── tests/                           # 单元测试
│   ├── test_wrappers.py             # 包装器实例化测试
│   ├── test_operators.py            # 本地执行测试
│   ├── test_ssh_e2e.py              # SSH 端到端测试
│   └── test_0304_match.py           # 03/04 MATCH 测试
├── docs/                            # 文档
│   ├── functional_spec.md           # 功能规格书 (层级 1/2)
│   └── architecture.md              # 技术架构图
├── configs/
│   └── settings.yaml                # 全局配置
├── main.py                          # 入口
├── requirements.txt
├── .gitignore
└── LICENSE                          # 非商用许可
```

---

## 🔄 工作流节点详解

### 节点 1: Task Parser

**功能**: 解析自然语言 → 结构化任务  
**输入**: `"用 S6A 和 JA3 做 2023 年 5 月的星间交叉"`  
**输出**:
```python
{
  "primary_sat": "S6A",
  "aux_data_type": "JA3", 
  "method": "star_cross",
  "start_date": "20230501",
  "end_date": "20230531"
}
```

### 节点 2: Data Discovery

**功能**: 扫描本地/远程数据  
**输入**: `{sat_id, date_range}`  
**输出**: `available_datasets = [{path, format, size, ...}]`

### 节点 3: Data Health Check ✨ 层级 1

**功能**: 诊断 NC/H5 文件完整性  
**检查项**:
- 文件大小合理性
- 必需变量存在性 (`latitude`, `range_correction`, `ssh`)
- 时间范围覆盖
- 数据点数量

**输出**:
```python
{
  "status": "healthy|warning|degraded|critical",
  "details": {
    "total_files": 47,
    "healthy": 27,
    "corrupted": 20
  },
  "recommendations": ["警告：20/47 文件无法读取"]
}
```

### 节点 4: Method Recommendation ✨ 层级 1

**功能**: 基于数据特征推荐定标方法  
**逻辑**:
1. 数据不健康 (`critical/degraded`) → **阻断** + 建议替代方法
2. 数据充足 (`available_count > 5`) → **允许继续**
3. 数据不足 → 推荐备选方案

**示例**:
```
输入：{method: "star_cross", available_count: 1}
输出: {
  action: "proceed",
  confidence: "low",
  reasoning: ["星间交叉适合检测卫星间系统性偏差", "但数据量不足 (1 个)"],
  alternative_methods: [{method: "self_cross", reason: "可先做自交叉监测漂移"}]
}
```

### 节点 5: Branch Decision

**功能**: 根据推荐结果路由  
**分支**:
- `abort` → 直接结束，返回诊断报告
- `proceed` → 进入执行阶段

### 节点 6: Execute Operator

**功能**: 执行选定的算子包装器  
**模式**:
- `run_local()`: 直接调用 Python 源码 (优先)
- `run_ssh()`: 远程执行 (备用)

### 节点 7: Fallback 🟡 层级 2

**功能**: 智能重试策略  
**策略**:
```python
retry 1: 放宽海岸距离 (50km → 100km)
retry 2: 放宽海洋深度 (1000m → 2000m)
retry 3: 放宽风速范围 ([2, 40] → [0, 50])
max_retries: 3
```

### 节点 8: Result Summarizer

**功能**: 汇总最终结果  
**输出**: JSON/TXT/PNG产品

---

## 🎯 层级演进路线

### ✨ 层级 1 (已完成) — **数据智能与诊断**

| 模块 | 功能 | 状态 |
|------|------|------|
| `DataHealthChecker` | NC/H5完整性诊断 | ✅ |
| `MethodRecommendation` | 方法选择建议 | ✅ |
| `BranchDecision` | 数据存在性判断 | ✅ |
| `AutoAbort` | 数据质量不佳时自动阻断 | ✅ |

**核心价值**: 避免无效计算，提前识别数据质量问题。

### 🟡 层级 2 (规划中) — **自适应与优化**

| 模块 | 功能 | 计划 |
|------|------|------|
| `ParamOptimizer` | 根据数据特征动态调整参数 | Week 5-6 |
| `ChainExecution` | MATCH→CAL自动链式执行 | Week 5-6 |
| `QualityEvaluator` | 结果质量评分 (RMSE/R²/残差分布) | Week 6 |
| `SmartRetry` | 基于失败原因的自适应重试 | Week 6 |
| `KnowledgeBase` | 历史案例记忆与复用 | Week 7-8 |

**预期效果**: 实现"一句话定标"，全流程无需人工干预。

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
from operators import OperatorRegistry
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

# 运行 MATCH
result = OperatorRegistry.run("star_cross_match", cfg)
print(result["status"])

# 运行 CAL (需要先有 MATCH 结果)
# result = OperatorRegistry.run("star_cross_cal", cfg)
```

每个算子类继承 `BaseOperator`，提供以下方法：

```python
from operators.star_cross_match import StarCrossMatchOperator

op = StarCrossMatchOperator(cfg)

# 本地执行
result = op.run_local(cfg.input_dir)

# SSH 远程执行
from data_adapter.ssh_executor import SSHExecutor
ssh = SSHExecutor(host="192.168.240.132", username="leehir", key_path="~/.ssh/id_ed25519")
result = op.run_ssh(ssh)

# 加载已有输出
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

**未经授权，不得用于商业用途**。  
商用请联系：1097304039@qq.com (1 元/年)
---

## 📞 联系方式
1097304039@qq.com