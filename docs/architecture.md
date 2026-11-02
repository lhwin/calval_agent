# Cal/Val Agent — 技术架构一览

**版本**: v2.0  
**面向**: 技术评审 / 架构讨论

---

## 🏛️ 系统架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                          用户界面层                                   │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  python main.py "用 S6A 和 JA3 做 2023 年 5 月的星间交叉"         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        LangGraph 工作流引擎                            │
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐       │
│  │ task_parser │ →  │ data_discovery │ → │ data_health_check   │       │
│  │ (解析指令)   │    │ (发现数据)     │    │ (数据质量诊断)       │       │
│  └─────────────┘    └─────────────┘    └─────────────────────┘       │
│                                         ↓                           │
│  ┌─────────────────┐   ┌──────────────────┐   ┌─────────────────┐   │
│  │ result_summarizer │←│ method_recommendation│←│branch_decision │   │
│  │ (汇总报告)        │  │ (方法推荐)         │  │ (分支路由)        │   │
│  └─────────────────┘   └──────────────────┘   └─────────────────┘   │
│                                         ↑                           │
│  ┌─────────────────┐   ┌──────────────────┐                         │
│  │ execute_operator │← │   fallback        │                         │
│  │ (执行算子)        │  │ (智能重试)         │                         │
│  └─────────────────┘   └──────────────────┘                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        核心能力层                                    │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │star_cross   │  │self_cross   │  │sig0_cross   │  │ycz        │ │
│  │(星间交叉)    │  │(星自交叉)    │  │(SIG0 交叉)   │  │(验潮站)    │ │
│  │MATCH+CAL    │  │MATCH+CAL    │  │MATCH+CAL    │  │MATCH+CAL  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │data_health  │  │param_opt    │  │quality_eval │  │auto_retry  │ │
│  │(健康诊断)    │  │(参数优化)    │  │(质量评估)    │  │(智能重试)    │ │
│  │✅已实现      │  │🟡规划中      │  │🟡规划中      │  │🟡规划中      │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        数据适配层                                    │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ explorer    │  │xml_generator│  │ssh_executor │  │cache_mgr   │ │
│  │(数据发现)    │  │(XML 生成器)  │  │(SSH 执行器)   │  │(缓存管理)    │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        存储层                                        │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │GPF_test_data│  │output_local │  │logs         │  │cache/      │ │
│  │(测试数据)    │  │test/        │  │             │  │scratch/     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 工作流状态流转

