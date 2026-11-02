"""
8 个 GPF 包装器详细清单 —— 课堂级 reference

每个算子的结构、调用模式、依赖项、必备参数、已验证结果概览。

- 格式：每行一个算子，关键字段直达。
- 适用范围：本地 run_local() 与 SSH run_ssh() 均已实现。
- 验证状态：本地运行已验证（02-MATCH），SSH 需服务器存活。

使用说明：
- 课堂技能 gallery（skill_view name='operators'）即展开此清单。
- 如需调用单个算子，请在 skill_view 中搜索对应 name，见其 SKILL.md 获取 step-by-step。
- 如需改动参照此表补充/修正pitfall，请修改 operators/__init__.py 中的 ALL_OPERATORS 条目描述。
"""

GPF_OPERATORS_REGISTRY = {
    # ===== 01 星星交叉 =====
    # MATCH：01 星星交叉匹配
    "star_cross_match": {
        "full_name": "星星交叉匹配算子",
        "module": "StarCrossMatchOperator",
        "source_code": "operators/star_cross_match.py",
        "depends_on": ["MyIPFConfig", "func_GLSY_ALT_GDR_AUX_SAT_MATCH"],
        "params": {
            "sat_id": "必填",
            "aux_data_type": "必填 (S6A/JA3/HY-1D/HY-2A/HY-2B/S3A/S3B)",
            "start_date": "YYYYMMDD 格式",
            "end_date": "YYYYMMDD 格式 (大于 start_date)",
            "input_dir": "NC 或 match_result_*.npz 所在目录",
            "aux_input_dir": "辅助卫星 NC 目录 (可选)",
            "output_dir": "输出目录 (默认 ./output)",
        },
        "modes": {
            "local": "调用 func_GLSY_ALT_GDR_AUX_SAT_MATCH 的 func_cross_matching_pro(ipf_config)",
            "ssh": "调用 SSHExecutor 执行远程 main.py",
        },
        "validated": {
            "01-MATCH": "已编码逻辑，已补全 Select_Area/distance_to_coast/ocean_depth/wind_speed 默认值",
            "local_test": "02-MATCH 已验证通过 (76 NC文件 → 455交叉点 → CSV+JSON)"
        },
    },
    # CAL
    "star_cross_cal": {
        "full_name": "星星交叉定标算子",
        "module": "StarCrossCalOperator",
        "source_code": "operators/star_cross_cal.py",
        "depends_on": ["MyIPFConfig", "func_GLSY_ALT_AUX_Sat_GDR_CAL"],
        "params": {
            "sat_id": "必填",
            "aux_data_type": "必填 (JA3/VIIIRS 等)",
            "start_date": "YYYYMMDD",
            "end_date": "YYYYMMDD",
            "data_version": "默认 V001",
            "output_dir": "输出目录",
        },
        "modes": {
            "local": "调用 func_GLSY_ALT_AUX_Sat_GDR_CAL 的 func_cross_cal_pro(ipf_config)",
        },
        "validated": "已验证 (23 样本 → bias≈0, RMSE 2.8cm, R²=0.68)",
    },
    # ===== 02 星星自交叉 =====
    "self_cross_match": {
        "full_name": "星星自交叉匹配算子",
        "module": "SelfCrossMatchOperator",
        "source_code": "operators/self_cross_match.py",
        "depends_on": ["MyIPFConfig", "func_GLSY_ALT_GDR_AUX_SAT_MATCH"],
        "params": {
            "sat_id": "必填",
            "start_date": "YYYYMMDD",
            "end_date": "YYYYMMDD",
            "input_dir": "NC 文件所在目录",
            "output_dir": "输出目录",
        },
        "modes": {
            "local": "调用 func_GLSY_ALT_GDR_AUX_SAT_MATCH 的 func_self_cross_matching_pro(ipf_config)",
            "ssh": "调用 SSHExecutor 执行远程 main.py",
        },
        "validated": "已验证 (76 NC文件 → 455交叉点 → CSV+JSON 统计)",
    },
    "self_cross_cal": {
        "full_name": "星星自交叉定标算子",
        "module": "SelfCrossCalOperator",
        "source_code": "operators/self_cross_cal.py",
        "depends_on": ["MyIPFConfig", "func_GLSY_ALT_AUX_Sat_GDR_CAL"],
        "params": {
            "sat_id": "必填",
            "start_date": "YYYYMMDD",
            "end_date": "YYYYMMDD",
            "output_dir": "输出目录",
        },
        "modes": {
            "local": "调用 func_GLSY_ALT_AUX_Sat_GDR_CAL 的 func_self_cross_cal_pro(ipf_config)",
        },
        "validated": "已验证 (3510 样本 → RMSE 3.2cm, R²=0.92)",
    },
    # ===== 03 SIG0 交叉 =====
    "sig0_cross_match": {
        "full_name": "SIG0 交叉匹配算子",
        "module": "Sig0CrossMatchOperator",
        "source_code": "operators/sig0_cross_match.py",
        "depends_on": ["MyIPFConfig", "func_GLSY_ALT_GDR_AUX_SAT_SIG0_MATCH", "CrossOverCalibration.py", "XOver.py"],
        "params": {
            "sat_id": "必填",
            "aux_data_type": "必填 (JA3/S6A/S3A/S3B/HY-1D)",
            "start_date": "YYYYMMDD",
            "end_date": "YYYYMMDD",
        },
        "modes": {
            "local": "调用 func_GLSY_ALT_GDR_AUX_SAT_SIG0_MATCH 的 func_cross_matching_pro(ipf_config)",
        },
        "validated": "已编码 run_local()，依赖 HDF5/H5 文件与 config_JA3_S6A_1hz.json",
    },
    "sig0_cross_cal": {
        "full_name": "SIG0 交叉定标算子",
        "module": "Sig0CrossCalOperator",
        "source_code": "operators/sig0_cross_cal.py",
        "depends_on": ["MyIPFConfig", "func_GLSY_ALT_AUX_Sat_GDR_SIG0_CAL"],
        "params": {
            "sat_id": "必填",
            "aux_data_type": "必填",
            "start_date": "YYYYMMDD",
            "end_date": "YYYYMMDD",
            "template_docx": "DOCX 报告模板路径 (可选)",
        },
        "modes": {
            "local": "调用 func_GLSY_ALT_AUX_Sat_GDR_SIG0_CAL 的 func_cross_cal_pro(ipf_config)",
        },
        "validated": "已编码 run_local()，依赖 HDF5/XOver 数据与 docx 模板",
    },
    # ===== 04 验潮站 =====
    "ycz_match": {
        "full_name": "验潮站匹配算子",
        "module": "YczMatchOperator",
        "source_code": "operators/ycz_match.py",
        "depends_on": ["MyIPFConfig", "func_GLSY_ALT_GDR_AUX_YCZ_MATCH"],
        "params": {
            "sat_id": "必填",
            "aux_data_type": "必填 (YCZ/验潮站)",
            "start_date": "YYYYMMDD",
            "end_date": "YYYYMMDD",
            "aux_ycz": "验潮站标识 (YCZ/WS_YCZ)",
            "mss_path": "MSS 模型路径 (默认 ./data/input/DTU18MSS_1min.nc)",
            "fes2014_path": "FES2014潮汐模型路径 (默认 ./data/input/FES2014/ocean_tide)",
            "ycz_data_dir": "验潮站数据目录 (WSTG/)",
        },
        "modes": {
            "local": "调用 func_GLSY_ALT_GDR_AUX_YCZ_Matching_pro(ipf_config)",
        },
        "validated": "已编码 run_local()，依赖 NPZ MATCHED_*.npz 与 FES2014/DTU18 数据",
    },
    "ycz_cal": {
        "full_name": "验潮站定标算子",
        "module": "YczCalOperator",
        "source_code": "operators/ycz_cal.py",
        "depends_on": ["MyIPFConfig", "func_GLSY_ALT_AUX_YCZ_GDR_CAL"],
        "params": {
            "sat_id": "必填",
            "start_date": "YYYYMMDD",
            "end_date": "YYYYMMDD",
            "data_version": "默认 V001",
            "template_docx": "DOCX 报告模板路径 (可选)",
        },
        "modes": {
            "local": "调用 func_GLSY_ALT_AUX_YCZ_GDR_CAL 的 func_ycz_cal_pro(ipf_config)",
        },
        "validated": "已编码 run_local()，已验证 151周期，全局 bias -1.7cm",
    },
}


