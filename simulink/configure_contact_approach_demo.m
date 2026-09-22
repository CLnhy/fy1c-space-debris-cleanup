%% 低速接近—接触验证工况
% 使 10 cm 等效目标以 0.20 m/s 沿 -X 方向接近左指，
% 并在约 3~4 s 内发生接触。该工况用于验证 Spatial Contact Force 的响应。

mdl = 'capture_dynamics_v1';
modelFile = fullfile(fileparts(mfilename('fullpath')), [mdl '.slx']);
if ~isfile(modelFile)
    error('未找到 %s。', modelFile);
end

load_system(modelFile);
open_system(mdl);

% 目标在左指中心线附近起始，沿 -X 方向以低相对速度接近。
set_param([mdl '/Target Initial Offset'], ...
    'TranslationMethod', 'Cartesian', ...
    'TranslationCartesianOffset', '[1.50 0.32 0]');
set_param([mdl '/Target Free Motion'], ...
    'PxVelocityTargetSpecify', 'on', ...
    'PxVelocityTargetPriority', 'High', ...
    'PxVelocityTargetValue', '-0.20');

set_param(mdl, 'StopTime', '5');
set_param(mdl, 'Description', [ ...
    '空间碎片抓取低速接近验证工况：直径 10 cm 目标从左指中心线附近以 0.20 m/s 接近；' ...
    '使用 Spatial Contact Force 记录接触状态、间距和法向力。']);
save_system(mdl, modelFile);
set_param(mdl, 'SimulationCommand', 'update');
save_system(mdl, modelFile);
open_system(mdl);