```
用户指令
   ↓
┌─────────────────────────────────────────────────────────────┐
│ [START]                                                     │
│  task_parser: 解析自然语言 → 卫星 ID、日期、方法                │
└─────────────────────────────────────────────────────────────┘
   ↓
┌─────────────────────────────────────────────────────────────┐
│ [DISCOVERY]                                                 │
│  data_discovery: 扫描本地/远程数据 → available_datasets      │
└─────────────────────────────────────────────────────────────┘
   ↓
┌─────────────────────────────────────────────────────────────┐
│ [HEALTH_CHECK] ✨ 层级 1                                      │
│  data_health_check:                                       │
│    - 检查文件完整性 (NC/H5)                                 │
│    - 计算损坏比例                                          │
│    - 判断健康状态 (healthy/warning/degraded/critical)         │
└─────────────────────────────────────────────────────────────┘
   ↓
   ├─ critical/degraded (>30% 损坏) → 阻断 → [END]
   └─ healthy/warning → 继续
   ↓
┌─────────────────────────────────────────────────────────────┐
│ [RECOMMENDATION] ✨ 层级 1                                    │
│  method_recommendation:                                   │
│    - 基于数据特征和方法类型                                │
│    - 生成推荐 (proceed/abort)                             │
│    - 提供替代方案                                          │
└─────────────────────────────────────────────────────────────┘
   ↓
   ├─ abort → [END]
   └─ proceed → 继续
   ↓
┌─────────────────────────────────────────────────────────────┐
│ [DECISION]                                                  │
│  branch_decision:                                         │
│    - 有数据? → MATCH                                      │
│    - 有 NPZ? → CAL                                       │
│    - 无数据? → 报错                                      │
└─────────────────────────────────────────────────────────────┘
   ↓
┌─────────────────────────────────────────────────────────────┐
│ [EXECUTE]                                                   │
│  execute_operator:                                        │
│    - 运行 MATCH (NC → NPZ)                                │
│    - 或运行 CAL (NPZ → 统计 + 图表)                       │
└─────────────────────────────────────────────────────────────┘
   ↓
   ├─ 成功 → 进入总结
   └─ 失败 → 进入重试
   ↓
┌─────────────────────────────────────────────────────────────┐
│ [FALLBACK] 🟡 层级 2                                          │
│  fallback:                                                │
│    - 识别失败原因                                          │
│    - 选择重试策略                                          │
│    - 调整参数 (最大 3 次)                                    │
└─────────────────────────────────────────────────────────────┘
   ↓
┌─────────────────────────────────────────────────────────────┐
│ [QUALITY_EVAL] 🟡 层级 2                                      │
│  result_quality_checker:                                  │
│    - 统计显著性                                            │
│    - 残差分布                                              │
│    - 时间稳定性                                            │
└─────────────────────────────────────────────────────────────┘
   ↓
┌─────────────────────────────────────────────────────────────┐
│ [SUMMARY]                                                   │
│  result_summarizer:                                       │
│    - 汇总结果 (偏差均值、RMSE、R²、样本数)                  │
│    - 生成日志                                              │
│    - 返回最终报告                                          │
└─────────────────────────────────────────────────────────────┘
   ↓
[END]
```

---

## 🧩 核心模块详解

### 1. 数据健康诊断 (`agents/data_health_check.py`)

```python
class DataHealthChecker:
    def check_nc_integrity(nc_path) -> Dict:
        """检查 NC 文件完整性"""
        # - 文件大小合理性
        # - 必需变量存在性
        # - 数据点数量
        # - 时间范围
        
    def quick_scan(base_dir) -> Dict:
        """批量扫描目录健康状况"""
        # - 健康/降级/损坏计数
        # - 详细文件列表
```

**输入**: 文件路径或目录  
**输出**: 
```json
{
  "status": "degraded",
  "details": {
    "total_files": 47,
    "healthy": 0,
    "corrupted": 20
  },
  "recommendations": ["警告：20/47 文件无法读取"]
}
```

### 2. 方法推荐引擎 (`agents/workflow.py` → `method_recommendation_node`)

```python
def method_recommendation_node(state):
    health_status = state.health_report.status
    available_count = len(state.available_datasets)
    
    if health_status in ("critical", "degraded"):
        return {"action": "abort", ...}
    
    method = state.parsed_task.method
    
    # 生成推荐逻辑
    # - 数据不足 → 建议替代方法
    # - 数据充足 → 允许继续
```

### 3. 算子包装器 (`operators/*.py`)

| 包装器 | 模式 | 说明 |
|--------|------|------|
| `StarCrossMatchOperator` | `run_local()` / `run_ssh()` | 星间交叉匹配 |
| `StarCrossCalOperator` | `run_local()` / `run_ssh()` | 星间交叉定标 |
| `SelfCrossMatchOperator` | `run_local()` / `run_ssh()` | 星自交叉匹配 |
| `SelfCrossCalOperator` | `run_local()` / `run_ssh()` | 星自交叉定标 |
| `Sig0CrossMatchOperator` | `run_local()` / `run_ssh()` | SIG0 交叉匹配 |
| `YczMatchOperator` | `run_local()` / `run_ssh()` | 验潮站匹配 |
| `YczCalOperator` | `run_local()` / `run_ssh()` | 验潮站定标 |

---

## 🔑 关键技术栈

