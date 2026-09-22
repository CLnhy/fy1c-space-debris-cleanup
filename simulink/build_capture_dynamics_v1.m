%% 空间碎片抓取初步动力学模型（Simscape Multibody）
% 场景：微重力环境下，服务航天器利用双指抓手接近并抓取约 10 cm 碎片。
% 本脚本只生成可继续扩展的机构骨架；接触力、闭环控制与蒙特卡洛统计
% 将在此模型的基础上逐步加入。

mdl = 'capture_dynamics_v1';
workFolder = fileparts(mfilename('fullpath'));
modelFile = fullfile(workFolder, [mdl '.slx']);

if isfile(modelFile)
    open_system(modelFile);
    return
end

% 如果上一次生成在保存前中断，关闭本脚本创建的临时未保存模型后重建。
if bdIsLoaded(mdl)
    close_system(mdl, 0);
end

cd(workFolder);
load_system('sm_lib');

% smnew 自动放入并连接 World Frame、Mechanism Configuration 和 Solver Configuration。
smnew(mdl);
set_param(mdl, 'StopTime', '5');
set_param([mdl '/Mechanism Configuration'], 'GravityVector', '[0 0 0]');

% ---------- 服务航天器与双指抓手 ----------
add_block('sm_lib/Joints/6-DOF Joint', [mdl '/Servicer Free Motion'], ...
    'Position', [210 130 275 195]);
add_block('sm_lib/Body Elements/Brick Solid', [mdl '/Servicer Platform'], ...
    'Position', [340 130 415 195], 'BrickDimensions', '[1.2 0.8 0.35]', ...
    'Density', '300');

add_block('sm_lib/Frames and Transforms/Rigid Transform', [mdl '/Left Finger Mount'], ...
    'Position', [495 55 575 105], 'TranslationMethod', 'Cartesian', ...
    'TranslationCartesianOffset', '[0.60 0.32 0]');
add_block('sm_lib/Joints/Prismatic Joint', [mdl '/Left Finger Slide'], ...
    'Position', [655 55 720 105]);
add_block('sm_lib/Body Elements/Brick Solid', [mdl '/Left Finger'], ...
    'Position', [790 55 865 105], 'BrickDimensions', '[0.35 0.06 0.08]', ...
    'Density', '700');

add_block('sm_lib/Frames and Transforms/Rigid Transform', [mdl '/Right Finger Mount'], ...
    'Position', [495 220 575 270], 'TranslationMethod', 'Cartesian', ...
    'TranslationCartesianOffset', '[0.60 -0.32 0]');
add_block('sm_lib/Joints/Prismatic Joint', [mdl '/Right Finger Slide'], ...
    'Position', [655 220 720 270]);
add_block('sm_lib/Body Elements/Brick Solid', [mdl '/Right Finger'], ...
    'Position', [790 220 865 270], 'BrickDimensions', '[0.35 0.06 0.08]', ...
    'Density', '700');

% ---------- 非合作目标：约 10 cm 的球形等效碎片 ----------
add_block('sm_lib/Joints/6-DOF Joint', [mdl '/Target Free Motion'], ...
    'Position', [245 410 310 475]);
add_block('sm_lib/Frames and Transforms/Rigid Transform', [mdl '/Target Initial Offset'], ...
    'Position', [405 410 485 460], 'TranslationMethod', 'Cartesian', ...
    'TranslationCartesianOffset', '[1.50 0 0]');
add_block('sm_lib/Body Elements/Spherical Solid', [mdl '/Target Debris 10cm'], ...
    'Position', [590 410 665 460], 'SphereRadius', '0.05', 'Density', '2700');

% ---------- 后续扩展接口（先作为清晰的建模位置） ----------
add_block('simulink/Ports & Subsystems/Subsystem', [mdl '/Phase 2 Contact Model'], ...
    'Position', [935 80 1090 145]);
set_param([mdl '/Phase 2 Contact Model'], 'BackgroundColor', 'yellow');
add_block('simulink/Ports & Subsystems/Subsystem', [mdl '/Phase 3 Success Logic'], ...
    'Position', [935 185 1090 250]);
set_param([mdl '/Phase 3 Success Logic'], 'BackgroundColor', 'cyan');
add_block('simulink/Ports & Subsystems/Subsystem', [mdl '/Monte Carlo Inputs'], ...
    'Position', [935 290 1090 355]);
set_param([mdl '/Monte Carlo Inputs'], 'BackgroundColor', 'green');

% 把占位子系统改成无端口的结构标签，避免第一阶段仿真产生未连接端口警告。
delete_block([mdl '/Phase 2 Contact Model/In1']);
delete_block([mdl '/Phase 2 Contact Model/Out1']);
delete_block([mdl '/Phase 3 Success Logic/In1']);
delete_block([mdl '/Phase 3 Success Logic/Out1']);
delete_block([mdl '/Monte Carlo Inputs/In1']);
delete_block([mdl '/Monte Carlo Inputs/Out1']);
defaultConverter = find_system(mdl, 'SearchDepth', 1, 'Name', 'Simulink-PS Converter');
if ~isempty(defaultConverter)
    delete_block(defaultConverter{1});
end

% ---------- 机构连接 ----------
connectFrames(mdl, 'World Frame', 'RConn', 'Servicer Free Motion', 'LConn');
connectFrames(mdl, 'Servicer Free Motion', 'RConn', 'Servicer Platform', 'RConn');
connectFrames(mdl, 'Servicer Platform', 'RConn', 'Left Finger Mount', 'LConn');
connectFrames(mdl, 'Left Finger Mount', 'RConn', 'Left Finger Slide', 'LConn');
connectFrames(mdl, 'Left Finger Slide', 'RConn', 'Left Finger', 'RConn');
connectFrames(mdl, 'Servicer Platform', 'RConn', 'Right Finger Mount', 'LConn');
connectFrames(mdl, 'Right Finger Mount', 'RConn', 'Right Finger Slide', 'LConn');
connectFrames(mdl, 'Right Finger Slide', 'RConn', 'Right Finger', 'RConn');
connectFrames(mdl, 'World Frame', 'RConn', 'Target Free Motion', 'LConn');
connectFrames(mdl, 'Target Free Motion', 'RConn', 'Target Initial Offset', 'LConn');
connectFrames(mdl, 'Target Initial Offset', 'RConn', 'Target Debris 10cm', 'RConn');

set_param(mdl, 'Description', [ ...
    '空间碎片抓取初步动力学模型。微重力；服务航天器和目标均为自由漂浮体；' ...
    '目标为直径 10 cm 的球形等效碎片。Phase 2/3 将添加接触力、抓取成功判据及蒙特卡洛输入。']);

save_system(mdl, modelFile);
open_system(mdl);
set_param(mdl, 'SimulationCommand', 'update');
save_system(mdl, modelFile);

function connectFrames(mdlName, srcName, srcPortName, dstName, dstPortName)
% 使用物理保守端口句柄连线，避免图形端口编号随版本变化。
srcHandles = get_param([mdlName '/' srcName], 'PortHandles');
dstHandles = get_param([mdlName '/' dstName], 'PortHandles');
add_line(mdlName, srcHandles.(srcPortName)(1), dstHandles.(dstPortName)(1), 'autorouting', 'on');
end
