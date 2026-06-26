"""
Garage Door Spring Engineering Engine
======================================
Supports both DUAL spring (paired) and SINGLE spring door calculations.

FORMULA (same for both modes):
    CDT   = (door_height_inches / HEIGHT_CIRC) + radius_offset[drum][radius]
    TIPP  = door_weight_lbs / CDT

DUAL spring:   match target TIPP against combined IPPT whitelist tables.
SINGLE spring: match target TIPP against individual spring IPPT values,
               AND check if any dual pair also qualifies (upgrade option).

Whitelist tables transcribed directly from physical SSC Combined IPPT Chart.
No cross-tier pairing. No heuristic ratio filtering.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# SSC Formula Constants
# ---------------------------------------------------------------------------

HEIGHT_CIRC = 30.307021

DRUM_PROFILES = {
    "d400_96":      {"label": "Canimex / TF D-400-96 (Standard Residential)"},
    "d400_144":     {"label": "Canimex D-400-144 (Large Drum)"},
    "standard_4in": {"label": "Standard 4-inch Drum"},
    "standard_2in": {"label": "Standard 2-inch Drum"},
}

RADIUS_OFFSETS = {
    "d400_96":      {12: 0.584622, 15: 0.717743},
    "d400_144":     {12: 0.533407, 15: 0.664401},
    "standard_4in": {12: 0.584622, 15: 0.717743},
    "standard_2in": {12: 0.584622, 15: 0.717743},
}

DEFAULT_TOLERANCE = 3.0

# ---------------------------------------------------------------------------
# SINGLE SPRING IPPT VALUES
# From the IPPT column on the right side of the physical SSC chart.
# ---------------------------------------------------------------------------

STANDARD_CYCLE_2IN_SINGLES = [
    ("207x22", 24.16),
    ("218x23", 30.28),
    ("225x24", 33.54),
]

HIGH_CYCLE_2IN_SINGLES = [
    ("207x28", 18.78),
    ("218x27", 25.60),
    ("234x30", 32.24),
    ("243x31", 37.83),
    ("250x32", 41.51),
    ("262x36", 46.71),
]

MAX_LIFE_2IN_SINGLES = [
    ("218x36.5", 18.73),
    ("234x39",   24.57),
    ("250x44",   29.86),
    ("262x51",   32.61),
    ("273x57.5", 34.95),
    ("289x62.5", 42.43),
    ("295x59",   49.77),
]

# ---------------------------------------------------------------------------
# DUAL SPRING PAIR WHITELIST
# Transcribed directly from physical SSC Combined IPPT Chart.
# Whitespace cells are absent — structurally impossible to suggest them.
# ---------------------------------------------------------------------------

STANDARD_CYCLE_2IN_PAIRS = [
    ("207x22", "207x22", 48.32),
    ("207x22", "218x23", 54.44),
    ("218x23", "218x23", 60.56),
    ("207x22", "225x24", 57.70),
    ("218x23", "225x24", 63.82),
    ("225x24", "225x24", 67.08),
]

HIGH_CYCLE_2IN_PAIRS = [
    ("207x28", "207x28", 37.56),
    ("207x28", "218x27", 44.38),
    ("218x27", "218x27", 51.20),
    ("207x28", "234x30", 51.02),
    ("218x27", "234x30", 57.84),
    ("234x30", "234x30", 64.48),
    ("207x28", "243x31", 56.61),  # corrected from 56.81
    ("218x27", "243x31", 63.43),
    ("234x30", "243x31", 70.07),
    ("243x31", "243x31", 75.66),
    ("207x28", "250x32", 60.28),
    ("218x27", "250x32", 67.11),
    ("234x30", "250x32", 73.75),
    ("243x31", "250x32", 79.34),
    ("250x32", "250x32", 83.02),
    ("207x28", "262x36", 65.49),
    ("218x27", "262x36", 72.31),
    ("234x30", "262x36", 78.95),
    ("243x31", "262x36", 84.54),
    ("250x32", "262x36", 88.22),
    ("262x36", "262x36", 93.42),
]

MAX_LIFE_2IN_PAIRS = [
    ("218x36.5", "218x36.5", 37.46),
    ("218x36.5", "234x39",   43.30),
    ("234x39",   "234x39",   49.14),
    ("218x36.5", "250x44",   48.59),
    ("234x39",   "250x44",   54.43),
    ("250x44",   "250x44",   59.72),
    ("218x36.5", "262x51",   51.34),
    ("234x39",   "262x51",   57.18),
    ("250x44",   "262x51",   62.47),
    ("262x51",   "262x51",   65.22),
    ("218x36.5", "273x57.5", 53.68),
    ("234x39",   "273x57.5", 59.52),
    ("250x44",   "273x57.5", 64.81),
    ("262x51",   "273x57.5", 67.56),
    ("273x57.5", "273x57.5", 69.90),
    ("218x36.5", "289x62.5", 61.16),
    ("234x39",   "289x62.5", 67.00),
    ("250x44",   "289x62.5", 72.29),
    ("262x51",   "289x62.5", 75.04),
    ("273x57.5", "289x62.5", 77.38),
    ("289x62.5", "289x62.5", 84.86),
    ("218x36.5", "295x59",   68.50),
    ("234x39",   "295x59",   74.63),
    ("250x44",   "295x59",   79.83),
    ("262x51",   "295x59",   82.38),
    ("273x57.5", "295x59",   84.72),
    ("289x62.5", "295x59",   92.20),  # reinstated - valid per clean chart photo
    ("295x59",   "295x59",   99.54),
]

# Tier registry — (label, pairs, singles)
TIERS = {
    "standard": ("Standard Cycle 2\"",  STANDARD_CYCLE_2IN_PAIRS, STANDARD_CYCLE_2IN_SINGLES),
    "high":     ("High Cycle 2\"",       HIGH_CYCLE_2IN_PAIRS,     HIGH_CYCLE_2IN_SINGLES),
    "max_life": ("Max Life 2\"",         MAX_LIFE_2IN_PAIRS,       MAX_LIFE_2IN_SINGLES),
}

TIER_LABELS = {k: v[0] for k, v in TIERS.items()}

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class SpringMatch:
    rank: int
    tier_key: str
    tier_label: str
    spring1_code: str
    spring2_code: str   # "(single)" for single spring results
    ippt: float         # combined for dual, individual for single
    delta: float
    abs_delta: float
    is_single: bool


@dataclass
class TierResult:
    tier_key: str
    tier_label: str
    match: Optional[SpringMatch]
    in_range: bool


@dataclass
class CalculationResult:
    door_weight_lbs: float
    door_height_ft: float
    door_height_inches: float
    track_radius: int
    drum_model: str
    drum_label: str
    cable_drum_turns: float
    track_factor: float
    target_ippt: float
    tolerance: float
    lower_bound: float
    upper_bound: float
    is_single_spring: bool
    # Primary results (single or dual depending on mode)
    tier_results: list
    all_matches: list
    # Dual upgrade suggestions (only populated when is_single_spring=True)
    dual_upgrade_tier_results: list = field(default_factory=list)
    dual_upgrade_matches: list = field(default_factory=list)
    notes: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core Calculation
# ---------------------------------------------------------------------------

def calculate_target_ippt(
    door_weight_lbs: float,
    door_height_ft: float,
    track_radius: int = 12,
    drum_model: str = "d400_96",
    single_spring: bool = False,
) -> CalculationResult:
    notes = []

    if track_radius not in (12, 15):
        raise ValueError(f"Track radius must be 12 or 15. Got: {track_radius}")
    if drum_model not in DRUM_PROFILES:
        raise ValueError(f"Unknown drum model: {drum_model}")

    drum_label = DRUM_PROFILES[drum_model]["label"]
    door_height_inches = round(door_height_ft * 12, 2)

    radius_offset = RADIUS_OFFSETS[drum_model][track_radius]
    turns = round(door_height_inches / HEIGHT_CIRC + radius_offset, 4)
    notes.append(f"CDT = {door_height_inches}\" / {HEIGHT_CIRC} + {radius_offset} = {turns} turns")

    target = round(door_weight_lbs / turns, 2)
    lower  = round(target - DEFAULT_TOLERANCE, 2)
    upper  = round(target + DEFAULT_TOLERANCE, 2)

    mode = "single spring" if single_spring else "combined dual"
    notes.append(f"Target IPPT ({mode}) = {door_weight_lbs} / {turns} = {target}")
    notes.append(f"Match window: {lower} – {upper} IPPT (±{DEFAULT_TOLERANCE})")

    if single_spring:
        primary_matches, primary_tiers = _find_single_matches(target, lower, upper)
        upgrade_matches, upgrade_tiers  = _find_pair_matches(target, lower, upper)
        has_upgrade = any(tr.in_range for tr in upgrade_tiers)
        if has_upgrade:
            notes.append("Qualifies for dual spring upgrade.")
    else:
        primary_matches, primary_tiers = _find_pair_matches(target, lower, upper)
        upgrade_matches, upgrade_tiers  = [], []

    return CalculationResult(
        door_weight_lbs=door_weight_lbs,
        door_height_ft=door_height_ft,
        door_height_inches=door_height_inches,
        track_radius=track_radius,
        drum_model=drum_model,
        drum_label=drum_label,
        cable_drum_turns=turns,
        track_factor=radius_offset,
        target_ippt=target,
        tolerance=DEFAULT_TOLERANCE,
        lower_bound=lower,
        upper_bound=upper,
        is_single_spring=single_spring,
        tier_results=primary_tiers,
        all_matches=primary_matches,
        dual_upgrade_tier_results=upgrade_tiers,
        dual_upgrade_matches=upgrade_matches,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Matching Helpers
# ---------------------------------------------------------------------------

def _find_pair_matches(target, lower, upper):
    all_in_range = []
    tier_results = []

    for tier_key, (tier_label, pairs, _singles) in TIERS.items():
        candidates = []
        for s1, s2, ippt in pairs:
            delta     = round(ippt - target, 2)
            abs_delta = abs(delta)
            in_range  = lower <= ippt <= upper
            c = dict(tier_key=tier_key, tier_label=tier_label,
                     spring1_code=s1, spring2_code=s2,
                     ippt=ippt, delta=delta, abs_delta=abs_delta,
                     in_range=in_range, is_single=False)
            candidates.append(c)
            if in_range:
                all_in_range.append(c)

        candidates.sort(key=lambda x: x["abs_delta"])
        best_list = [c for c in candidates if c["in_range"]]
        best = _to_match(best_list[0], rank=1) if best_list else None
        tier_results.append(TierResult(tier_key=tier_key, tier_label=tier_label,
                                       match=best, in_range=best is not None))

    all_in_range.sort(key=lambda x: x["abs_delta"])
    flat = [_to_match(c, rank=i+1) for i, c in enumerate(all_in_range)]
    return flat, tier_results


def _find_single_matches(target, lower, upper):
    all_in_range = []
    tier_results = []

    for tier_key, (tier_label, _pairs, singles) in TIERS.items():
        candidates = []
        for code, ippt in singles:
            delta     = round(ippt - target, 2)
            abs_delta = abs(delta)
            in_range  = lower <= ippt <= upper
            c = dict(tier_key=tier_key, tier_label=tier_label,
                     spring1_code=code, spring2_code="(single)",
                     ippt=ippt, delta=delta, abs_delta=abs_delta,
                     in_range=in_range, is_single=True)
            candidates.append(c)
            if in_range:
                all_in_range.append(c)

        candidates.sort(key=lambda x: x["abs_delta"])
        best_list = [c for c in candidates if c["in_range"]]
        best = _to_match(best_list[0], rank=1) if best_list else None
        tier_results.append(TierResult(tier_key=tier_key, tier_label=tier_label,
                                       match=best, in_range=best is not None))

    all_in_range.sort(key=lambda x: x["abs_delta"])
    flat = [_to_match(c, rank=i+1) for i, c in enumerate(all_in_range)]
    return flat, tier_results


def _to_match(c: dict, rank: int) -> SpringMatch:
    return SpringMatch(
        rank=rank,
        tier_key=c["tier_key"],
        tier_label=c["tier_label"],
        spring1_code=c["spring1_code"],
        spring2_code=c["spring2_code"],
        ippt=c["ippt"],
        delta=c["delta"],
        abs_delta=c["abs_delta"],
        is_single=c["is_single"],
    )


# ---------------------------------------------------------------------------
# CLI Test Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 70)
    print(" SPRING ENGINE — DUAL + SINGLE SPRING MODE")
    print("=" * 70)

    print("\n--- DUAL SPRING TESTS ---")
    dual_tests = [
        (185, 7.0,  12, "d400_96",  55.12, "185lb/7ft/12/D400-96"),
        (235, 8.0,  12, "d400_144", 63.60, "235lb/8ft/12/D400-144"),
        (253, 9.0,  15, "d400_144", 60.13, "253lb/9ft/15/D400-144"),
        (302, 10.0, 12, "d400_144", 67.38, "302lb/10ft/12/D400-144"),
    ]
    for w, h, r, drum, exp, label in dual_tests:
        res = calculate_target_ippt(w, h, r, drum, single_spring=False)
        diff = abs(res.target_ippt - exp)
        status = "PASS" if diff <= 0.40 else "FAIL"
        print(f"\n  {label} [{status}] target={res.target_ippt} expected={exp} diff={diff:.3f}")
        for tr in res.tier_results:
            if tr.in_range:
                m = tr.match
                print(f"    [{tr.tier_label}]: {m.spring1_code} + {m.spring2_code} = {m.ippt} (delta {m.delta:+.2f})")
            else:
                print(f"    [{tr.tier_label}]: out of range")

    print("\n--- SINGLE SPRING TESTS (with dual upgrade check) ---")
    single_tests = [
        (100, 7.0, 12, "d400_96",  "100lb/7ft/12/D400-96"),
        (120, 7.0, 12, "d400_96",  "120lb/7ft/12/D400-96"),
        (140, 8.0, 12, "d400_96",  "140lb/8ft/12/D400-96"),
        (160, 8.0, 15, "d400_144", "160lb/8ft/15/D400-144"),
    ]
    for w, h, r, drum, label in single_tests:
        res = calculate_target_ippt(w, h, r, drum, single_spring=True)
        print(f"\n  {label}: target={res.target_ippt}")
        print("  Single spring options:")
        for tr in res.tier_results:
            if tr.in_range:
                m = tr.match
                print(f"    [{tr.tier_label}]: {m.spring1_code} = {m.ippt} IPPT (delta {m.delta:+.2f})")
            else:
                print(f"    [{tr.tier_label}]: out of range")
        has_upgrade = any(tr.in_range for tr in res.dual_upgrade_tier_results)
        if has_upgrade:
            print("  *** Qualifies for dual spring upgrade ***")
            for tr in res.dual_upgrade_tier_results:
                if tr.in_range:
                    m = tr.match
                    print(f"    [{tr.tier_label}]: {m.spring1_code} + {m.spring2_code} = {m.ippt} (delta {m.delta:+.2f})")
        else:
            print("  (No dual spring upgrade available)")

    print("\n" + "=" * 70)
    print(" DONE")
    print("=" * 70)
