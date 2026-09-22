import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(scriptDir, "..", "..");
const sourcePath = path.join(rootDir, "public_debris_calculation", "screening_result.json");
const outputDir = path.join(rootDir, "outputs", "space_debris_calculation_tables");
const result = JSON.parse(await fs.readFile(sourcePath, "utf8"));
await fs.mkdir(outputDir, { recursive: true });

const workbook = Workbook.create();
const summary = workbook.worksheets.add("任务汇总");
const assumptions = workbook.worksheets.add("假设与常数");
const targetsSheet = workbook.worksheets.add("目标参数");
const legsSheet = workbook.worksheets.add("分段转移");
const deorbitSheet = workbook.worksheets.add("离轨计算");
const capability = workbook.worksheets.add("能力计算");
const sensitivity = workbook.worksheets.add("敏感性分析");
const sources = workbook.worksheets.add("来源与边界");

const palette = {
  navy: "#17365D",
  blue: "#D9EAF7",
  teal: "#DDEBF7",
  pale: "#F3F6F9",
  yellow: "#FFF2CC",
  green: "#E2F0D9",
  border: "#B8C4CE",
  white: "#FFFFFF",
  dark: "#1F2937",
  muted: "#5B6573",
};

function utcText(value) {
  return String(value)
    .replace("T", " ")
    .replace(/\.\d+(?=\+|Z|$)/, "")
    .replace("+00:00", " UTC")
    .replace("Z", " UTC");
}

function setTitle(sheet, range, text) {
  sheet.mergeCells(range);
  const cell = range.split(":")[0];
  sheet.getRange(cell).values = [[text]];
  sheet.getRange(range).format = {
    fill: palette.navy,
    font: { bold: true, color: palette.white },
    horizontalAlignment: "left",
    verticalAlignment: "center",
  };
  sheet.getRange(range).format.rowHeight = 30;
}

function setSubtitle(sheet, range, text) {
  sheet.mergeCells(range);
  const cell = range.split(":")[0];
  sheet.getRange(cell).values = [[text]];
  sheet.getRange(range).format = {
    fill: palette.pale,
    font: { color: palette.muted },
    wrapText: true,
    verticalAlignment: "center",
  };
  sheet.getRange(range).format.rowHeight = 32;
}

function styleHeader(sheet, range) {
  sheet.getRange(range).format = {
    fill: palette.navy,
    font: { bold: true, color: palette.white },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "inside", style: "thin", color: palette.border },
  };
}

function styleSection(sheet, range) {
  sheet.getRange(range).format = {
    fill: palette.blue,
    font: { bold: true, color: palette.dark },
    borders: { preset: "outside", style: "thin", color: palette.border },
  };
}

function styleBody(sheet, range) {
  sheet.getRange(range).format = {
    verticalAlignment: "center",
    wrapText: true,
    borders: {
      insideHorizontal: { style: "thin", color: palette.border },
      bottom: { style: "thin", color: palette.border },
    },
  };
}

function setColumnWidths(sheet, widths) {
  widths.forEach(([column, width]) => {
    sheet.getRange(`${column}:${column}`).format.columnWidth = width;
  });
}

for (const sheet of [summary, assumptions, targetsSheet, legsSheet, deorbitSheet, capability, sensitivity, sources]) {
  sheet.showGridLines = false;
}

