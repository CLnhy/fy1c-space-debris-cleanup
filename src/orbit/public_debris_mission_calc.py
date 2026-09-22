#!/usr/bin/env python3
"""Preliminary, reproducible ADR benchmark from public CelesTrak data.

The route model deliberately separates catalog-derived quantities from
architecture assumptions.  It is an impulsive two-body screening model, not a
flight-dynamics or proximity-operations product.
"""

from __future__ import annotations

import itertools
import json
import math
import pathlib
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEPS_DIR = ROOT / "vendor" / "sgp4_local"
if DEPS_DIR.exists():
    sys.path.insert(0, str(DEPS_DIR))

from sgp4 import omm
from sgp4.api import Satrec
from sgp4.conveniences import jday_datetime


MU = 398600.4418  # km^3/s^2
R_E = 6378.137  # km
G0 = 9.80665  # m/s^2

GP_URL = (
    "https://celestrak.org/NORAD/elements/gp.php?"
    "GROUP=FENGYUN-1C-DEBRIS&FORMAT=JSON"
)
SATCAT_URL = (
    "https://celestrak.org/satcat/records.php?NAME="
    + urllib.parse.quote("FENGYUN 1C DEB")
    + "&FORMAT=JSON&ONORBIT=1"
)


@dataclass(frozen=True)
class Target:
    norad: int
    object_id: str
    name: str
    epoch: str
    mean_motion_rev_day: float
    a_km: float
    e: float
    inc_deg: float
    source_raan_deg: float
    raan_deg: float
    source_argp_deg: float
    argp_deg: float
    source_mean_anomaly_deg: float
    mean_anomaly_deg: float
    reference_epoch: str
    epoch_age_days: float
    perigee_km: float
    apogee_km: float
    period_min: float
    rcs_m2: float
    rcs_equiv_d_cm: float
    state_r_teme_km: tuple[float, float, float] = (0.0, 0.0, 0.0)
    state_v_teme_kms: tuple[float, float, float] = (0.0, 0.0, 0.0)