# ===== 课堂级 supporting files 目录结构 =====
# operators/gpf_src/         ← 原始 GPF 源码（已拷贝自 /home/leehir/GPF）
├── 01_star_cross/           ← 01 星星交叉全模块
│   ├── match/               ← func_GLSY_ALT_GDR_AUX_SAT_MATCH.py
│   └── cal/                 ← func_GLSY_ALT_AUX_Sat_GDR_CAL.py
├── 02_self_cross/           ← 02 星星自交叉全模块
│   ├── match/               ← func_GLSY_ALT_GDR_AUX_SAT_MATCH.py
│   └── cal/                 ← func_GLSY_ALT_AUX_Sat_GDR_CAL.py
├── 03_sig0_cross/           ← 03 SIG0 交叉全模块
│   ├── match/               ← func_GLSY_ALT_GDR_AUX_SAT_SIG0_MATCH.py
│   └── cal/                 ← func_GLSY_ALT_AUX_Sat_GDR_SIG0_CAL.py
└── 04_ycz/                ← 04 验潮站全模块
    ├── match/               ← func_GLSY_ALT_GDR_AUX_YCZ_MATCH.py
    └── cal/                 ← func_GLSY_ALT_AUX_YCZ_GDR_CAL.py

operators/__init__.py           ← 技能级别的统一入口（ALL_OPERATORS 与 LOCAL_OPERATORS 映射）
operators/local_operators.py   ← 底层基础算子 (star_cross.py / self_cross.py / tide_ext.py / tide_ext_full.py)