// 1. Assumptions and constants
setTitle(assumptions, "A1:E1", "假设与常数（黄色单元格为可修改输入）");
setSubtitle(
  assumptions,
  "A2:E2",
  `公开数据获取：${result.retrieved_utc}；共同历元：${result.model.common_epoch}`,
);
assumptions.getRange("A4:E4").values = [["参数", "符号", "数值", "单位", "性质/依据"]];
styleHeader(assumptions, "A4:E4");
assumptions.getRange("A5:E17").values = [
  ["地球标准引力参数", "μ", 398600.4418, "km³/s²", "物理常数"],
  ["地球赤道半径", "Rₑ", 6378.137, "km", "物理常数"],
  ["离轨后目标近地点高度", "hₚ,new", 100, "km", "处置目标假设"],
  ["每个目标交会/抓取/收纳停留", "t_dwell", 2, "day/target", "规划假设（非目录数据）"],
  ["首目标获取时间", "t_acq", 90, "day", "规划假设（非目录数据）"],
  ["首目标获取 Δv", "Δv_acq", 30, "m/s", "规划假设（非目录数据）"],
  ["末段处置操作时间", "t_disp", 7, "day", "规划假设（非目录数据）"],
  ["每目标近距离操作 Δv", "Δv_RPO", 5, "m/s/target", "规划假设（非目录数据）"],
  ["Δv 设计余量", "f_res", 0.2, "比例", "规划假设（非目录数据）"],
  ["单目标条件成功率", "q", 0.75, "概率", "能力敏感性假设"],
  ["最终处置成功率", "p_disp", 0.99, "概率", "能力敏感性假设"],
  ["单次相位机动速度增量上限", "Δv_phase,max", 10, "m/s/burn", "基准路线约束"],
  ["任务目标数", "N", 5, "target", "本场景定义"],
];
styleBody(assumptions, "A5:E17");
assumptions.getRange("C5:C17").format.fill = palette.yellow;
assumptions.getRange("C5:C12").format.numberFormat = "0.00";
assumptions.getRange("C13:C15").format.numberFormat = "0.0%";
assumptions.getRange("C16:C17").format.numberFormat = "0.00";
assumptions.freezePanes.freezeRows(4);
setColumnWidths(assumptions, [["A", 31], ["B", 17], ["C", 14], ["D", 16], ["E", 34]]);

// 2. Target table
setTitle(targetsSheet, "A1:R1", "五个约 10 cm 目标的公开轨道参数");
setSubtitle(
  targetsSheet,
  "A2:R2",
  "目标按最小 Δv 定时路线排序；轨道要素由公开 OMM 经 SGP4 对齐至共同历元。等效直径由 RCS 圆面积代理计算，不等于实测几何尺寸。",
);
targetsSheet.getRange("A4:R4").values = [[
  "顺序", "NORAD", "国际编号", "名称", "近地点\nkm", "远地点\nkm", "半长轴\nkm", "偏心率", "倾角\ndeg",
  "RAAN\ndeg", "近地点幅角\ndeg", "平近点角\ndeg", "平均运动\nrev/day", "周期\nmin", "RCS\nm²", "等效直径\ncm", "历元时效\nday", "共同历元",
]];
styleHeader(targetsSheet, "A4:R4");
const route = result.timed_route_minimum_dv.route;
const targetsByNorad = new Map(result.selected_targets.map((target) => [target.norad, target]));
const orderedTargets = route.map((norad) => targetsByNorad.get(norad));
targetsSheet.getRange("A5:R9").values = orderedTargets.map((target, index) => [
  index + 1,
  String(target.norad),
  target.object_id,
  target.name,
  target.perigee_km,
  target.apogee_km,
  target.a_km,
  target.e,
  target.inc_deg,
  target.raan_deg,
  target.argp_deg,
  target.mean_anomaly_deg,
  target.mean_motion_rev_day,
  null,
  target.rcs_m2,
  null,
  target.epoch_age_days,
  utcText(result.model.common_epoch),
]);
for (let row = 5; row <= 9; row += 1) {
  targetsSheet.getRange(`N${row}`).formulas = [[`=1440/M${row}`]];
  targetsSheet.getRange(`P${row}`).formulas = [[`=2*SQRT(O${row}/PI())*100`]];
}
styleBody(targetsSheet, "A5:R9");
targetsSheet.getRange("N5:N9").format.fill = palette.teal;
targetsSheet.getRange("P5:P9").format.fill = palette.teal;
targetsSheet.getRange("E5:G9").format.numberFormat = "0.000";
targetsSheet.getRange("H5:H9").format.numberFormat = "0.000000";
targetsSheet.getRange("I5:M9").format.numberFormat = "0.000000";
targetsSheet.getRange("N5:N9").format.numberFormat = "0.000";
targetsSheet.getRange("O5:Q9").format.numberFormat = "0.0000";
targetsSheet.freezePanes.freezeRows(4);
targetsSheet.freezePanes.freezeColumns(4);
setColumnWidths(targetsSheet, [
  ["A", 8], ["B", 11], ["C", 17], ["D", 20], ["E", 11], ["F", 11], ["G", 13], ["H", 12], ["I", 12],
  ["J", 13], ["K", 16], ["L", 15], ["M", 15], ["N", 12], ["O", 11], ["P", 13], ["Q", 13], ["R", 28],
]);