| 技术 | 用途 | 版本 |
|------|------|------|
| **LangGraph** | 工作流编排 | ≥0.2.0 |
| **netCDF4** | NC 文件读写 | ≥1.5.0 |
| **h5py / tables** | H5 文件读写 | ≥3.0.0 |
| **SciPy** | 统计计算 | ≥1.11.0 |
| **numpy / pandas** | 数据处理 | ≥1.24.0 / ≥2.0.0 |
| **python-docx** | DOCX 报告生成 | ≥0.8.0 |
| **OpenSSH** | 远程执行 | ≥7.0 |

---

## 💻 部署环境

### 硬件要求
- CPU: 4 核以上
- RAM: ≥8GB
- Disk: ≥10GB (含测试数据)

### 软件要求
- OS: Windows / Linux / macOS
- Python: 3.9+
- Conda/venv: 推荐
- SSH: Git Bash (Windows) 或 native bash (Linux/macOS)

### 依赖安装
```bash
pip install -r requirements.txt
pip install netCDF4 h5py python-docx openpyxl tqdm cartopy seaborn tables
```

---

## 📊 性能基准

| 操作 | 耗时 | 备注 |
|------|------|------|
| 任务解析 | <50ms | 纯 CPU |
| 健康诊断 (47 文件) | ~800ms | 并行扫描 |
| MATCH (76 NC → NPZ) | ~3s | 单机 |
| CAL (NPZ → 统计) | ~1s | 单机 |
| 端到端 (完整流程) | ~5s | 无网络延迟 |

---

## 🔄 版本演进

| 版本 | 时间 | 里程碑 |
|------|------|--------|
| v1.0 | Week 1 | 算子包装器完成 |
| v1.5 | Week 2 | 工作流打通 |
| v2.0 | Week 3 | **层级 1 完成** (数据诊断 + 方法推荐) |
| v3.0 | Week 5-6 | 层级 2 完成 (参数优化 + 链式执行) |
| v4.0 | Week 7-8 | 甲方验收 |

---

## 📁 项目结构

```
calval_agent/
├── agents/
│   ├── workflow.py                 # LangGraph 工作流
│   ├── state.py                    # 状态定义
│   ├── task_parser.py              # 任务解析
│   └── data_health_check.py        # 数据诊断 ✨
├── operators/
│   ├── gpf_src/                    # GPF 原始源码
│   ├── star_cross_*.py             # 星间交叉
│   ├── self_cross_*.py             # 星自交叉
│   ├── sig0_cross_*.py             # SIG0 交叉
│   └── ycz_*.py                    # 验潮站
├── core/
│   ├── base_operator.py
│   └── op_config.py
├── data_adapter/
│   ├── explorer.py
│   ├── xml_generator.py
│   └── ssh_executor.py
├── GPF_test_data/
├── output_local_test/
├── config/
├── configs/settings.yaml
├── tests/
├── docs/
│   ├── functional_spec.md          # 功能说明
│   └── architecture.md             # 本文档
├── main.py
└── requirements.txt
```

---

## 🚀 扩展性设计

### 插件式算子注册
```python
from operators import OperatorRegistry

# 新增算子只需:
# 1. 继承 BaseOperator
# 2. 实现 run_local/run_ssh/load_output
# 3. 注册到 OperatorRegistry
```

### 可插拔的诊断策略
```python
class DataHealthChecker:
    def add_diagnostic(self, name, checker_fn):
        """动态添加诊断项"""
        self.diagnostic_fns[name] = checker_fn
```

### 策略模式的重试机制
```python
class RetryPolicy:
    def get_strategy(failure_type):
        return {
            "data_too_small": ExpandDateRange(),
            "too_many_outliers": RelaxThreshold(),
            ...
        }[failure_type]
```

---

## 📝 总结

**层级 1** 已完成数据健康诊断和方法推荐，实现自动化的数据质量控制，避免无效计算。  
**层级 2** 将聚焦参数优化、链式执行、结果评估和智能重试，进一步提升自动化程度和用户体验。

---

**文档版本**: v1.0  
**更新日期**: 2026-11-01
