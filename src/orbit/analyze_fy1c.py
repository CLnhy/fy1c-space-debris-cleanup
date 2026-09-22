from __future__ import annotations

import csv
import itertools
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"

sys.path.insert(0, str(ROOT / "vendor" / "sgp4_local"))

import numpy as np
from sgp4 import omm
from sgp4.api import Satrec, jday

MU = 398600.4418  # km^3/s^2
RE = 6378.137  # km
COMMON_EPOCH = datetime(2026, 9, 2, 0, 0, 0, tzinfo=timezone.utc)
RCS_MIN = math.pi * (0.08 / 2) ** 2
RCS_MAX = math.pi * (0.12 / 2) ** 2


def jd_fr(dt: datetime) -> tuple[float, float]:
    sec = dt.second + dt.microsecond / 1e6
    return jday(dt.year, dt.month, dt.day, dt.hour, dt.minute, sec)


def rv_to_elements(r: np.ndarray, v: np.ndarray) -> dict[str, float]:
    rmag = np.linalg.norm(r)
    vmag = np.linalg.norm(v)
    h = np.cross(r, v)
    hmag = np.linalg.norm(h)
    nvec = np.cross(np.array([0.0, 0.0, 1.0]), h)
    nmag = np.linalg.norm(nvec)
    evec = ((vmag * vmag - MU / rmag) * r - np.dot(r, v) * v) / MU
    e = np.linalg.norm(evec)
    a = 1.0 / (2.0 / rmag - vmag * vmag / MU)
    inc = math.acos(np.clip(h[2] / hmag, -1.0, 1.0))
    raan = math.atan2(nvec[1], nvec[0]) % (2 * math.pi)
    # Argument of latitude is well conditioned for near-circular objects.
    u = math.atan2(
        np.dot(np.cross(nvec, r), h) / (nmag * hmag * rmag),
        np.dot(nvec, r) / (nmag * rmag),
    ) % (2 * math.pi)
    return {
        "a_km": a,
        "e_osc": e,
        "i_deg": math.degrees(inc),
        "raan_deg": math.degrees(raan),
        "u_deg": math.degrees(u),
        "r_km": rmag,
        "v_kms": vmag,
        "period_min": 2 * math.pi * math.sqrt(a**3 / MU) / 60,
        "hx": h[0] / hmag,
        "hy": h[1] / hmag,
        "hz": h[2] / hmag,
    }


def plane_angle_deg(a: dict, b: dict) -> float:
    ha = np.array([a["hx"], a["hy"], a["hz"]])
    hb = np.array([b["hx"], b["hy"], b["hz"]])
    return math.degrees(math.acos(np.clip(np.dot(ha, hb), -1.0, 1.0)))


def direct_plane_dv_ms(a: dict, b: dict) -> float:
    psi = math.radians(plane_angle_deg(a, b))
    rbar = 0.5 * (a["a_km"] + b["a_km"])
    vbar = math.sqrt(MU / rbar)
    return 2 * vbar * math.sin(psi / 2) * 1000


def hohmann(a: dict, b: dict) -> tuple[float, float]:
    r1, r2 = a["a_km"], b["a_km"]
    v1 = math.sqrt(MU / r1)
    v2 = math.sqrt(MU / r2)
    at = (r1 + r2) / 2
    dv1 = abs(v1 * (math.sqrt(2 * r2 / (r1 + r2)) - 1))
    dv2 = abs(v2 * (1 - math.sqrt(2 * r1 / (r1 + r2))))
    tof_min = math.pi * math.sqrt(at**3 / MU) / 60
    return (dv1 + dv2) * 1000, tof_min


gp = json.loads((DATA_RAW / "fy1c_gp.json").read_text(encoding="utf-8"))
satcat = json.loads((DATA_RAW / "fy1c_satcat.json").read_text(encoding="utf-8"))
gp_by_id = {int(x["NORAD_CAT_ID"]): x for x in gp}

selected = []
jd, fr = jd_fr(COMMON_EPOCH)
for sc in satcat:
    try:
        norad = int(sc["NORAD_CAT_ID"])
        rcs = float(sc["RCS"])
        perigee = float(sc["PERIGEE"])
        apogee = float(sc["APOGEE"])
    except (TypeError, ValueError, KeyError):
        continue
    field = gp_by_id.get(norad)
    if field is None:
        continue
    if sc.get("OBJECT_TYPE") != "DEB":
        continue
    if not (RCS_MIN <= rcs <= RCS_MAX):
        continue
    if not (700 <= perigee <= 900 and 700 <= apogee <= 900):
        continue
    # Keep current-enough element sets; old GP solutions are poor route inputs.
    epoch = datetime.fromisoformat(field["EPOCH"]).replace(tzinfo=timezone.utc)
    age_days = (COMMON_EPOCH - epoch).total_seconds() / 86400
    if abs(age_days) > 5:
        continue
    sat = Satrec()
    omm.initialize(sat, field)
    err, r, v = sat.sgp4(jd, fr)
    if err:
        continue
    elem = rv_to_elements(np.array(r), np.array(v))
    selected.append(
        {
            **elem,
            "norad": norad,
            "object_id": sc["OBJECT_ID"],
            "rcs_m2": rcs,
            "d_eq_cm": 200 * math.sqrt(rcs / math.pi),
            "perigee_cat_km": perigee,
            "apogee_cat_km": apogee,
            "gp_epoch": field["EPOCH"],
            "age_days": age_days,
            "mean_motion": float(field["MEAN_MOTION"]),
            "mean_e": float(field["ECCENTRICITY"]),
            "mean_i": float(field["INCLINATION"]),
            "mean_raan": float(field["RA_OF_ASC_NODE"]),
            "mean_argp": float(field["ARG_OF_PERICENTER"]),
            "mean_M": float(field["MEAN_ANOMALY"]),
        }
    )