// 3. Timed transfer legs
setTitle(legsSheet, "A1:R1", "目标间定时转移计算");
setSubtitle(
  legsSheet,
  "方法：SGP4 互轨道面交点搜索 + 等效圆轨道霍曼/轨道面合并机动 + 单次不超过 10 m/s 的相位机动。",
);
legsSheet.getRange("A4:R4").values = [[
  "段", "起点", "终点", "开始 UTC", "转移出发 UTC", "进入目标轨道 UTC", "交会 UTC", "节点等待\nh", "霍曼飞行\nmin",
  "相位角\ndeg", "相位方向", "相位圈数", "相位时间\nday", "轨道面夹角\ndeg", "几何 Δv\nm/s", "相位 Δv\nm/s", "分段 Δv\nm/s", "分段历时\nday",
]];
styleHeader(legsSheet, "A4:R4");
const timedLegs = result.timed_route_minimum_dv.legs;
legsSheet.getRange("A5:R8").values = timedLegs.map((leg, index) => [
  index + 1,
  String(leg.from),
  String(leg.to),
  utcText(leg.start_utc),
  utcText(leg.departure_utc),
  utcText(leg.arrival_orbit_utc),
  utcText(leg.rendezvous_utc),
  leg.node_wait_hours,
  leg.hohmann_tof_min,
  leg.phase_angle_deg,
  leg.phase_direction === "lower" ? "低轨相位" : "高轨相位",
  leg.phase_orbits,
  leg.phase_duration_days,
  leg.plane_angle_deg,
  leg.geometry_dv_mps,
  leg.phasing_dv_mps,
  null,
  null,
]);
for (let row = 5; row <= 8; row += 1) {
  legsSheet.getRange(`Q${row}`).formulas = [[`=O${row}+P${row}`]];
  legsSheet.getRange(`R${row}`).formulas = [[`=H${row}/24+I${row}/1440+M${row}`]];
}
legsSheet.getRange("A10:R10").values = [["四段机动小计", null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null]];
legsSheet.getRange("O10").formulas = [["=SUM(O5:O8)"]];
legsSheet.getRange("P10").formulas = [["=SUM(P5:P8)"]];
legsSheet.getRange("Q10").formulas = [["=SUM(Q5:Q8)"]];
legsSheet.getRange("R10").formulas = [["=SUM(R5:R8)"]];
legsSheet.getRange("A11:R11").values = [["五个目标停留时间", null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null]];
legsSheet.getRange("R11").formulas = [["='假设与常数'!$C$8*'假设与常数'!$C$17"]];
legsSheet.getRange("A12:R12").values = [["目标间阶段合计", null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null]];
legsSheet.getRange("Q12").formulas = [["=Q10"]];
legsSheet.getRange("R12").formulas = [["=R10+R11"]];
styleBody(legsSheet, "A5:R12");
styleSection(legsSheet, "A10:R12");
legsSheet.getRange("Q5:R8").format.fill = palette.teal;
legsSheet.getRange("H5:J8").format.numberFormat = "0.000";
legsSheet.getRange("M5:R12").format.numberFormat = "0.000";
legsSheet.freezePanes.freezeRows(4);
legsSheet.freezePanes.freezeColumns(3);
setColumnWidths(legsSheet, [
  ["A", 8], ["B", 11], ["C", 11], ["D", 27], ["E", 27], ["F", 27], ["G", 27], ["H", 12], ["I", 13],
  ["J", 13], ["K", 13], ["L", 11], ["M", 13], ["N", 15], ["O", 13], ["P", 13], ["Q", 13], ["R", 13],
]);

