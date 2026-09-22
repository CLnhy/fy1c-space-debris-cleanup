%% 抓取模型第二阶段：等效接触、闭合指令与抓取判据
% 这是用于方案筛选的低阶模型：接触法向力采用线性弹簧-阻尼等效，
% 成功判据由间距、相对速度和抓手闭合量共同决定。

mdl = 'capture_dynamics_v1';
workFolder = fileparts(mfilename('fullpath'));
modelFile = fullfile(workFolder, [mdl '.slx']);

if ~isfile(modelFile)
    error('未找到 %s，请先运行 build_capture_dynamics_v1.m。', modelFile);
end

load_system(modelFile);
open_system(mdl);
set_param(mdl, 'StopTime', '5');

% 双指滑块的机械限位与等效柔顺性：后续将由位置控制器替换为真实驱动。
for jointName = {'Left Finger Slide', 'Right Finger Slide'}
    jointPath = [mdl '/' jointName{1}];
    set_param(jointPath, 'LowerLimitSpecify', 'on', 'LowerLimitBound', '-0.15', ...
        'UpperLimitSpecify', 'on', 'UpperLimitBound', '0.15', ...
        'SpringStiffness', '100', 'DampingCoefficient', '5');
end

buildContactModel([mdl '/Phase 2 Contact Model']);
buildSuccessLogic([mdl '/Phase 3 Success Logic']);
buildMonteCarloInputs([mdl '/Monte Carlo Inputs']);

set_param(mdl, 'Description', [ ...
    '空间碎片抓取初步动力学模型。阶段 2：线性弹簧-阻尼等效接触；' ...
    '阶段 3：闭合量、间距和相对速度的抓取候选判据；阶段 4：蒙特卡洛参数入口。']);

save_system(mdl, modelFile);
set_param(mdl, 'SimulationCommand', 'update');
save_system(mdl, modelFile);
open_system([mdl '/Phase 3 Success Logic']);

function buildContactModel(sys)
clearSubsystem(sys);
add_block('simulink/Sources/Constant', [sys '/Penetration test [m]'], ...
    'Position', [25 55 110 85], 'Value', '0.002');
add_block('simulink/Math Operations/Gain', [sys '/Normal stiffness 1500 N per m'], ...
    'Position', [155 50 250 90], 'Gain', '1500');
add_block('simulink/Sources/Constant', [sys '/Approach speed [m per s]'], ...
    'Position', [25 130 110 160], 'Value', '0.01');
add_block('simulink/Math Operations/Gain', [sys '/Damping 15 N per mps'], ...
    'Position', [155 125 250 165], 'Gain', '15');
add_block('simulink/Math Operations/Sum', [sys '/Equivalent normal force'], ...
    'Position', [310 75 340 135], 'Inputs', '++');
add_block('simulink/Sinks/Display', [sys '/Normal force [N]'], ...
    'Position', [410 92 475 123]);
add_line(sys, 'Penetration test [m]/1', 'Normal stiffness 1500 N per m/1');
add_line(sys, 'Approach speed [m per s]/1', 'Damping 15 N per mps/1');
add_line(sys, 'Normal stiffness 1500 N per m/1', 'Equivalent normal force/1');
add_line(sys, 'Damping 15 N per mps/1', 'Equivalent normal force/2');
add_line(sys, 'Equivalent normal force/1', 'Normal force [N]/1');
end

function buildSuccessLogic(sys)
clearSubsystem(sys);
add_block('simulink/Sources/Step', [sys '/Closing command [m]'], ...
    'Position', [25 40 80 70], 'Time', '1', 'Before', '0', 'After', '0.07');
add_block('simulink/Logic and Bit Operations/Compare To Constant', [sys '/Closure at least 0.06 m'], ...
    'Position', [140 38 245 72], 'relop', '>=', 'const', '0.06');
add_block('simulink/Sources/Constant', [sys '/Range [m]'], ...
    'Position', [25 110 80 140], 'Value', '0.09');
add_block('simulink/Logic and Bit Operations/Compare To Constant', [sys '/Range at most 0.11 m'], ...
    'Position', [140 108 245 142], 'relop', '<=', 'const', '0.11');
add_block('simulink/Sources/Constant', [sys '/Relative speed [m per s]'], ...
    'Position', [25 180 80 210], 'Value', '0.02');
add_block('simulink/Logic and Bit Operations/Compare To Constant', [sys '/Speed at most 0.05 mps'], ...
    'Position', [140 178 245 212], 'relop', '<=', 'const', '0.05');
add_block('simulink/Logic and Bit Operations/Logical Operator', [sys '/All capture conditions'], ...
    'Position', [300 95 350 155], 'Operator', 'AND', 'Inputs', '3');
add_block('simulink/Sinks/Display', [sys '/Capture candidate'], ...
    'Position', [420 110 490 142]);
add_line(sys, 'Closing command [m]/1', 'Closure at least 0.06 m/1');
add_line(sys, 'Range [m]/1', 'Range at most 0.11 m/1');
add_line(sys, 'Relative speed [m per s]/1', 'Speed at most 0.05 mps/1');
add_line(sys, 'Closure at least 0.06 m/1', 'All capture conditions/1');
add_line(sys, 'Range at most 0.11 m/1', 'All capture conditions/2');
add_line(sys, 'Speed at most 0.05 mps/1', 'All capture conditions/3');
add_line(sys, 'All capture conditions/1', 'Capture candidate/1');
end

function buildMonteCarloInputs(sys)
clearSubsystem(sys);
add_block('simulink/Sources/Constant', [sys '/Range sigma [m]'], ...
    'Position', [25 40 100 70], 'Value', '0.02');
add_block('simulink/Sources/Constant', [sys '/Speed sigma [m per s]'], ...
    'Position', [25 100 100 130], 'Value', '0.01');
add_block('simulink/Sources/Constant', [sys '/Attitude sigma [deg]'], ...
    'Position', [25 160 100 190], 'Value', '15');
add_block('simulink/Signal Routing/Mux', [sys '/Uncertainty vector'], ...
    'Position', [165 75 190 160], 'Inputs', '3');
add_block('simulink/Sinks/Display', [sys '/Monte Carlo parameters'], ...
    'Position', [260 100 355 135]);
add_line(sys, 'Range sigma [m]/1', 'Uncertainty vector/1');
add_line(sys, 'Speed sigma [m per s]/1', 'Uncertainty vector/2');
add_line(sys, 'Attitude sigma [deg]/1', 'Uncertainty vector/3');
add_line(sys, 'Uncertainty vector/1', 'Monte Carlo parameters/1');
end

function clearSubsystem(sys)
allLines = find_system(sys, 'FindAll', 'on', 'Type', 'line');
if ~isempty(allLines)
    delete_line(allLines);
end
allBlocks = find_system(sys, 'SearchDepth', 1, 'Type', 'Block');
for k = 1:numel(allBlocks)
    if ~strcmp(allBlocks{k}, sys)
        delete_block(allBlocks{k});
    end
end
end
