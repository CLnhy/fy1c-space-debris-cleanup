% UPGRADE_TO_THREE_FINGER_CAPTURE
% 将现有两指接触模型升级为三指对称抓取模型，并计算多指接触判据。
mdl = 'capture_dynamics_v1';
workFolder = fileparts(mfilename('fullpath'));
modelFile = fullfile(workFolder, [mdl '.slx']);
if ~isfile(modelFile)
    error('Model file not found: %s', modelFile);
end
load_system(modelFile);
open_system(mdl);

% 三指围绕 10 cm 球形碎片形成三角接触区；目标沿 -X 方向接近。
set_param([mdl '/Left Finger Mount'],  'TranslationCartesianOffset', '[0.60 0.075 0]');
set_param([mdl '/Right Finger Mount'], 'TranslationCartesianOffset', '[0.60 -0.075 0]');
set_param([mdl '/Target Initial Offset'], 'TranslationCartesianOffset', '[1.50 0 0]');
set_param([mdl '/Target Free Motion'], 'PxVelocityTargetSpecify', 'on', ...
    'PxVelocityTargetPriority', 'High', 'PxVelocityTargetValue', '-0.20');
set_param(mdl, 'StopTime', '5');

% 使脚本可重复执行：先清除旧的三指及统计模块。
deleteIfPresent(mdl, {'ThreeFingerCapture','ContactCount','At Least Two Contacts', ...
    'Finger Contact Count','TopContactStatus','TopSeparation','TopNormalForce', ...
    'Top contact status PS','Top separation PS','Top normal force PS', ...
    'Top Finger Contact','Top Finger','Top Finger Slide'});

% 第三根手指：位于 +Z 方向，与左右手指共同围成三角夹持区域。
if isempty(find_system(mdl, 'SearchDepth', 1, 'Name', 'Top Finger Mount'))
    add_block('sm_lib/Frames and Transforms/Rigid Transform', [mdl '/Top Finger Mount'], ...
        'Position', [500 420 585 470], 'TranslationMethod', 'Cartesian', ...
        'TranslationCartesianOffset', '[0.60 0 0.085]');
end
set_param([mdl '/Top Finger Mount'], 'TranslationCartesianOffset', '[0.60 0 0.085]');
add_block('sm_lib/Joints/Prismatic Joint', [mdl '/Top Finger Slide'], ...
    'Position', [625 420 690 470]);
add_block('sm_lib/Body Elements/Brick Solid', [mdl '/Top Finger'], ...
    'Position', [735 420 805 470], 'BrickDimensions', '[0.35 0.06 0.08]', ...
    'Density', '700', 'ExportEntireGeometry', 'on');

% Top Finger Mount 的 LConn 已接入平台的框架分支（与左右指共用航天器基座）。
connectIfTargetFree(mdl, 'Top Finger Mount', 'RConn', 'Top Finger Slide', 'LConn');
connectIfTargetFree(mdl, 'Top Finger Slide', 'RConn', 'Top Finger', 'RConn');

% 第三指与目标的实际 Spatial Contact Force 接触对，并记录接触状态、间隙和法向力。
addContactPair(mdl, 'Top', 'Top Finger', 'Target Debris 10cm', 580, ...
    'TopContactStatus', 'TopSeparation', 'TopNormalForce');

% 接触数量 = 三根手指接触状态之和；成功条件为至少两指同时接触。
add_block('simulink/Math Operations/Sum', [mdl '/Finger Contact Count'], ...
    'Position', [1120 420 1150 495], 'Inputs', '+++');
add_block('simulink/Logic and Bit Operations/Compare To Constant', ...
    [mdl '/At Least Two Contacts'], 'Position', [1190 440 1305 480], ...
    'relop', '>=', 'const', '2');
add_block('simulink/Sinks/To Workspace', [mdl '/ContactCount'], ...
    'Position', [1190 395 1305 425], 'VariableName', 'ContactCount', ...
    'SaveFormat', 'Structure With Time');
add_block('simulink/Sinks/To Workspace', [mdl '/ThreeFingerCapture'], ...
    'Position', [1350 440 1480 470], 'VariableName', 'ThreeFingerCapture', ...
    'SaveFormat', 'Structure With Time');

statusPS = {'Left contact status PS','Right contact status PS','Top contact status PS'};
sumPorts = get_param([mdl '/Finger Contact Count'], 'PortHandles');
for k = 1:numel(statusPS)
    p = get_param([mdl '/' statusPS{k}], 'PortHandles');
    add_line(mdl, p.Outport(1), sumPorts.Inport(k), 'autorouting', 'on');
