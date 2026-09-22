%% 抓取模型第三阶段：Spatial Contact Force 与可记录接触测量
% 每根手指与 10 cm 目标分别建立一个真实的 Simscape Multibody 接触对。
% 目标初始位置仍设置为分离状态；后续加入接近机动后，接触会自动产生力。

mdl = 'capture_dynamics_v1';
workFolder = fileparts(mfilename('fullpath'));
modelFile = fullfile(workFolder, [mdl '.slx']);
if ~isfile(modelFile)
    error('未找到 %s，请先运行前两个建模脚本。', modelFile);
end

load_system(modelFile);
open_system(mdl);

% 导出三处实体的凸包几何，供 Spatial Contact Force 使用。
set_param([mdl '/Left Finger'], 'ExportEntireGeometry', 'on');
set_param([mdl '/Right Finger'], 'ExportEntireGeometry', 'on');
set_param([mdl '/Target Debris 10cm'], 'ExportEntireGeometry', 'on');

% 删除本阶段曾经中断时遗留的测试块，确保可重复执行。
deleteIfPresent(mdl, {'Left Finger Contact', 'Right Finger Contact', 'Test PS Converter', ...
    'Left contact status PS', 'Left separation PS', 'Left normal force PS', ...
    'Right contact status PS', 'Right separation PS', 'Right normal force PS', ...
    'LeftContactStatus', 'LeftSeparation', 'LeftNormalForce', ...
    'RightContactStatus', 'RightSeparation', 'RightNormalForce'});

addContactPair(mdl, 'Left', 'Left Finger', 'Target Debris 10cm', 315, ...
    'LeftContactStatus', 'LeftSeparation', 'LeftNormalForce');
addContactPair(mdl, 'Right', 'Right Finger', 'Target Debris 10cm', 465, ...
    'RightContactStatus', 'RightSeparation', 'RightNormalForce');

set_param(mdl, 'Description', [ ...
    '空间碎片抓取初步动力学模型。左右手指与 10 cm 目标之间使用 Spatial Contact Force；' ...
    '接触状态、分离距离和法向接触力记录为工作区变量。']);
set_param(mdl, 'StopTime', '5');
save_system(mdl, modelFile);
set_param(mdl, 'SimulationCommand', 'update');
save_system(mdl, modelFile);
open_system(mdl);

function addContactPair(mdl, side, fingerName, targetName, y, statusVar, sepVar, forceVar)
contactName = [side ' Finger Contact'];
contactPath = [mdl '/' contactName];
add_block('sm_lib/Forces and Torques/Spatial Contact Force', contactPath, ...
    'Position', [820 y 900 y+50], ...
    'NormalForceType', 'SmoothSpringDamper', ...
    'NormalStiffness', '1500', ...
    'NormalDamping', '15', ...
    'NormalTransitionRegionWidth', '0.001', ...
    'FrictionType', 'SmoothStickSlip', ...
    'CoefficientOfStaticFriction', '0.5', ...
    'CoefficientOfDynamicFriction', '0.4', ...
    'FrictionalCriticalVelocity', '0.01', ...
    'SenseContactSignal', 'on', ...
    'SenseSeparationDistance', 'on', ...
    'SenseNormalForceMagnitude', 'on');

fingerPorts = get_param([mdl '/' fingerName], 'PortHandles');
targetPorts = get_param([mdl '/' targetName], 'PortHandles');
contactPorts = get_param(contactPath, 'PortHandles');

% 实体块 LConn 为导出的几何端口；接触块的 LConn/RConn(1) 分别为 B/F 几何端口。
add_line(mdl, fingerPorts.LConn(1), contactPorts.LConn(1), 'autorouting', 'on');
add_line(mdl, targetPorts.LConn(1), contactPorts.RConn(1), 'autorouting', 'on');

addLoggedSignal(mdl, contactPorts.RConn(2), [side ' contact status PS'], 945, y-10, statusVar);
addLoggedSignal(mdl, contactPorts.RConn(3), [side ' separation PS'], 945, y+35, sepVar);
addLoggedSignal(mdl, contactPorts.RConn(4), [side ' normal force PS'], 945, y+80, forceVar);
end

function addLoggedSignal(mdl, sourcePort, converterName, x, y, variableName)
converterPath = [mdl '/' converterName];
workspacePath = [mdl '/' variableName];
add_block('nesl_utility/PS-Simulink Converter', converterPath, ...
    'Position', [x y x+75 y+30]);
add_block('simulink/Sinks/To Workspace', workspacePath, ...
    'Position', [x+120 y x+195 y+30], ...
    'VariableName', variableName, 'SaveFormat', 'Structure With Time');
converterPorts = get_param(converterPath, 'PortHandles');
workspacePorts = get_param(workspacePath, 'PortHandles');
add_line(mdl, sourcePort, converterPorts.LConn(1), 'autorouting', 'on');
add_line(mdl, converterPorts.Outport(1), workspacePorts.Inport(1), 'autorouting', 'on');
end

function deleteIfPresent(mdl, names)
for k = 1:numel(names)
    blockPath = [mdl '/' names{k}];
    if ~isempty(find_system(mdl, 'SearchDepth', 1, 'Name', names{k}))
        delete_block(blockPath);
    end
end
end