// 4. Last-target deorbit
setTitle(deorbitSheet, "A1:D1", "末目标离轨机动计算");
setSubtitle(deorbitSheet, "A2:D2", "在末目标 31150 的远地点实施逆行脉冲，将新轨道近地点降至 100 km。采用二体瞬时脉冲模型。");
deorbitSheet.getRange("A4:D4").values = [["参数", "数值/公式", "单位", "计算说明"]];
styleHeader(deorbitSheet, "A4:D4");
deorbitSheet.getRange("A5:D17").values = [
  ["末目标 NORAD", "31150", "—", "最小 Δv 路线的第 5 个目标"],
  ["原轨道半长轴 a₀", null, "km", "来自目标参数表"],
  ["原轨道偏心率 e₀", null, "—", "来自目标参数表"],
  ["地球半径 Rₑ", null, "km", "常数"],
  ["新近地点高度 hₚ,new", null, "km", "任务处置假设"],
  ["远地点半径 rₐ", null, "km", "a₀(1+e₀)"],
  ["点火高度", null, "km", "rₐ−Rₑ"],
  ["新近地点半径 rₚ,new", null, "km", "Rₑ+hₚ,new"],
  ["转移轨道半长轴 aₜ", null, "km", "(rₐ+rₚ,new)/2"],
  ["点火前远地点速度", null, "km/s", "√[μ(2/rₐ−1/a₀)]"],
  ["点火后远地点速度", null, "km/s", "√[μ(2/rₐ−1/aₜ)]"],
  ["离轨脉冲 Δv", null, "m/s", "(v_before−v_after)×1000"],
  ["至新近地点滑行时间", null, "min", "π√(aₜ³/μ)/60"],
];
deorbitSheet.getRange("B6").formulas = [["='目标参数'!G9"]];
deorbitSheet.getRange("B7").formulas = [["='目标参数'!H9"]];
deorbitSheet.getRange("B8").formulas = [["='假设与常数'!C6"]];
deorbitSheet.getRange("B9").formulas = [["='假设与常数'!C7"]];
deorbitSheet.getRange("B10").formulas = [["=B6*(1+B7)"]];
deorbitSheet.getRange("B11").formulas = [["=B10-B8"]];
deorbitSheet.getRange("B12").formulas = [["=B8+B9"]];
deorbitSheet.getRange("B13").formulas = [["=(B10+B12)/2"]];
deorbitSheet.getRange("B14").formulas = [["=SQRT('假设与常数'!C5*(2/B10-1/B6))"]];
deorbitSheet.getRange("B15").formulas = [["=SQRT('假设与常数'!C5*(2/B10-1/B13))"]];
deorbitSheet.getRange("B16").formulas = [["=(B14-B15)*1000"]];
deorbitSheet.getRange("B17").formulas = [["=PI()*SQRT(B13^3/'假设与常数'!C5)/60"]];
styleBody(deorbitSheet, "A5:D17");
deorbitSheet.getRange("B6:B17").format.fill = palette.teal;
deorbitSheet.getRange("B6:B17").format.numberFormat = "0.000000";
deorbitSheet.getRange("B16:B17").format.numberFormat = "0.000";
deorbitSheet.freezePanes.freezeRows(4);
setColumnWidths(deorbitSheet, [["A", 31], ["B", 20], ["C", 12], ["D", 42]]);

// 5. Mission capability calculation
setTitle(capability, "A1:D1", "任务周期、Δv 与有效清理能力");
setSubtitle(capability, "A2:D2", "蓝色单元格为公式结果；所有规划假设集中在“假设与常数”表中，可修改后自动重算。");
capability.getRange("A4:D4").values = [["指标", "计算结果", "单位", "公式/含义"]];
styleHeader(capability, "A4:D4");
capability.getRange("A5:D12").values = [
  ["目标数", null, "target", "N"],
  ["目标间转移 Δv", null, "m/s", "四段几何与相位机动之和"],
  ["首目标获取 Δv", null, "m/s", "规划假设"],
  ["近距离操作 Δv 合计", null, "m/s", "N×Δv_RPO"],
  ["末目标离轨 Δv", null, "m/s", "远地点逆行脉冲"],
  ["余量前总 Δv", null, "m/s", "转移+获取+RPO+离轨"],
  ["设计余量", null, "比例", "f_res"],
  ["设计总 Δv", null, "m/s", "余量前总量×(1+f_res)"],
];
capability.getRange("B5").formulas = [["='假设与常数'!C17"]];
capability.getRange("B6").formulas = [["='分段转移'!Q12"]];
capability.getRange("B7").formulas = [["='假设与常数'!C10"]];
capability.getRange("B8").formulas = [["=B5*'假设与常数'!C12"]];
capability.getRange("B9").formulas = [["='离轨计算'!B16"]];
capability.getRange("B10").formulas = [["=SUM(B6:B9)"]];
capability.getRange("B11").formulas = [["='假设与常数'!C13"]];
capability.getRange("B12").formulas = [["=B10*(1+B11)"]];