end
countPorts = get_param([mdl '/Finger Contact Count'], 'PortHandles');
capturePorts = get_param([mdl '/At Least Two Contacts'], 'PortHandles');
countLogPorts = get_param([mdl '/ContactCount'], 'PortHandles');
captureLogPorts = get_param([mdl '/ThreeFingerCapture'], 'PortHandles');
add_line(mdl, countPorts.Outport(1), capturePorts.Inport(1), 'autorouting', 'on');
add_line(mdl, countPorts.Outport(1), countLogPorts.Inport(1), 'autorouting', 'on');
add_line(mdl, capturePorts.Outport(1), captureLogPorts.Inport(1), 'autorouting', 'on');

set_param(mdl, 'Description', ['三指空间碎片抓取模型：10 cm 球形目标以 0.20 m/s 接近，' ...
    '三根手指采用 Spatial Contact Force 实体接触；至少两指同时接触即判为初步包络成功。']);
set_param(mdl, 'SimulationCommand', 'update');
save_system(mdl, modelFile);
disp('三指模型已建立并保存。');

function addContactPair(mdl, tag, fingerName, targetName, y, statusVar, sepVar, forceVar)
    contact = [mdl '/' tag ' Finger Contact'];
    add_block('sm_lib/Forces and Torques/Spatial Contact Force', contact, ...
        'Position', [870 y 965 y+70], ...
        'NormalForceType', 'SmoothSpringDamper', ...
        'NormalStiffness', '1500', 'NormalDamping', '15', ...
        'NormalTransitionRegionWidth', '0.001', ...
        'FrictionType', 'SmoothStickSlip', ...
        'CoefficientOfStaticFriction', '0.5', ...
        'CoefficientOfDynamicFriction', '0.4', ...
        'FrictionalCriticalVelocity', '0.01', ...
        'SenseContactSignal', 'on', 'SenseSeparationDistance', 'on', ...
        'SenseNormalForceMagnitude', 'on');
    fp = get_param([mdl '/' fingerName], 'PortHandles');
    tp = get_param([mdl '/' targetName], 'PortHandles');
    cp = get_param(contact, 'PortHandles');
    add_line(mdl, fp.LConn(1), cp.LConn(1), 'autorouting', 'on');
    add_line(mdl, tp.LConn(1), cp.RConn(1), 'autorouting', 'on');
    addLoggedSignal(mdl, cp.RConn(2), [tag ' contact status PS'], statusVar, [1010 y 1130 y+25]);
    addLoggedSignal(mdl, cp.RConn(3), [tag ' separation PS'], sepVar, [1010 y+30 1130 y+55]);
    addLoggedSignal(mdl, cp.RConn(4), [tag ' normal force PS'], forceVar, [1010 y+60 1130 y+85]);
end

function addLoggedSignal(mdl, physicalPort, converterName, variableName, pos)
    converter = [mdl '/' converterName];
    logger = [mdl '/' variableName];
    add_block('nesl_utility/PS-Simulink Converter', converter, 'Position', pos);
    add_block('simulink/Sinks/To Workspace', logger, 'Position', pos + [150 0 150 0], ...
        'VariableName', variableName, 'SaveFormat', 'Structure With Time');
    cp = get_param(converter, 'PortHandles');
    lp = get_param(logger, 'PortHandles');
    add_line(mdl, physicalPort, cp.LConn(1), 'autorouting', 'on');
    add_line(mdl, cp.Outport(1), lp.Inport(1), 'autorouting', 'on');
end

function connectFrames(mdl, sourceBlock, sourceField, targetBlock, targetField)
    sp = get_param([mdl '/' sourceBlock], 'PortHandles');
    tp = get_param([mdl '/' targetBlock], 'PortHandles');
    add_line(mdl, sp.(sourceField)(1), tp.(targetField)(1), 'autorouting', 'on');
end

function connectIfTargetFree(mdl, sourceBlock, sourceField, targetBlock, targetField)
    tl = get_param([mdl '/' targetBlock], 'LineHandles');
    if isempty(tl.(targetField))
        connectFrames(mdl, sourceBlock, sourceField, targetBlock, targetField);
    end
end

function deleteIfPresent(mdl, names)
    for k = 1:numel(names)
        block = [mdl '/' names{k}];
        if ~isempty(find_system(mdl, 'SearchDepth', 1, 'Name', names{k}))
            delete_block(block);
        end
    end
end