print("RCS limits", RCS_MIN, RCS_MAX)
print("candidate count", len(selected))

# Pair-cost matrix using separately interpretable ideal lower-bound components.
n = len(selected)
edge = {}
for i, j in itertools.combinations(range(n), 2):
    dp = direct_plane_dv_ms(selected[i], selected[j])
    dh, tof = hohmann(selected[i], selected[j])
    edge[i, j] = {"plane": dp, "height": dh, "sum": dp + dh, "tof": tof}


def E(i: int, j: int) -> dict[str, float]:
    return edge[tuple(sorted((i, j)))]


# Enumerate compact five-object neighborhoods; solve the shortest Hamiltonian path
# within each neighborhood. This avoids all C(n,5) combinations.
best = None
for center in range(n):
    neigh = sorted(
        (j for j in range(n) if j != center), key=lambda j: E(center, j)["sum"]
    )[:12]
    pool = [center] + neigh
    for combo_others in itertools.combinations(neigh, 4):
        combo = (center,) + combo_others
        for perm in itertools.permutations(combo):
            # Remove reverse-path duplication.
            if perm[0] > perm[-1]:
                continue
            total = sum(E(perm[k], perm[k + 1])["sum"] for k in range(4))
            if best is None or total < best[0]:
                best = (total, perm)

assert best is not None
_, route = best
print("best route index", route)

print("\nROUTE OBJECTS")
for k, idx in enumerate(route, 1):
    x = selected[idx]
    print(
        k,
        x["norad"],
        x["object_id"],
        f'RCS={x["rcs_m2"]:.4f}',
        f'd={x["d_eq_cm"]:.2f}cm',
        f'cat={x["perigee_cat_km"]:.0f}-{x["apogee_cat_km"]:.0f}km',
        f'a={x["a_km"]:.3f}',
        f'e={x["e_osc"]:.6f}',
        f'i={x["i_deg"]:.6f}',
        f'raan={x["raan_deg"]:.6f}',
        f'u={x["u_deg"]:.3f}',
        f'T={x["period_min"]:.6f}min',
        f'GP={x["gp_epoch"]}',
    )

print("\nLEGS")
totals = {"plane": 0.0, "height": 0.0, "sum": 0.0, "tof": 0.0}
for a_idx, b_idx in zip(route, route[1:]):
    a, b = selected[a_idx], selected[b_idx]
    data = E(a_idx, b_idx)
    psi = plane_angle_deg(a, b)
    print(
        a["norad"], "->", b["norad"],
        f"plane={psi:.6f}deg",
        f"dv_plane={data['plane']:.3f}m/s",
        f"dv_height={data['height']:.3f}m/s",
        f"ideal_sum={data['sum']:.3f}m/s",
        f"Hohmann_tof={data['tof']:.3f}min",
    )
    for key in totals:
        totals[key] += data[key]
print("totals", totals)


def show_route(label: str, route_to_show: tuple[int, ...]) -> None:
    print(f"\n{label}")
    for k, idx in enumerate(route_to_show, 1):
        x = selected[idx]
        print(
            k,
            x["norad"],
            x["object_id"],
            f'RCS={x["rcs_m2"]:.4f}',
            f'd={x["d_eq_cm"]:.2f}cm',
            f'cat={x["perigee_cat_km"]:.0f}-{x["apogee_cat_km"]:.0f}km',
            f'a={x["a_km"]:.3f}',
            f'e={x["e_osc"]:.6f}',
            f'i={x["i_deg"]:.6f}',
            f'raan={x["raan_deg"]:.6f}',
            f'u={x["u_deg"]:.3f}',
            f'T={x["period_min"]:.6f}min',
            f'GP={x["gp_epoch"]}',
        )
    route_totals = {"plane": 0.0, "height": 0.0, "sum": 0.0, "tof": 0.0}
    for a_idx, b_idx in zip(route_to_show, route_to_show[1:]):
        a, b = selected[a_idx], selected[b_idx]
        data = E(a_idx, b_idx)
        psi = plane_angle_deg(a, b)
        print(
            a["norad"], "->", b["norad"],
            f"plane={psi:.6f}deg",
            f"dv_plane={data['plane']:.3f}m/s",
            f"dv_height={data['height']:.3f}m/s",
            f"ideal_sum={data['sum']:.3f}m/s",
            f"Hohmann_tof={data['tof']:.3f}min",
        )
        for key in route_totals:
            route_totals[key] += data[key]
    print("route totals", route_totals)


# Also preserve the previously nominated NORAD 30284 as the first captured target.
anchor = next(i for i, x in enumerate(selected) if x["norad"] == 30284)
neighbors = sorted(
    (j for j in range(n) if j != anchor), key=lambda j: E(anchor, j)["sum"]
)[:20]
anchor_best = None
for combo in itertools.combinations(neighbors, 4):
    # 30284 is the fixed first target; optimize the remaining order.
    for tail in itertools.permutations(combo):
        candidate_route = (anchor,) + tail
        cost = sum(E(candidate_route[k], candidate_route[k + 1])["sum"] for k in range(4))
        if anchor_best is None or cost < anchor_best[0]:
            anchor_best = (cost, candidate_route)
assert anchor_best
show_route("ANCHORED ROUTE STARTING AT 30284", anchor_best[1])

DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
with (DATA_PROCESSED / "fy1c_filtered.csv").open(
    "w", newline="", encoding="utf-8-sig"
) as f:
    writer = csv.DictWriter(f, fieldnames=list(selected[0].keys()))
    writer.writeheader()
    writer.writerows(selected)