def fetch_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Codex ADR benchmark/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def angle_diff_deg(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def semimajor_from_mean_motion(rev_per_day: float) -> float:
    n = rev_per_day * 2.0 * math.pi / 86400.0
    return (MU / n**2) ** (1.0 / 3.0)


def plane_angle_rad(t1: Target, t2: Target) -> float:
    i1, i2 = math.radians(t1.inc_deg), math.radians(t2.inc_deg)
    draan = math.radians(angle_diff_deg(t1.raan_deg, t2.raan_deg))
    c = math.cos(i1) * math.cos(i2) + math.sin(i1) * math.sin(i2) * math.cos(draan)
    return math.acos(max(-1.0, min(1.0, c)))


def combined_hohmann_plane_change(t1: Target, t2: Target) -> dict[str, float]:
    """Two-impulse transfer between equivalent circular radii.

    The complete plane change is combined with the burn at the higher radius.
    This is an exact evaluation of that declared architecture, not a globally
    optimal transfer between the original eccentric mean-element orbits.
    """
    r1, r2 = t1.a_km, t2.a_km
    psi = plane_angle_rad(t1, t2)
    vc1, vc2 = math.sqrt(MU / r1), math.sqrt(MU / r2)
    at = (r1 + r2) / 2.0
    vt1 = math.sqrt(MU * (2.0 / r1 - 1.0 / at))
    vt2 = math.sqrt(MU * (2.0 / r2 - 1.0 / at))
    if r2 >= r1:
        dv1 = abs(vt1 - vc1)
        dv2 = math.sqrt(vt2**2 + vc2**2 - 2.0 * vt2 * vc2 * math.cos(psi))
    else:
        dv1 = math.sqrt(vc1**2 + vt1**2 - 2.0 * vc1 * vt1 * math.cos(psi))
        dv2 = abs(vc2 - vt2)
    tof_s = math.pi * math.sqrt(at**3 / MU)
    return {
        "plane_angle_deg": math.degrees(psi),
        "dv_mps": (dv1 + dv2) * 1000.0,
        "hohmann_tof_min": tof_s / 60.0,
    }


def satrec_from_omm(fields: dict) -> Satrec:
    satellite = Satrec()
    omm.initialize(satellite, fields)
    return satellite


def sgp4_state(satellite: Satrec, when: datetime):
    jd, fraction = jday_datetime(when)
    error, r, v = satellite.sgp4(jd, fraction)
    if error:
        raise RuntimeError(f"SGP4 error {error} at {when.isoformat()}")
    return tuple(r), tuple(v)


def unit(vector):
    magnitude = norm(vector)
    return tuple(value / magnitude for value in vector)


def signed_prograde_angle(r_from, r_to, h_vector):
    a, b, h = unit(r_from), unit(r_to), unit(h_vector)
    return math.atan2(dot(h, cross(a, b)), dot(a, b)) % (2.0 * math.pi)


def plane_angle_from_states(r1, v1, r2, v2):
    h1, h2 = unit(cross(r1, v1)), unit(cross(r2, v2))
    cosine = max(-1.0, min(1.0, dot(h1, h2)))
    return math.acos(cosine)


def semimajor_from_state(r, v):
    return -MU / (2.0 * (dot(v, v) / 2.0 - MU / norm(r)))


def combined_transfer_from_states(r1, v1, r2, v2):
    radius1, radius2 = semimajor_from_state(r1, v1), semimajor_from_state(r2, v2)
    plane_angle = plane_angle_from_states(r1, v1, r2, v2)
    vc1, vc2 = math.sqrt(MU / radius1), math.sqrt(MU / radius2)
    transfer_a = (radius1 + radius2) / 2.0
    vt1 = math.sqrt(MU * (2.0 / radius1 - 1.0 / transfer_a))
    vt2 = math.sqrt(MU * (2.0 / radius2 - 1.0 / transfer_a))
    if radius2 >= radius1:
        dv1 = abs(vt1 - vc1)
        dv2 = math.sqrt(vt2**2 + vc2**2 - 2.0 * vt2 * vc2 * math.cos(plane_angle))
    else:
        dv1 = math.sqrt(vc1**2 + vt1**2 - 2.0 * vc1 * vt1 * math.cos(plane_angle))
        dv2 = abs(vc2 - vt2)
    return {
        "radius1_km": radius1,
        "radius2_km": radius2,
        "plane_angle_deg": math.degrees(plane_angle),
        "dv_mps": (dv1 + dv2) * 1000.0,
        "tof_s": math.pi * math.sqrt(transfer_a**3 / MU),
    }


def find_next_plane_crossings(
    current_satellite: Satrec,
    next_satellite: Satrec,
    start: datetime,
    horizon_hours: float = 4.0,
    sample_seconds: float = 180.0,
):
    def residual(when):
        r1, _ = sgp4_state(current_satellite, when)
        r2, v2 = sgp4_state(next_satellite, when)
        return dot(unit(r1), unit(cross(r2, v2)))

    roots = []
    left = start + timedelta(seconds=1.0)
    f_left = residual(left)
    steps = int(horizon_hours * 3600.0 / sample_seconds)
    for step in range(1, steps + 1):
        right = start + timedelta(seconds=step * sample_seconds)
        f_right = residual(right)
        if f_left == 0.0 or f_left * f_right < 0.0:
            low, high = left, right
            f_low = f_left
            for _ in range(35):
                middle = low + (high - low) / 2
                f_middle = residual(middle)
                if f_low * f_middle <= 0.0:
                    high = middle
                else:
                    low, f_low = middle, f_middle
            root = low + (high - low) / 2
            if not roots or (root - roots[-1]).total_seconds() > 60.0:
                roots.append(root)
            if len(roots) == 2:
                break
        left, f_left = right, f_right
    if not roots:
        raise RuntimeError("No mutual-plane crossing found within search horizon")
    return roots


def phasing_solution(radius_km: float, phase_ahead_rad: float, max_burn_mps: float = 10.0):
    circular_period = 2.0 * math.pi * math.sqrt(radius_km**3 / MU)
    circular_velocity = math.sqrt(MU / radius_km)
    candidates = []
    gain_fraction = (phase_ahead_rad % (2.0 * math.pi)) / (2.0 * math.pi)
    for direction, fraction in (("lower", gain_fraction), ("upper", 1.0 - gain_fraction)):
        if fraction < 1e-10:
            candidates.append({"direction": "none", "duration_s": 0.0, "dv_mps": 0.0, "orbits": 0})
            continue
        for orbit_count in range(1, 1000):
            ratio = 1.0 - fraction / orbit_count if direction == "lower" else 1.0 + fraction / orbit_count
            phasing_period = circular_period * ratio
            phasing_a = radius_km * ratio ** (2.0 / 3.0)
            if phasing_a <= radius_km / 2.0:
                continue
            if direction == "lower" and 2.0 * phasing_a - radius_km < R_E + 200.0:
                continue
            phasing_velocity = math.sqrt(MU * (2.0 / radius_km - 1.0 / phasing_a))
            burn_mps = abs(phasing_velocity - circular_velocity) * 1000.0
            if burn_mps <= max_burn_mps:
                candidates.append(
                    {
                        "direction": direction,
                        "duration_s": orbit_count * phasing_period,
                        "dv_mps": 2.0 * burn_mps,
                        "orbits": orbit_count,
                        "burn_each_mps": burn_mps,
                    }
                )
                break
    return min(candidates, key=lambda item: (item["duration_s"], item["dv_mps"]))


def simulate_leg(
    current_target: Target,
    next_target: Target,
    satellites: dict[int, Satrec],
    start: datetime,
    max_phase_burn_mps: float = 10.0,
):
    current_sat = satellites[current_target.norad]
    next_sat = satellites[next_target.norad]
    candidates = []
    for departure in find_next_plane_crossings(current_sat, next_sat, start):
        r1, v1 = sgp4_state(current_sat, departure)
        r2_departure, v2_departure = sgp4_state(next_sat, departure)
        transfer = combined_transfer_from_states(r1, v1, r2_departure, v2_departure)
        arrival = departure + timedelta(seconds=transfer["tof_s"])
        target_r_arrival, target_v_arrival = sgp4_state(next_sat, arrival)
        arrival_position = tuple(-value for value in unit(r1))
        phase_angle = signed_prograde_angle(
            arrival_position,
            target_r_arrival,
            cross(target_r_arrival, target_v_arrival),
        )
        phase = phasing_solution(transfer["radius2_km"], phase_angle, max_phase_burn_mps)
        rendezvous = arrival + timedelta(seconds=phase["duration_s"])
        candidates.append(
            {
                "from": current_target.norad,
                "to": next_target.norad,
                "start_utc": start.isoformat(),
                "departure_utc": departure.isoformat(),
                "arrival_orbit_utc": arrival.isoformat(),
                "rendezvous_utc": rendezvous.isoformat(),
                "node_wait_hours": (departure - start).total_seconds() / 3600.0,
                "hohmann_tof_min": transfer["tof_s"] / 60.0,
                "phase_angle_deg": math.degrees(phase_angle),
                "phase_direction": phase["direction"],
                "phase_orbits": phase["orbits"],
                "phase_duration_days": phase["duration_s"] / 86400.0,
                "plane_angle_deg": transfer["plane_angle_deg"],
                "geometry_dv_mps": transfer["dv_mps"],
                "phasing_dv_mps": phase["dv_mps"],
                "leg_dv_mps": transfer["dv_mps"] + phase["dv_mps"],
                "leg_duration_days": (rendezvous - start).total_seconds() / 86400.0,
            }
        )
    return min(candidates, key=lambda item: (item["leg_duration_days"], item["leg_dv_mps"]))


def simulate_route(
    route: list[Target],
    gp_by_id: dict[int, dict],
    start: datetime,
    dwell_days_after_capture: float = 2.0,
    max_phase_burn_mps: float = 10.0,
):
    satellites = {norad: satrec_from_omm(gp_by_id[norad]) for norad in {t.norad for t in route}}
    current_time = start + timedelta(days=dwell_days_after_capture)
    legs = []
    for current, nxt in zip(route, route[1:]):
        leg = simulate_leg(current, nxt, satellites, current_time, max_phase_burn_mps)
        legs.append(leg)
        current_time = datetime.fromisoformat(leg["rendezvous_utc"]) + timedelta(
            days=dwell_days_after_capture
        )
    return {
        "route": [target.norad for target in route],
        "legs": legs,
        "inter_target_dv_mps": sum(leg["leg_dv_mps"] for leg in legs),
        "inter_target_elapsed_days": (current_time - start).total_seconds() / 86400.0,
        "dwell_days_after_capture": dwell_days_after_capture,
        "max_phase_burn_each_mps": max_phase_burn_mps,
    }


def load_targets(gp_rows, sat_rows) -> list[Target]:
    sat_by_id = {int(row["NORAD_CAT_ID"]): row for row in sat_rows}
    targets: list[Target] = []
    for gp in gp_rows:
        sat = sat_by_id.get(int(gp["NORAD_CAT_ID"]))
        if not sat or sat.get("RCS") is None:
            continue
        rcs = float(sat["RCS"])
        d_eq_cm = 200.0 * math.sqrt(rcs / math.pi)
        perigee = float(sat["PERIGEE"])
        apogee = float(sat["APOGEE"])
        e = float(gp["ECCENTRICITY"])
        if not (
            8.0 <= d_eq_cm <= 12.0
            and 700.0 <= perigee
            and apogee <= 900.0
            and e <= 0.02
        ):
            continue
        a = semimajor_from_mean_motion(float(gp["MEAN_MOTION"]))
        targets.append(
            Target(
                norad=int(gp["NORAD_CAT_ID"]),
                object_id=gp["OBJECT_ID"],
                name=gp["OBJECT_NAME"],
                epoch=gp["EPOCH"],
                mean_motion_rev_day=float(gp["MEAN_MOTION"]),
                a_km=a,
                e=e,
                inc_deg=float(gp["INCLINATION"]),
                source_raan_deg=float(gp["RA_OF_ASC_NODE"]),
                raan_deg=float(gp["RA_OF_ASC_NODE"]),
                source_argp_deg=float(gp["ARG_OF_PERICENTER"]),
                argp_deg=float(gp["ARG_OF_PERICENTER"]),
                source_mean_anomaly_deg=float(gp["MEAN_ANOMALY"]),
                mean_anomaly_deg=float(gp["MEAN_ANOMALY"]),
                reference_epoch=gp["EPOCH"],
                epoch_age_days=0.0,
                perigee_km=perigee,
                apogee_km=apogee,
                period_min=1440.0 / float(gp["MEAN_MOTION"]),
                rcs_m2=rcs,
                rcs_equiv_d_cm=d_eq_cm,
            )
        )
    return targets


def parse_epoch(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def norm(a):
    return math.sqrt(dot(a, a))


def rv_to_elements(r, v):
    rmag, vmag = norm(r), norm(v)
    hvec = cross(r, v)
    hmag = norm(hvec)
    nvec = (-hvec[1], hvec[0], 0.0)
    nmag = norm(nvec)
    rv = dot(r, v)
    evec = tuple(((vmag**2 - MU / rmag) * x - rv * y) / MU for x, y in zip(r, v))
    ecc = norm(evec)
    energy = vmag**2 / 2.0 - MU / rmag
    sma = -MU / (2.0 * energy)
    inc = math.acos(max(-1.0, min(1.0, hvec[2] / hmag)))
    raan = math.atan2(nvec[1], nvec[0]) % (2.0 * math.pi)
    if ecc > 1e-10 and nmag > 1e-10:
        argp = math.atan2(
            dot(cross(nvec, evec), hvec) / (nmag * ecc * hmag),
            dot(nvec, evec) / (nmag * ecc),
        ) % (2.0 * math.pi)
        nu = math.atan2(
            dot(cross(evec, r), hvec) / (ecc * rmag * hmag),
            dot(evec, r) / (ecc * rmag),
        ) % (2.0 * math.pi)
        ecc_anomaly = 2.0 * math.atan2(
            math.sqrt(1.0 - ecc) * math.sin(nu / 2.0),
            math.sqrt(1.0 + ecc) * math.cos(nu / 2.0),
        )
        mean_anomaly = (ecc_anomaly - ecc * math.sin(ecc_anomaly)) % (2.0 * math.pi)
    else:
        argp = 0.0
        mean_anomaly = math.atan2(r[2] / max(math.sin(inc), 1e-12), dot(r, nvec) / max(nmag, 1e-12)) % (2.0 * math.pi)
    return sma, ecc, inc, raan, argp, mean_anomaly


def propagate_sgp4(target: Target, gp_fields: dict, reference: datetime) -> Target:
    """Propagate the CelesTrak OMM mean elements with SGP4 to a common epoch."""
    epoch = parse_epoch(target.epoch)
    satellite = Satrec()
    omm.initialize(satellite, gp_fields)
    jd, fraction = jday_datetime(reference)
    error, r, v = satellite.sgp4(jd, fraction)
    if error:
        raise RuntimeError(f"SGP4 error {error} for NORAD {target.norad}")
    sma, ecc, inc, raan, argp, mean_anomaly = rv_to_elements(r, v)
    return replace(
        target,
        a_km=sma,
        e=ecc,
        inc_deg=math.degrees(inc),
        raan_deg=math.degrees(raan),
        argp_deg=math.degrees(argp),
        mean_anomaly_deg=math.degrees(mean_anomaly),
        reference_epoch=reference.isoformat(),
        epoch_age_days=(reference - epoch).total_seconds() / 86400.0,
        state_r_teme_km=tuple(r),
        state_v_teme_kms=tuple(v),
    )


def best_route(targets: list[Target], neighbor_count: int = 12) -> tuple[list[Target], float]:
    n = len(targets)
    costs = [[0.0] * n for _ in range(n)]
    neighbors: list[list[int]] = []
    for i in range(n):
        ranked = []
        for j in range(n):
            if i == j:
                continue
            cost = combined_hohmann_plane_change(targets[i], targets[j])["dv_mps"]
            costs[i][j] = cost
            ranked.append((cost, j))
        ranked.sort()
        neighbors.append([j for _, j in ranked[:neighbor_count]])

    best_path: list[int] | None = None
    best_cost = float("inf")

    def visit(path: list[int], cost: float):
        nonlocal best_path, best_cost
        if cost >= best_cost:
            return
        if len(path) == 5:
            best_path, best_cost = path.copy(), cost
            return
        for nxt in neighbors[path[-1]]:
            if nxt in path:
                continue
            visit(path + [nxt], cost + costs[path[-1]][nxt])

    for start in range(n):
        visit([start], 0.0)
    assert best_path is not None
    return [targets[i] for i in best_path], best_cost


def deorbit_from_apogee(target: Target, final_perigee_alt_km: float = 100.0) -> dict[str, float]:
    ra = target.a_km * (1.0 + target.e)
    a0 = target.a_km
    rp_new = R_E + final_perigee_alt_km
    at = (ra + rp_new) / 2.0
    v_before = math.sqrt(MU * (2.0 / ra - 1.0 / a0))
    v_after = math.sqrt(MU * (2.0 / ra - 1.0 / at))
    coast_s = math.pi * math.sqrt(at**3 / MU)
    return {
        "burn_mps": (v_before - v_after) * 1000.0,
        "coast_min": coast_s / 60.0,
        "burn_altitude_km": ra - R_E,
        "target_perigee_km": final_perigee_alt_km,
    }


def sphere_proxy_mass_kg(diameter_cm: float, density_g_cm3: float) -> float:
    return 4.0 / 3.0 * math.pi * (diameter_cm / 2.0) ** 3 * density_g_cm3 / 1000.0


def main():
    out_dir = ROOT / "public_debris_calculation"
    out_dir.mkdir(exist_ok=True)
    gp_snapshot = out_dir / "celestrak_fy1c_gp_snapshot.json"
    sat_snapshot = out_dir / "celestrak_fy1c_satcat_snapshot.json"
    offline = "--offline" in sys.argv
    if offline:
        gp_saved = json.loads(gp_snapshot.read_text(encoding="utf-8"))
        sat_saved = json.loads(sat_snapshot.read_text(encoding="utf-8"))
        retrieved = gp_saved["retrieved_utc"]
        gp_rows = gp_saved["data"]
        sat_rows = sat_saved["data"]
    else:
        retrieved = datetime.now(timezone.utc).isoformat()
        gp_rows = fetch_json(GP_URL)
        sat_rows = fetch_json(SATCAT_URL)
    gp_snapshot.write_text(
        json.dumps({"retrieved_utc": retrieved, "source": GP_URL, "data": gp_rows}, indent=2),
        encoding="utf-8",
    )
    sat_snapshot.write_text(
        json.dumps({"retrieved_utc": retrieved, "source": SATCAT_URL, "data": sat_rows}, indent=2),
        encoding="utf-8",
    )

    raw_targets = load_targets(gp_rows, sat_rows)
    common_epoch = max(parse_epoch(target.epoch) for target in raw_targets)
    # Stale GP records can create spurious plane clusters.  Retain only objects
    # observed within three days of the common epoch, then propagate their mean
    # elements to that epoch with first-order secular J2 rates.
    fresh_targets = [
        target
        for target in raw_targets
        if (common_epoch - parse_epoch(target.epoch)).total_seconds() <= 3.0 * 86400.0
    ]
    gp_by_id = {int(row["NORAD_CAT_ID"]): row for row in gp_rows}
    targets = [
        propagate_sgp4(target, gp_by_id[target.norad], common_epoch)
        for target in fresh_targets
    ]
    route, route_dv = best_route(targets)
    legs = []
    for a, b in zip(route, route[1:]):
        leg = combined_hohmann_plane_change(a, b)
        leg.update({"from": a.norad, "to": b.norad})
        legs.append(leg)
    timed_routes = [
        simulate_route(list(permutation), gp_by_id, common_epoch)
        for permutation in itertools.permutations(route)
    ]
    best_timed_by_dv = min(
        timed_routes,
        key=lambda item: (item["inter_target_dv_mps"], item["inter_target_elapsed_days"]),
    )
    best_timed_by_time = min(
        timed_routes,
        key=lambda item: (item["inter_target_elapsed_days"], item["inter_target_dv_mps"]),
    )
    route_by_id = {target.norad: target for target in route}
    final_target = route_by_id[best_timed_by_dv["route"][-1]]
    deorbit = deorbit_from_apogee(final_target)

    phase_burn_sensitivity = {}
    for phase_limit in (5.0, 10.0, 20.0):
        if phase_limit == 10.0:
            phase_routes = timed_routes
        else:
            phase_routes = [
                simulate_route(
                    list(permutation),
                    gp_by_id,
                    common_epoch,
                    dwell_days_after_capture=2.0,
                    max_phase_burn_mps=phase_limit,
                )
                for permutation in itertools.permutations(route)
            ]
        phase_best = min(
            phase_routes,
            key=lambda item: (item["inter_target_dv_mps"], item["inter_target_elapsed_days"]),
        )
        phase_burn_sensitivity[str(phase_limit)] = {
            "route": phase_best["route"],
            "inter_target_dv_mps": phase_best["inter_target_dv_mps"],
            "inter_target_elapsed_days": phase_best["inter_target_elapsed_days"],
        }

    # Planning assumptions kept separate from catalog-derived results.
    first_target_acquisition_days = 90.0
    first_target_acquisition_dv_mps = 30.0
    final_disposal_operations_days = 7.0
    rpo_dv_per_target_mps = 5.0
    delta_v_reserve_fraction = 0.20
    q_target_chain = 0.75
    p_final_disposal = 0.99
    total_mission_days = (
        first_target_acquisition_days
        + best_timed_by_dv["inter_target_elapsed_days"]
        + final_disposal_operations_days
    )
    delta_v_before_reserve = (
        best_timed_by_dv["inter_target_dv_mps"]
        + first_target_acquisition_dv_mps
        + 5.0 * rpo_dv_per_target_mps
        + deorbit["burn_mps"]
    )
    design_delta_v = delta_v_before_reserve * (1.0 + delta_v_reserve_fraction)
    expected_continue = 5.0 * q_target_chain * p_final_disposal
    expected_abort = p_final_disposal * sum(q_target_chain**k for k in range(1, 6))
    density_scenarios = {}
    ordered_targets = [route_by_id[norad] for norad in best_timed_by_dv["route"]]
    for density in (1.4, 2.8, 7.9):
        masses = [sphere_proxy_mass_kg(t.rcs_equiv_d_cm, density) for t in ordered_targets]
        density_scenarios[str(density)] = {
            "nominal_mass_kg": sum(masses),
            "effective_mass_continue_kg": q_target_chain * p_final_disposal * sum(masses),
            "effective_mass_abort_kg": p_final_disposal
            * sum(mass * q_target_chain**k for k, mass in enumerate(masses, start=1)),
        }
    probability_sensitivity = {}
    for q_value in (0.60, 0.75, 0.90):
        for disposal_value in (0.90, 0.99):
            key = f"q={q_value:.2f},pdisp={disposal_value:.2f}"
            probability_sensitivity[key] = {
                "continue_after_safe_failure": 5.0 * q_value * disposal_value,
                "abort_after_failure": disposal_value
                * sum(q_value**k for k in range(1, 6)),
            }
    calendar_sensitivity = {}
    for label, acquisition_days, disposal_days in (
        ("mature_optimistic", 30.0, 3.0),
        ("benchmark", 90.0, 7.0),
        ("demonstration_conservative", 180.0, 14.0),
    ):
        days = acquisition_days + best_timed_by_dv["inter_target_elapsed_days"] + disposal_days
        calendar_sensitivity[label] = {
            "total_days": days,
            "nominal_rate_per_year": 5.0 * 365.0 / days,
            "effective_rate_q075_pdisp099_continue": expected_continue * 365.0 / days,
            "effective_rate_q075_pdisp099_abort": expected_abort * 365.0 / days,
        }
    mission_metrics = {
        "planning_assumptions_not_catalog_data": {
            "first_target_acquisition_days": first_target_acquisition_days,
            "first_target_acquisition_dv_mps": first_target_acquisition_dv_mps,
            "final_disposal_operations_days": final_disposal_operations_days,
            "rpo_dv_per_target_mps": rpo_dv_per_target_mps,
            "delta_v_reserve_fraction": delta_v_reserve_fraction,
            "per_target_conditional_success_q": q_target_chain,
            "final_disposal_success_probability": p_final_disposal,
        },
        "total_mission_days": total_mission_days,
        "nominal_targets": 5,
        "nominal_rate_targets_per_year": 5.0 * 365.0 / total_mission_days,
        "effective_targets_continue_after_safe_failure": expected_continue,
        "effective_rate_continue_per_year": expected_continue * 365.0 / total_mission_days,
        "effective_targets_abort_after_failure": expected_abort,
        "effective_rate_abort_per_year": expected_abort * 365.0 / total_mission_days,
        "delta_v_before_reserve_mps": delta_v_before_reserve,
        "design_delta_v_with_20pct_reserve_mps": design_delta_v,
        "sphere_proxy_mass_sensitivity": density_scenarios,
        "probability_sensitivity": probability_sensitivity,
        "calendar_sensitivity": calendar_sensitivity,
        "phase_burn_sensitivity": phase_burn_sensitivity,
    }
    result = {
        "retrieved_utc": retrieved,
        "model": {
            "target_filter": "FENGYUN 1C DEB; RCS-equivalent diameter 8-12 cm; perigee >=700 km; apogee <=900 km; e<=0.02; GP age <=3 days",
            "common_epoch": common_epoch.isoformat(),
            "element_alignment": "sgp4 2.25 propagation of published OMM mean elements to common epoch; TEME states",
            "route": "nearest-neighbour graph exhaustive depth-5 path search",
            "transfer": "equivalent-circular two-impulse Hohmann; full plane change combined at higher radius",
            "timed_route": "SGP4 mutual-plane crossing search + equivalent-circular Hohmann/plane change + <=10 m/s per-burn phasing; 2 day RPO/capture/stow dwell at each target",
            "exclusions": "No finite burns, precision ephemeris/covariance, attitude/tumble dynamics, contact dynamics, or ground-network constraints",
        },
        "eligible_target_count": len(targets),
        "selected_targets": [asdict(t) for t in route],
        "legs": legs,
        "route_transfer_dv_mps": route_dv,
        "timed_route_minimum_dv": best_timed_by_dv,
        "timed_route_minimum_time": best_timed_by_time,
        "last_target_deorbit": deorbit,
        "mission_metrics": mission_metrics,
    }
    (out_dir / "screening_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