capability.getRange("A14:D14").values = [["周期与清理率", null, null, null]];
styleSection(capability, "A14:D14");
capability.getRange("A15:D25").values = [
  ["首目标获取时间", null, "day", "t_acq"],
  ["目标间阶段时间", null, "day", "含 5 次停留"],
  ["最终处置操作时间", null, "day", "t_disp"],
  ["任务总周期", null, "day", "获取+目标间阶段+处置"],
  ["名义目标数", null, "target", "N"],
  ["名义清理率", null, "target/year", "N×365/任务总周期"],
  ["安全失败后继续：期望有效目标数", null, "target", "N×q×p_disp"],
  ["安全失败后继续：有效清理率", null, "target/year", "期望有效目标数×365/任务总周期"],
  ["任一失败即终止：期望有效目标数", null, "target", "p_disp×Σ(qᵏ), k=1…N"],
  ["任一失败即终止：有效清理率", null, "target/year", "期望有效目标数×365/任务总周期"],
  ["基准路线", "36668 → 30741 → 35089 → 35175 → 31150", "—", "最小 Δv 定时路线"],
];
capability.getRange("B15").formulas = [["='假设与常数'!C9"]];
capability.getRange("B16").formulas = [["='分段转移'!R12"]];
capability.getRange("B17").formulas = [["='假设与常数'!C11"]];
capability.getRange("B18").formulas = [["=SUM(B15:B17)"]];
capability.getRange("B19").formulas = [["=B5"]];
capability.getRange("B20").formulas = [["=B19*365/B18"]];
capability.getRange("B21").formulas = [["=B19*'假设与常数'!C14*'假设与常数'!C15"]];
capability.getRange("B22").formulas = [["=B21*365/B18"]];
capability.getRange("B23").formulas = [["='假设与常数'!C15*SUM('假设与常数'!C14^1,'假设与常数'!C14^2,'假设与常数'!C14^3,'假设与常数'!C14^4,'假设与常数'!C14^5)"]];
capability.getRange("B24").formulas = [["=B23*365/B18"]];
styleBody(capability, "A5:D25");
capability.getRange("B5:B24").format.fill = palette.teal;
capability.getRange("B5:B24").format.numberFormat = "0.000";
capability.getRange("B11").format.numberFormat = "0.0%";
capability.getRange("B25").format.numberFormat = "@";
capability.freezePanes.freezeRows(4);
setColumnWidths(capability, [["A", 42], ["B", 45], ["C", 16], ["D", 46]]);

// 6. Sensitivity tables
setTitle(sensitivity, "A1:F1", "关键假设敏感性");
setSubtitle(sensitivity, "A2:F2", "相位机动部分为外部定时路线模型输出；日历、概率和质量代理部分使用表内公式自动重算。");
sensitivity.getRange("A4:D4").values = [["单次相位机动上限 m/s", "目标间 Δv m/s", "目标间历时 day", "路线"]];
styleHeader(sensitivity, "A4:D4");
const phaseCases = result.mission_metrics.phase_burn_sensitivity;
sensitivity.getRange("A5:D7").values = ["5.0", "10.0", "20.0"].map((key) => [
  Number(key),
  phaseCases[key].inter_target_dv_mps,
  phaseCases[key].inter_target_elapsed_days,
  phaseCases[key].route.join(" → "),
]);
styleBody(sensitivity, "A5:D7");
sensitivity.getRange("A5:C7").format.numberFormat = "0.000";

