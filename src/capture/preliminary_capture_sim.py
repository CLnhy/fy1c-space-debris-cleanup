"""Preliminary Monte Carlo capture simulation for five FY-1C debris targets.

Model level: rigid target + kinematic closing delay + simplified impact,
retention, and angular-momentum limits.  The model is intended for concept
screening.  Values under ASSUMPTIONS are engineering placeholders, not public
catalog measurements or qualified hardware data.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "public_debris_calculation" / "screening_result.json"
OUTDIR = ROOT / "outputs" / "preliminary_capture_sim"
SEED = 20260903
TRIALS_PER_TARGET = 200_000


ASSUMPTIONS = {
    "capture_aperture_m": 0.30,
    "radial_safety_margin_m": 0.015,
    "position_error_sigma_m": 0.030,
    "lateral_velocity_sigma_mps": 0.010,
    "approach_speed_mean_mps": 0.050,
    "approach_speed_sigma_mps": 0.012,
    "approach_speed_min_mps": 0.015,
    "approach_speed_max_mps": 0.100,
    "closure_time_mean_s": 0.30,
    "closure_time_sigma_s": 0.05,
    "closure_time_clip_s": [0.15, 0.45],
    "physical_size_to_rcs_diameter_factor": [0.85, 1.25],
    "mass_log_uniform_kg": [0.20, 1.50],
    "tumble_rate_triangular_deg_s": [0.0, 5.0, 20.0],
    "coefficient_of_restitution_uniform": [0.10, 0.40],
    "friction_coefficient_uniform": [0.25, 0.55],
    "clamp_force_mean_N": 15.0,
    "clamp_force_sigma_N": 2.0,
    "max_contact_speed_mps": 0.120,
    "max_impact_impulse_Ns": 0.180,
    "max_surface_speed_mps": 0.025,
    "max_absorbed_angular_momentum_Nms": 0.015,
}


CRITERION_ORDER = [
    "aperture_intercept",
    "approach_window",
    "contact_speed",
    "impact_impulse",
    "tumble_surface_speed",
    "friction_retention",
    "angular_momentum",
]


def wilson_interval(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    p = successes / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom
    return centre - half, centre + half


def log_uniform(rng: np.random.Generator, low: float, high: float, n: int) -> np.ndarray:
    return np.exp(rng.uniform(math.log(low), math.log(high), n))


def simulate_target(
    rng: np.random.Generator,
    target: dict,
    n: int,
    overrides: dict | None = None,
) -> dict:
    a = dict(ASSUMPTIONS)
    if overrides:
        a.update(overrides)

    rcs_diameter = float(target["rcs_equiv_d_cm"]) / 100.0
    size_factor = rng.uniform(*a["physical_size_to_rcs_diameter_factor"], n)
    physical_diameter = rcs_diameter * size_factor
    target_radius = physical_diameter / 2.0

    # Position and velocity are expressed in the gripper frame.  x/y are
    # lateral to the capture axis; positive z speed means commanded approach.
    x0 = rng.normal(0.0, a["position_error_sigma_m"], n)
    y0 = rng.normal(0.0, a["position_error_sigma_m"], n)
    vx = rng.normal(0.0, a["lateral_velocity_sigma_mps"], n)
    vy = rng.normal(0.0, a["lateral_velocity_sigma_mps"], n)
    vz = rng.normal(a["approach_speed_mean_mps"], a["approach_speed_sigma_mps"], n)
    close_time = np.clip(
        rng.normal(a["closure_time_mean_s"], a["closure_time_sigma_s"], n),
        a["closure_time_clip_s"][0],
        a["closure_time_clip_s"][1],
    )

    # Propagate lateral drift until the gripper has closed and locked.
    x_lock = x0 + vx * close_time
    y_lock = y0 + vy * close_time
    radial_offset = np.hypot(x_lock, y_lock)
    radial_clearance = (
        (a["capture_aperture_m"] - physical_diameter) / 2.0
        - a["radial_safety_margin_m"]
    )

    omega_deg_s = rng.triangular(*a["tumble_rate_triangular_deg_s"], n)
    omega = np.deg2rad(omega_deg_s)
    surface_speed = omega * target_radius
    lateral_speed = np.hypot(vx, vy)
    contact_speed = np.sqrt(vz * vz + lateral_speed * lateral_speed + surface_speed * surface_speed)

    mass = log_uniform(rng, *a["mass_log_uniform_kg"], n)
    restitution = rng.uniform(*a["coefficient_of_restitution_uniform"], n)
    friction = rng.uniform(*a["friction_coefficient_uniform"], n)
    clamp_force = np.maximum(0.1, rng.normal(a["clamp_force_mean_N"], a["clamp_force_sigma_N"], n))

    impact_impulse = mass * (1.0 + restitution) * contact_speed
    # Tangential impulse that can be arrested during the closing interval.
    required_tangential_impulse = mass * (lateral_speed + surface_speed)
    available_friction_impulse = friction * clamp_force * close_time

    # Rigid equivalent sphere: I = 2/5 m r^2.  Include off-centre approach
    # momentum to represent the attitude-control impulse after capture.
    spin_momentum = 0.4 * mass * target_radius * target_radius * omega
    offset_momentum = mass * radial_offset * np.maximum(vz, 0.0)
    absorbed_angular_momentum = spin_momentum + offset_momentum

    criteria = {
        "aperture_intercept": (radial_clearance > 0.0) & (radial_offset <= radial_clearance),
        "approach_window": (vz >= a["approach_speed_min_mps"]) & (vz <= a["approach_speed_max_mps"]),
        "contact_speed": contact_speed <= a["max_contact_speed_mps"],
        "impact_impulse": impact_impulse <= a["max_impact_impulse_Ns"],
        "tumble_surface_speed": surface_speed <= a["max_surface_speed_mps"],
        "friction_retention": required_tangential_impulse <= available_friction_impulse,
        "angular_momentum": absorbed_angular_momentum <= a["max_absorbed_angular_momentum_Nms"],
    }

    success = np.ones(n, dtype=bool)
    for name in CRITERION_ORDER:
        success &= criteria[name]

    successes = int(success.sum())
    ci_low, ci_high = wilson_interval(successes, n)

    active = np.ones(n, dtype=bool)
    primary_failure = {}
    for name in CRITERION_ORDER:
        first_fail = active & ~criteria[name]
        primary_failure[name] = int(first_fail.sum()) / n
        active &= criteria[name]

    return {
        "norad": int(target["norad"]),
        "object_id": target["object_id"],
        "rcs_equiv_d_cm": float(target["rcs_equiv_d_cm"]),
        "trials": n,
        "successes": successes,
        "success_probability": successes / n,
        "wilson_95_low": ci_low,
        "wilson_95_high": ci_high,
        "mean_physical_diameter_cm": float(physical_diameter.mean() * 100.0),
        "mean_radial_clearance_cm": float(radial_clearance.mean() * 100.0),
        "marginal_failure_probability": {
            name: float((~passed).mean()) for name, passed in criteria.items()
        },
        "exclusive_primary_failure_probability": primary_failure,
    }


def pooled_summary(results: list[dict]) -> dict:
    probabilities = np.array([r["success_probability"] for r in results])
    return {
        "mean_single_target_success_probability": float(probabilities.mean()),
        "minimum_single_target_success_probability": float(probabilities.min()),
        "maximum_single_target_success_probability": float(probabilities.max()),
        "expected_successful_captures_if_all_five_attempted": float(probabilities.sum()),
        "probability_all_five_succeed_independent_attempts": float(probabilities.prod()),
        "probability_at_least_one_failure_independent_attempts": float(1.0 - probabilities.prod()),
    }


def run_sensitivity(targets: list[dict]) -> list[dict]:
    cases = []
    # Use a smaller but still stable sample for each screening case.
    n = 50_000
    case_id = 0
    for sigma_mm in [15, 25, 30, 40, 50]:
        for aperture_mm in [250, 300, 350]:
            case_id += 1
            rng = np.random.default_rng(SEED + 1000 + case_id)
            results = [
                simulate_target(
                    rng,
                    t,
                    n,
                    {
                        "position_error_sigma_m": sigma_mm / 1000.0,
                        "capture_aperture_m": aperture_mm / 1000.0,
                    },
                )
                for t in targets
            ]
            p = np.array([r["success_probability"] for r in results])
            cases.append(
                {
                    "position_sigma_mm": sigma_mm,
                    "aperture_mm": aperture_mm,
                    "mean_single_target_success_probability": float(p.mean()),
                    "probability_all_five_succeed": float(p.prod()),
                }
            )
    return cases


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows({k: row.get(k) for k in columns} for row in rows)


def main() -> None:
    payload = json.loads(INPUT.read_text(encoding="utf-8"))
    selected = {int(t["norad"]): t for t in payload["selected_targets"]}
    route = payload["timed_route_minimum_dv"]["route"]
    targets = [selected[int(norad)] for norad in route]

    rng = np.random.default_rng(SEED)
    results = [simulate_target(rng, target, TRIALS_PER_TARGET) for target in targets]
    sensitivity = run_sensitivity(targets)

    output = {
        "model": "rigid body + kinematic closing delay + simplified contact/retention limits",
        "purpose": "concept screening only; not a qualified mission reliability prediction",
        "random_seed": SEED,
        "trials_per_target": TRIALS_PER_TARGET,
        "input_orbit_dataset": str(INPUT.relative_to(ROOT)).replace("\\", "/"),
        "assumption_classification": "All ASSUMPTIONS values are planning assumptions until replaced by hardware, navigation, and target-characterization test data.",
        "assumptions": ASSUMPTIONS,
        "success_definition": CRITERION_ORDER,
        "targets": results,
        "mission_summary": pooled_summary(results),
        "sensitivity": sensitivity,
    }

    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "preliminary_capture_results.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    target_rows = []
    for result in results:
        row = {k: result[k] for k in [
            "norad", "object_id", "rcs_equiv_d_cm", "trials", "successes",
            "success_probability", "wilson_95_low", "wilson_95_high",
            "mean_physical_diameter_cm", "mean_radial_clearance_cm",
        ]}
        row.update({f"primary_fail_{k}": v for k, v in result["exclusive_primary_failure_probability"].items()})
        target_rows.append(row)
    target_columns = list(target_rows[0].keys())
    write_csv(OUTDIR / "preliminary_capture_targets.csv", target_rows, target_columns)
    write_csv(
        OUTDIR / "preliminary_capture_sensitivity.csv",
        sensitivity,
        [
            "position_sigma_mm",
            "aperture_mm",
            "mean_single_target_success_probability",
            "probability_all_five_succeed",
        ],
    )

    print(json.dumps(output["mission_summary"], ensure_ascii=False, indent=2))
    for result in results:
        print(
            f"NORAD {result['norad']}: p={result['success_probability']:.5f}, "
            f"95% CI [{result['wilson_95_low']:.5f}, {result['wilson_95_high']:.5f}]"
        )


if __name__ == "__main__":
    main()