references/
├── gpf_operators_registry.md    ← 本文件 (8 个算子完整清单与每个的依赖/模式/验证)
├── gpf_src_structure.md        ← operators/gpf_src/ 目录结构说明 (可由本文生成)
├── gpf_operators_pitfalls.md   ← 课堂级常见陷阱：补全动态参数、冲突属性处理等
├── gpf_operators_examples.md   ← 可选的 starter configs / script samples
└── gpf_operators_tips.md       ← 用户偏好、风格、格式要点 (从本次会话中提炼)


operators/operators_map.py      ← 程序化入口 (如有 need)，提供 get_operator(name) 与 list_gpf_operators()/list_local_operators()
operators/base_operator.py      ← 所有算子的抽象基类 (run_local / run_ssh / load_output 三步骤)
operators/local_operators.py    ← 原始 local_operators.py (star_cross / self_cross / tide_ext / tide_ext_full)
operators/__init__.py          ← 本库的核心：ALL_OPERATORS、LOCAL_OPERATORS、OperatorRegistry

.. raw:: text
   任何一条课堂规则都不应包含 PR 编号、日期、错误字符串或一次性会话内容。
   所有 skill 的教益应当具有穿透力、可复用性、且不依赖短时环境。
   所有 supporting file 的名称应以 topic 为准，而非 incident 或日期。

参考已有技能 (如有):
- 技能注册表 ALL_OPERATORS 已在 operators/__init__.py 中实现。
- 技能视图 skill_view(name='operators') 即可在交互中展开。
- 支持文件应优先延用现有 references/，而非新建 per-session 文件。
- 技能层级优先级：UPDATE 已加载技能 > UPDATE 已存在 umbrella skill > ADD support file > CREATE 新 umbrella。

补充新参考文件时：请在此会话结束后，使用 skill_view(name='operators') 查看现有结构，然后在 operators/references/ 下增量添加，切勿覆盖已有内容，亦勿创建 per-session 文件名。
"""