sensitivity.getRange("A10:F10").values = [["日历情景", "首目标获取 day", "末段处置 day", "总周期 day", "名义率 target/year", "继续型有效率 target/year"]];
styleHeader(sensitivity, "A10:F10");
sensitivity.getRange("A11:F13").values = [
  ["成熟乐观", 30, 3, null, null, null],
  ["基准", 90, 7, null, null, null],
  ["演示保守", 180, 14, null, null, null],
];
for (let row = 11; row <= 13; row += 1) {
  sensitivity.getRange(`D${row}`).formulas = [[`=B${row}+'分段转移'!R12+C${row}`]];
  sensitivity.getRange(`E${row}`).formulas = [[`='能力计算'!B19*365/D${row}`]];
  sensitivity.getRange(`F${row}`).formulas = [[`='能力计算'!B21*365/D${row}`]];
}
styleBody(sensitivity, "A11:F13");
sensitivity.getRange("D11:F13").format.fill = palette.teal;
sensitivity.getRange("B11:F13").format.numberFormat = "0.000";

sensitivity.getRange("A16:D16").values = [["单目标成功率 q", "处置成功率 p_disp", "继续型期望目标数", "终止型期望目标数"]];
styleHeader(sensitivity, "A16:D16");
const probabilityCases = [[0.6, 0.9], [0.6, 0.99], [0.75, 0.9], [0.75, 0.99], [0.9, 0.9], [0.9, 0.99]];
sensitivity.getRange("A17:D22").values = probabilityCases.map(([q, p]) => [q, p, null, null]);
for (let row = 17; row <= 22; row += 1) {
  sensitivity.getRange(`C${row}`).formulas = [[`='假设与常数'!C17*A${row}*B${row}`]];
  sensitivity.getRange(`D${row}`).formulas = [[`=B${row}*SUM(A${row}^1,A${row}^2,A${row}^3,A${row}^4,A${row}^5)`]];
}
styleBody(sensitivity, "A17:D22");
sensitivity.getRange("A17:B22").format.numberFormat = "0.0%";
sensitivity.getRange("C17:D22").format.numberFormat = "0.000";
sensitivity.getRange("C17:D22").format.fill = palette.teal;

sensitivity.getRange("A25:D25").values = [["球体代理密度 g/cm³", "名义清理质量 kg", "继续型有效质量 kg", "终止型有效质量 kg"]];
styleHeader(sensitivity, "A25:D25");
sensitivity.getRange("A26:D28").values = [[1.4, null, null, null], [2.8, null, null, null], [7.9, null, null, null]];
for (let row = 26; row <= 28; row += 1) {
  const massTerm = `4/3*PI()*A${row}/1000`;
  const volumeSum = "SUM(('目标参数'!P5/2)^3,('目标参数'!P6/2)^3,('目标参数'!P7/2)^3,('目标参数'!P8/2)^3,('目标参数'!P9/2)^3)";
  const abortMass = `SUM(('目标参数'!P5/2)^3*'假设与常数'!C14^1,('目标参数'!P6/2)^3*'假设与常数'!C14^2,('目标参数'!P7/2)^3*'假设与常数'!C14^3,('目标参数'!P8/2)^3*'假设与常数'!C14^4,('目标参数'!P9/2)^3*'假设与常数'!C14^5)`;
  sensitivity.getRange(`B${row}`).formulas = [[`=${massTerm}*${volumeSum}`]];
  sensitivity.getRange(`C${row}`).formulas = [[`=B${row}*'假设与常数'!C14*'假设与常数'!C15`]];
  sensitivity.getRange(`D${row}`).formulas = [[`=${massTerm}*'假设与常数'!C15*${abortMass}`]];
}
styleBody(sensitivity, "A26:D28");
sensitivity.getRange("B26:D28").format.fill = palette.teal;
sensitivity.getRange("A26:D28").format.numberFormat = "0.000";
sensitivity.getRange("A30:D30").values = [["说明", "RCS 等效圆直径被进一步假设为实心球直径；仅用于质量量级敏感性，不是目录质量。", null, null]];
sensitivity.mergeCells("B30:D30");
sensitivity.getRange("A30:D30").format = { fill: palette.pale, wrapText: true, font: { color: palette.muted } };
sensitivity.freezePanes.freezeRows(4);
setColumnWidths(sensitivity, [["A", 29], ["B", 25], ["C", 25], ["D", 31], ["E", 25], ["F", 28]]);

