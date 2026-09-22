%% PLOT_CAPTURE_RESULTS
% 读取 preliminary_capture_sim.py 生成的 JSON，并绘制：
% 1) 抓手开口 × 横向定位误差的成功率热力图；
% 2) 各目标条件成功率及 Wilson 95%% 置信区间；
% 3) 各目标的首要失败原因分解图。
%
% 运行前请先执行：preliminary_capture_sim.py
% 运行方式：在 MATLAB 当前文件夹切换到本项目后，输入 plot_capture_results

clear; clc;

projectRoot = fileparts(fileparts(mfilename('fullpath')));
inputFile = fullfile(projectRoot, 'outputs', 'preliminary_capture_sim', ...
    'preliminary_capture_results.json');
outputDir = fullfile(projectRoot, 'outputs', 'preliminary_capture_sim', 'figures');

if ~isfile(inputFile)
    error('未找到结果文件：%s\n请先运行 preliminary_capture_sim.py。', inputFile);
end
if ~isfolder(outputDir)
    mkdir(outputDir);
end

% 中文显示；若本机没有微软雅黑，则删除本行或改为本机可用字体。
set(groot, 'defaultAxesFontName', 'Microsoft YaHei');
set(groot, 'defaultTextFontName', 'Microsoft YaHei');

result = jsondecode(fileread(inputFile));
targets = result.targets;
sensitivity = result.sensitivity;

figure('Color', 'w', 'Position', [80 120 1800 560]);
tiledlayout(1, 3, 'TileSpacing', 'compact', 'Padding', 'compact');

%% 图 1：抓手开口和导航定位误差的双变量敏感性热力图
nexttile;
sigmaMm = unique([sensitivity.position_sigma_mm], 'sorted');
apertureMm = unique([sensitivity.aperture_mm], 'sorted');
successGrid = nan(numel(apertureMm), numel(sigmaMm));

for k = 1:numel(sensitivity)
    i = find(apertureMm == sensitivity(k).aperture_mm, 1);
    j = find(sigmaMm == sensitivity(k).position_sigma_mm, 1);
    successGrid(i, j) = 100 * sensitivity(k).mean_single_target_success_probability;
end

imagesc(sigmaMm, apertureMm, successGrid);
set(gca, 'YDir', 'normal');
colormap(gca, parula);
cb = colorbar;
cb.Label.String = '平均单目标成功率 / %';
xlabel('横向定位误差标准差 \sigma_p / mm');
ylabel('抓手开口 / mm');
title('成功率：开口与定位误差', 'FontWeight', 'bold');
hold on;

for i = 1:numel(apertureMm)
    for j = 1:numel(sigmaMm)
        text(sigmaMm(j), apertureMm(i), sprintf('%.1f%%', successGrid(i, j)), ...
            'HorizontalAlignment', 'center', 'FontSize', 9, 'Color', 'k');
    end
end

% 红色叉号是当前 Python 蒙特卡洛模型采用的基准工况。
baselineSigmaMm = 1000 * result.assumptions.position_error_sigma_m;
baselineApertureMm = 1000 * result.assumptions.capture_aperture_m;
plot(baselineSigmaMm, baselineApertureMm, 'rx', ...
    'MarkerSize', 13, 'LineWidth', 2.5, 'DisplayName', '当前基准工况');
legend('Location', 'southwest');
grid on;

%% 图 2：不同目标的成功率和统计置信区间
nexttile;
[diameterCm, sortIndex] = sort([targets.rcs_equiv_d_cm]);
sortedTargets = targets(sortIndex);
probability = 100 * [sortedTargets.success_probability];
ciLow = 100 * [sortedTargets.wilson_95_low];
ciHigh = 100 * [sortedTargets.wilson_95_high];

errorbar(diameterCm, probability, probability - ciLow, ciHigh - probability, ...
    'o-', 'Color', [0.00 0.45 0.74], 'LineWidth', 1.5, ...
    'MarkerFaceColor', [0.00 0.45 0.74], 'MarkerSize', 6);
hold on;
meanProbability = 100 * result.mission_summary.mean_single_target_success_probability;
yline(meanProbability, '--', sprintf('平均值 %.2f%%', meanProbability), ...
    'Color', [0.85 0.33 0.10], 'LineWidth', 1.3, 'LabelHorizontalAlignment', 'left');

for k = 1:numel(sortedTargets)
    text(diameterCm(k), probability(k) + 0.45, string(sortedTargets(k).norad), ...
        'HorizontalAlignment', 'center', 'FontSize', 8);
end

xlabel('RCS 等效直径 / cm');
ylabel('初步抓取成功率 / %');
title('目标条件成功率（Wilson 95% CI）', 'FontWeight', 'bold');
ylim([min(90, min(ciLow) - 1), 100.2]);
grid on;

%% 图 3：各目标最先失败的判据；各色块互斥，可以相加得到总失败率。
nexttile;
failureFields = {'aperture_intercept', 'approach_window', 'contact_speed', ...
    'impact_impulse', 'tumble_surface_speed', 'friction_retention', 'angular_momentum'};
failureLabels = {'未进入有效包络', '接近速度超窗', '接触速度超限', ...
    '冲量超限', '翻滚表面速度超限', '摩擦保持不足', '角动量超限'};
failureMatrix = zeros(numel(targets), numel(failureFields));

for k = 1:numel(targets)
    for j = 1:numel(failureFields)
        failureMatrix(k, j) = 100 * ...
            targets(k).exclusive_primary_failure_probability.(failureFields{j});
    end
end

targetLabels = string([targets.norad]);
bar(categorical(targetLabels), failureMatrix, 'stacked', 'BarWidth', 0.72);
xlabel('目标 NORAD 编号');
ylabel('首要失败概率 / %');
title('失败原因分解（互斥首个失败判据）', 'FontWeight', 'bold');
legend(failureLabels, 'Location', 'southoutside', 'NumColumns', 2, 'FontSize', 8);
grid on;

sgtitle('三指抓手初步蒙特卡洛结果（概念筛选级）', 'FontWeight', 'bold', 'FontSize', 15);

outputFile = fullfile(outputDir, 'capture_success_summary_matlab.png');
exportgraphics(gcf, outputFile, 'Resolution', 220);
fprintf('作图完成：%s\n', outputFile);
