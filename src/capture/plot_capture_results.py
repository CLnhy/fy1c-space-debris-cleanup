"""Plot the preliminary three-finger capture Monte Carlo results.

Input:
    outputs/preliminary_capture_sim/preliminary_capture_results.json

Output:
    outputs/preliminary_capture_sim/figures/capture_success_summary.png

Run with the bundled Python runtime:
    python src/capture/plot_capture_results.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "outputs" / "preliminary_capture_sim" / "preliminary_capture_results.json"
OUTDIR = INPUT.parent / "figures"


def configure_chinese_font() -> None:
    """Prefer common Windows Chinese fonts, while remaining usable elsewhere."""
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False


def plot_sensitivity_heatmap(ax: plt.Axes, data: dict) -> None:
    """Plot aperture versus position-error success probability."""
    sensitivity = data["sensitivity"]
    position_mm = sorted({row["position_sigma_mm"] for row in sensitivity})
    aperture_mm = sorted({row["aperture_mm"] for row in sensitivity})
    grid = np.full((len(aperture_mm), len(position_mm)), np.nan)

    for row in sensitivity:
        row_idx = aperture_mm.index(row["aperture_mm"])
        col_idx = position_mm.index(row["position_sigma_mm"])
        grid[row_idx, col_idx] = 100 * row["mean_single_target_success_probability"]

    image = ax.imshow(
        grid,
        origin="lower",
        aspect="auto",
        cmap="YlGnBu",
        vmin=np.floor(np.nanmin(grid)),
        vmax=np.ceil(np.nanmax(grid)),
    )
    ax.set_xticks(range(len(position_mm)), position_mm)
    ax.set_yticks(range(len(aperture_mm)), aperture_mm)
    ax.set_xlabel("横向定位误差标准差 σp / mm")
    ax.set_ylabel("抓手开口 / mm")
    ax.set_title("初步抓取成功率：开口与定位误差", weight="bold")

    for row_idx, aperture in enumerate(aperture_mm):
        for col_idx, sigma in enumerate(position_mm):
            ax.text(
                col_idx,
                row_idx,
                f"{grid[row_idx, col_idx]:.1f}%",
                ha="center",
                va="center",
                fontsize=8,
                color="white" if grid[row_idx, col_idx] < 96 else "black",
            )

    assumptions = data["assumptions"]
    baseline_sigma = 1000 * assumptions["position_error_sigma_m"]
    baseline_aperture = 1000 * assumptions["capture_aperture_m"]
    baseline_x = position_mm.index(baseline_sigma)
    baseline_y = aperture_mm.index(baseline_aperture)
    ax.plot(
        baseline_x,
        baseline_y,
        marker="x",
        markersize=12,
        markeredgewidth=2.5,
        color="crimson",
        label="当前基准工况",
    )
    ax.legend(loc="lower left", fontsize=8, frameon=True)
    colorbar = ax.figure.colorbar(image, ax=ax, pad=0.02)
    colorbar.set_label("平均单目标成功率 / %")


def plot_target_success(ax: plt.Axes, data: dict) -> None:
    """Plot target-level probabilities and Wilson 95% confidence intervals."""
    targets = sorted(data["targets"], key=lambda row: row["rcs_equiv_d_cm"])
    diameter = np.array([row["rcs_equiv_d_cm"] for row in targets])
    probability = 100 * np.array([row["success_probability"] for row in targets])
    lower = 100 * np.array([row["wilson_95_low"] for row in targets])
    upper = 100 * np.array([row["wilson_95_high"] for row in targets])

    ax.errorbar(
        diameter,
        probability,
        yerr=np.vstack([probability - lower, upper - probability]),
        fmt="o-",
        capsize=3,
        color="#1f77b4",
        label="单目标成功率（95% CI）",
    )
    for d, p, target in zip(diameter, probability, targets):
        ax.annotate(
            str(target["norad"]),
            (d, p),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=8,
        )

    mean_probability = 100 * data["mission_summary"]["mean_single_target_success_probability"]
    ax.axhline(mean_probability, color="crimson", linestyle="--", linewidth=1.2,
               label=f"五目标平均值：{mean_probability:.2f}%")
    ax.set_xlabel("RCS 等效直径 / cm")
    ax.set_ylabel("初步抓取成功率 / %")
    ax.set_title("不同约 10 cm 目标的条件成功率", weight="bold")
    ax.set_ylim(min(90, lower.min() - 1), 100.2)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8, loc="lower left")


def plot_primary_failures(ax: plt.Axes, data: dict) -> None:
    """Plot mutually exclusive first-failure causes by target."""
    labels = {
        "aperture_intercept": "未进入有效包络",
        "approach_window": "接近速度超窗",
        "contact_speed": "接触速度超限",
        "impact_impulse": "冲量超限",
        "tumble_surface_speed": "翻滚表面速度超限",
        "friction_retention": "摩擦保持不足",
        "angular_momentum": "角动量超限",
    }
    colors = ["#d55e00", "#e69f00", "#56b4e9", "#009e73", "#0072b2", "#cc79a7", "#666666"]
    targets = data["targets"]
    x = np.arange(len(targets))
    bottom = np.zeros(len(targets))

    for (key, label), color in zip(labels.items(), colors):
        values = 100 * np.array(
            [row["exclusive_primary_failure_probability"][key] for row in targets]
        )
        ax.bar(x, values, bottom=bottom, width=0.68, label=label, color=color)
        bottom += values

    ax.set_xticks(x, [str(row["norad"]) for row in targets])
    ax.set_xlabel("目标 NORAD 编号")
    ax.set_ylabel("首要失败概率 / %")
    ax.set_title("失败原因分解（互斥首个失败判据）", weight="bold")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=7, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.23))


def main() -> None:
    if not INPUT.exists():
        raise FileNotFoundError(
            f"找不到蒙特卡洛结果：{INPUT}\n"
            "请先运行 preliminary_capture_sim.py。"
        )

    data = json.loads(INPUT.read_text(encoding="utf-8"))
    configure_chinese_font()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    figure, axes = plt.subplots(1, 3, figsize=(18, 5.8), constrained_layout=True)
    plot_sensitivity_heatmap(axes[0], data)
    plot_target_success(axes[1], data)
    plot_primary_failures(axes[2], data)

    figure.suptitle(
        "三指抓手初步蒙特卡洛结果（概念筛选级）",
        fontsize=16,
        fontweight="bold",
    )
    output = OUTDIR / "capture_success_summary.png"
    figure.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(figure)
    print(f"已生成：{output}")


if __name__ == "__main__":
    main()