// 7. Sources and model boundaries
setTitle(sources, "A1:D1", "公开数据来源与模型边界");
setSubtitle(sources, "A2:D2", "本表将公开目录量、模型计算量和规划假设分开，避免把任务假设误认为公开测量数据。");
sources.getRange("A4:D4").values = [["来源", "地址/文件", "获取时间", "用途"]];
styleHeader(sources, "A4:D4");
sources.getRange("A5:D7").values = [
  ["CelesTrak GP/OMM", "https://celestrak.org/NORAD/elements/gp.php?GROUP=FENGYUN-1C-DEBRIS&FORMAT=JSON", utcText(result.retrieved_utc), "轨道根数与 SGP4 传播输入"],
  ["CelesTrak SATCAT", "https://celestrak.org/satcat/records.php?NAME=FENGYUN%201C%20DEB&FORMAT=JSON&ONORBIT=1", utcText(result.retrieved_utc), "RCS 与目标标识"],
  ["本地计算结果", "public_debris_calculation/screening_result.json", utcText(result.retrieved_utc), "筛选、路线、时序和能力计算结果"],
];
styleBody(sources, "A5:D7");
sources.getRange("A10:C10").values = [["类别", "内容", "影响"]];
styleHeader(sources, "A10:C10");
sources.getRange("A11:C16").values = [
  ["目标筛选", "FENGYUN 1C DEB；RCS 等效直径 8–12 cm；近地点≥700 km；远地点≤900 km；e≤0.02；根数时效≤3 day", "决定候选集与所选 5 目标"],
  ["轨道模型", "SGP4/OMM 对齐至共同历元，TEME 状态", "适合规划级比较，不替代精密定轨"],
  ["转移模型", "等效圆轨道双脉冲霍曼；完整轨道面变化并入高半径脉冲", "不是原偏心轨道间全局最优解"],
  ["时序模型", "互轨道面交点搜索；≤10 m/s/次相位机动；每目标停留 2 day", "给出规划级任务时间"],
  ["未计入", "有限推力、精密协方差、姿态/翻滚、接触动力学、照明通信、地面网与窗口约束", "工程任务周期和 Δv 可能增加"],
  ["尺寸与质量", "RCS 圆面积等效直径；球体密度代理质量", "只用于 10 cm 量级筛选与敏感性"],
];
styleBody(sources, "A11:C16");
sources.freezePanes.freezeRows(4);
setColumnWidths(sources, [["A", 24], ["B", 82], ["C", 31], ["D", 38]]);

// 8. Executive summary and calculation-process table
setTitle(summary, "A1:F1", "10 cm 级空间碎片清理能力——计算过程汇总表");
setSubtitle(
  summary,
  "A2:F2",
  "典型场景：5 个风云一号 C 碎片，约 8–12 cm，约 780–880 km 太阳同步轨道带。结果为规划级基准，不替代任务级精密分析。",
);
summary.getRange("A4:D4").values = [["核心指标", "基准值", "单位", "口径"]];
styleHeader(summary, "A4:D4");
summary.getRange("A5:D12").values = [
  ["目标间转移 Δv", null, "m/s", "四段转移+相位机动"],
  ["离轨脉冲 Δv", null, "m/s", "末目标远地点点火至 100 km 近地点"],
  ["余量前总 Δv", null, "m/s", "含首目标获取和每目标 RPO"],
  ["设计总 Δv", null, "m/s", "含 20% 余量"],
  ["任务总周期", null, "day", "90 day 获取+目标间阶段+7 day 处置"],
  ["名义清理率", null, "target/year", "5 个目标全部成功"],
  ["继续型有效清理率", null, "target/year", "q=75%，p_disp=99%"],
  ["终止型有效清理率", null, "target/year", "任一失败即终止"],
];
summary.getRange("B5").formulas = [["='能力计算'!B6"]];
summary.getRange("B6").formulas = [["='能力计算'!B9"]];
summary.getRange("B7").formulas = [["='能力计算'!B10"]];
summary.getRange("B8").formulas = [["='能力计算'!B12"]];
summary.getRange("B9").formulas = [["='能力计算'!B18"]];
summary.getRange("B10").formulas = [["='能力计算'!B20"]];
summary.getRange("B11").formulas = [["='能力计算'!B22"]];
summary.getRange("B12").formulas = [["='能力计算'!B24"]];
styleBody(summary, "A5:D12");
summary.getRange("B5:B12").format.fill = palette.green;
summary.getRange("B5:B12").format.numberFormat = "0.00";

