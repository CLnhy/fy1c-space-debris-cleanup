# 太空抓手 / 风云一号 C 碎片清理研究

本项目包含风云一号 C 碎片轨道筛选、多目标清理路线计算、三指抓取初步蒙特卡洛评估、Simulink/Simscape 抓取模型，以及配套报告和计算表。

## 项目结构

```text
.
├─ src/
│  ├─ orbit/                 # 轨道数据下载、筛选和任务路线计算
│  └─ capture/               # 抓取蒙特卡洛仿真与绘图
├─ simulink/                 # MATLAB/Simulink/Simscape 模型与构建脚本
├─ tools/reporting/          # Word 报告和 Excel 计算表生成工具
├─ data/
│  ├─ raw/                   # 探索性分析使用的原始 CelesTrak 数据
│  └─ processed/             # 探索性分析的派生数据
├─ public_debris_calculation/# 正式计算使用的冻结快照和筛选结果
├─ outputs/                  # 报告、表格、仿真结果和图片
├─ web/                      # 轨道可视化页面
└─ vendor/                   # 项目内置的第三方离线依赖
```

## 主要工作流

以下命令均从项目根目录运行。

### 1. 获取并探索轨道数据

```powershell
python src/orbit/download_celestrak.py
python src/orbit/analyze_fy1c.py
```

下载结果写入 `data/raw/`，探索性筛选表写入 `data/processed/`。

### 2. 生成正式任务筛选结果

```powershell
python src/orbit/public_debris_mission_calc.py --offline
```

离线模式读取 `public_debris_calculation/` 中的冻结快照，并更新同目录下的 `screening_result.json`。不加 `--offline` 时会重新请求 CelesTrak。

> `analyze_fy1c.py` 是早期探索性分析；`public_debris_mission_calc.py` 及其冻结快照是报告和后续仿真的正式数据链。两者的筛选条件不同，不应混用结果。

### 3. 运行初步抓取仿真

```powershell
python src/capture/preliminary_capture_sim.py
python src/capture/plot_capture_results.py
```

结果写入 `outputs/preliminary_capture_sim/`。

### 4. 生成报告和计算表

```powershell
python tools/reporting/build_fy1c_report.py
node tools/reporting/build_calculation_tables.mjs
```

生成文件分别位于 `outputs/fy1c_cleanup_report/` 和 `outputs/space_debris_calculation_tables/`。

### 5. 构建 Simulink/Simscape 抓取模型

在 MATLAB 中依次运行：

```matlab
run('simulink/build_capture_dynamics_v1.m')
run('simulink/extend_capture_dynamics_v2.m')
run('simulink/extend_capture_dynamics_v3_contact.m')
run('simulink/configure_contact_approach_demo.m')
run('simulink/upgrade_to_three_finger_capture.m')
run('simulink/restore_three_finger_logging.m')
```

模型文件保存在 `simulink/capture_dynamics_v1.slx`。已有仿真 JSON 结果可用 `simulink/plot_capture_results.m` 绘图。

## 数据与结果约定

- `public_debris_calculation/` 是可复现正式结果的输入快照与中间结果，保持版本化。
- `outputs/` 是当前交付成果，保持版本化。
- `.deps/`、`.tmp_pkgs/`、`local_packages/` 和 `node_modules/` 是本地运行依赖或缓存，不纳入版本控制。
- 各脚本通过自身位置解析项目根目录，因此可从项目根目录或其他工作目录启动。
