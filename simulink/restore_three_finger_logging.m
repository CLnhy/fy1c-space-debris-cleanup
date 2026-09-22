% RESTORE_THREE_FINGER_LOGGING
% 恢复三指模型的上指测量和“至少两指接触”统计支路。
mdl = 'capture_dynamics_v1';
workFolder = fileparts(mfilename('fullpath'));
modelFile = fullfile(workFolder, [mdl '.slx']);
if ~isfile(modelFile)
    error('Model file not found: %s', modelFile);
end
load_system(modelFile);

deleteIfPresent(mdl, {'Top contact status PS','Top separation PS','Top normal force PS', ...
    'TopContactStatus','TopSeparation','TopNormalForce', ...
    'Finger Contact Count','At Least Two Contacts','ContactCount','ThreeFingerCapture'});
clearContactOutputLines(mdl, 'Top Finger Contact');

cp = get_param([mdl '/Top Finger Contact'], 'PortHandles');
addLoggedSignal(mdl, cp.RConn(2), 'Top contact status PS', 'TopContactStatus', [1020 575 1100 600]);
addLoggedSignal(mdl, cp.RConn(3), 'Top separation PS', 'TopSeparation', [1020 610 1100 635]);
addLoggedSignal(mdl, cp.RConn(4), 'Top normal force PS', 'TopNormalForce', [1020 645 1100 670]);

add_block('simulink/Math Operations/Sum', [mdl '/Finger Contact Count'], ...
    'Position', [1180 410 1210 485], 'Inputs', '+++');
add_block('simulink/Logic and Bit Operations/Compare To Constant', ...
    [mdl '/At Least Two Contacts'], 'Position', [1250 430 1365 470], ...
    'relop', '>=', 'const', '2');
add_block('simulink/Sinks/To Workspace', [mdl '/ContactCount'], ...
    'Position', [1250 385 1365 415], 'VariableName', 'ContactCount', ...
    'SaveFormat', 'Structure With Time');
add_block('simulink/Sinks/To Workspace', [mdl '/ThreeFingerCapture'], ...
    'Position', [1410 430 1540 460], 'VariableName', 'ThreeFingerCapture', ...
    'SaveFormat', 'Structure With Time');

sources = {'Left contact status PS','Right contact status PS','Top contact status PS'};
sumPorts = get_param([mdl '/Finger Contact Count'], 'PortHandles');
for k = 1:3
    pp = get_param([mdl '/' sources{k}], 'PortHandles');
    add_line(mdl, pp.Outport(1), sumPorts.Inport(k), 'autorouting', 'on');
end
sp = get_param([mdl '/Finger Contact Count'], 'PortHandles');
ap = get_param([mdl '/At Least Two Contacts'], 'PortHandles');
lp = get_param([mdl '/ContactCount'], 'PortHandles');
gp = get_param([mdl '/ThreeFingerCapture'], 'PortHandles');
add_line(mdl, sp.Outport(1), ap.Inport(1), 'autorouting', 'on');
add_line(mdl, sp.Outport(1), lp.Inport(1), 'autorouting', 'on');
add_line(mdl, ap.Outport(1), gp.Inport(1), 'autorouting', 'on');

set_param(mdl, 'SimulationCommand', 'update');
save_system(mdl, modelFile);
disp('三指记录与成功判据已恢复。');

function addLoggedSignal(mdl, physicalPort, converterName, variableName, pos)
    converter = [mdl '/' converterName];
    logger = [mdl '/' variableName];
    add_block('nesl_utility/PS-Simulink Converter', converter, 'Position', pos);
    add_block('simulink/Sinks/To Workspace', logger, 'Position', pos + [150 0 150 0], ...
        'VariableName', variableName, 'SaveFormat', 'Structure With Time');
    cp = get_param(converter, 'PortHandles');
    lp = get_param(logger, 'PortHandles');
    cl = get_param(converter, 'LineHandles');
    wl = get_param(logger, 'LineHandles');
    if lineFree(cl.LConn)
        add_line(mdl, physicalPort, cp.LConn(1), 'autorouting', 'on');
    end
    if lineFree(wl.Inport)
        add_line(mdl, cp.Outport(1), lp.Inport(1), 'autorouting', 'on');
    end
end

function deleteIfPresent(mdl, names)
    for k = 1:numel(names)
        if ~isempty(find_system(mdl, 'SearchDepth', 1, 'Name', names{k}))
            delete_block([mdl '/' names{k}]);
        end
    end
end

function clearContactOutputLines(mdl, contactName)
    lh = get_param([mdl '/' contactName], 'LineHandles');
    for k = 2:4
        if ~isempty(lh.RConn) && numel(lh.RConn) >= k && lh.RConn(k) ~= -1
            try
                delete_line(mdl, lh.RConn(k));
            catch
                % 端口可能已无有效连接；此时可直接继续创建记录支路。
            end
        end
    end
end

function tf = lineFree(h)
    tf = isempty(h) || all(h == -1);
end