summary.getRange("A15:F15").values = [["步骤", "输入", "计算方法", "输出", "单位", "数据性质"]];
styleHeader(summary, "A15:F15");
summary.getRange("A16:F23").values = [
  ["1 目标筛选", "公开 GP + SATCAT", "8–12 cm；700–900 km；e≤0.02；时效≤3 day", 145, "eligible targets", "公开目录筛选"],
  ["2 选取代表目标", "145 个候选", "近邻图 + 深度 5 穷举路径", 5, "targets", "模型选择"],
  ["3 共同时刻对齐", "公开 OMM", "SGP4 传播至 2026-09-01 23:06:52 UTC", 5, "TEME states", "轨道模型"],
  ["4 定时路线", "5 个状态与轨道面", "120 条排列逐一仿真，按 Δv 最小排序", "36668→30741→35089→35175→31150", "route", "模型计算"],
  ["5 分段机动", "交点等待+霍曼+相位", "Δv_leg=Δv_geometry+Δv_phase", null, "m/s", "模型计算"],
  ["6 目标间历时", "4 段历时+5 次停留", "Σt_leg+N×2 day", null, "day", "模型+规划假设"],
  ["7 末目标离轨", "a₀、e₀、100 km 近地点", "远地点二体逆行脉冲", null, "m/s", "二体模型"],
  ["8 能力指标", "Δv、任务周期、成功率", "目标数×365/周期；有效数按两种失败策略", null, "target/year", "规划级能力"],
];
summary.getRange("D20").formulas = [["='能力计算'!B6"]];
summary.getRange("D21").formulas = [["='能力计算'!B16"]];
summary.getRange("D22").formulas = [["='能力计算'!B9"]];
summary.getRange("D23").formulas = [["='能力计算'!B22"]];
styleBody(summary, "A16:F23");
summary.getRange("D20:D23").format.fill = palette.teal;
summary.getRange("D20:D23").format.numberFormat = "0.000";
summary.freezePanes.freezeRows(4);
setColumnWidths(summary, [["A", 25], ["B", 31], ["C", 48], ["D", 37], ["E", 18], ["F", 24]]);

// Compact verification and visual previews
const summaryCheck = await workbook.inspect({
  kind: "table",
  range: "任务汇总!A1:F23",
  include: "values,formulas",
  tableMaxRows: 24,
  tableMaxCols: 6,
  maxChars: 10000,
});
console.log(summaryCheck.ndjson);

const formulaErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log(formulaErrors.ndjson);

const previewRanges = [
  ["任务汇总", "A1:F23"],
  ["假设与常数", "A1:E17"],
  ["目标参数", "A1:R9"],
  ["分段转移", "A1:R12"],
  ["离轨计算", "A1:D17"],
  ["能力计算", "A1:D25"],
  ["敏感性分析", "A1:F30"],
  ["来源与边界", "A1:D16"],
];
for (const [sheetName, range] of previewRanges) {
  const preview = await workbook.render({ sheetName, range, scale: 1.2, format: "png" });
  await fs.writeFile(
    path.join(outputDir, `preview-${sheetName}.png`),
    new Uint8Array(await preview.arrayBuffer()),
  );
}

const output = await SpreadsheetFile.exportXlsx(workbook);
const outputPath = path.join(outputDir, "空间碎片清理能力计算过程表.xlsx");
await output.save(outputPath);
console.log(`OUTPUT=${outputPath}`);
