"""
Garage Door Spring Engineering Engine
======================================
Calculates the Target Combined IPPT for a door using the SSC formula,
then matches against an explicit whitelist of valid spring pairs read
directly from the physical SSC Combined IPPT chart.

CORRECT FORMULA (verified against SSC Spring Engineering App, all heights):
    CDT   = (door_height_inches / HEIGHT_CIRC) + radius_offset[drum][radius]
    TIPP  = door_weight_lbs / CDT

HEIGHT_CIRC = 30.307021 (constant for all drums)

Radius offsets per (drum_model, track_radius):
    D400-96  / 12" = 0.584622
    D400-96  / 15" = 0.717743
    D400-144 / 12" = 0.533407
    D400-144 / 15" = 0.664401

VERIFIED against SSC app across 7ft–10ft doors, all within ±0.40 IPPT.

NOTE on SSC app "Turn" field:
    The "Turn" displayed in the SSC app is MAX SPRING WIND TURNS,
    not CDT. Our CDT formula is correct regardless.

PAIR MATCHING:
    Only pairs explicitly listed in the physical SSC Combined IPPT Chart
    are valid. Whitespace cells in the chart = invalid pair, never suggested.
    No cross-tier pairing (Low Cycle + High Cycle = invalid).
    The MAX_IPPT_RATIO heuristic has been removed entirely.
"""

from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# SSC Formula Constants
# ---------------------------------------------------------------------------

HEIGHT_CIRC = 30.307021

DRUM_PROFILES = {
    "d400_96":  {"label": "Canimex / TF D-400-96 (Standard Residential)"},
    "d400_144": {"label": "Canimex D-400-144 (Large Drum)"},
}

RADIUS_OFFSETS = {
    "d400_96":  {12: 0.584622, 15: 0.717743},
    "d400_144": {12: 0.533407, 15: 0.664401},
}

DEFAULT_TOLERANCE = 3.0

# ---------------------------------------------------------------------------
# HARDCODED SPRING PAIR TABLES
# Transcribed directly from the physical SSC Combined IPPT Chart.
# Only cells with a printed number are listed — whitespace = invalid pair.
# Pairs are stored with smaller spring first for dedup, but matching
# allows either order.
# ---------------------------------------------------------------------------

# Each entry: (spring1, spring2, combined_ippt)
# spring1 <= spring2 by convention (matched or mixed pair)

LOW_CYCLE_2IN_PAIRS = [
    # Chart springs: 207x22, 218x23, 225x24
    # Individual IPPT: 24.16, 30.28, 33.54
    ("207x22", "207x22", 48.32),
    ("207x22", "218x23", 54.44),
    ("218x23", "218x23", 60.56),
    ("207x22", "225x24", 57.70),
    ("218x23", "225x24", 63.82),
    ("225x24", "225x24", 67.08),
]

HIGH_CYCLE_2IN_PAIRS = [
    # Chart springs: 207x28, 218x27, 234x30, 243x31, 250x32, 262x36
    ("207x28", "207x28", 37.56),
    ("207x28", "218x27", 44.38),
    ("218x27", "218x27", 51.20),
    ("207x28", "234x30", 51.02),
    ("218x27", "234x30", 57.84),
    ("234x30", "234x30", 64.48),
    ("207x28", "243x31", 56.81),
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
    # Chart springs: 218x36.5, 234x39, 250x44, 262x51, 273x57.5, 289x62.5, 295x59
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
    ("295x59",   "295x59",   99.54),
]

# Tier definitions: maps tier_key -> (label, pairs_list)
TIERS = {
    "economy":  ("Economy (Low Cycle ~10k)",   LOW_CYCLE_2IN_PAIRS),
    "mid":      ("Mid-Grade (High Cycle ~20k)", HIGH_CYCLE_2IN_PAIRS),
    "max_life": ("Max Life (~100k)",            MAX_LIFE_2IN_PAIRS),
}

# For engine.py compatibility
TIER_CATEGORIES = {
    "economy":  ["low_cycle_2in"],
    "mid":      ["high_cycle_2in"],
    "max_life": ["max_life_2in"],
}
TIER_LABELS = {k: v[0] for k, v in TIERS.items()}

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class SpringPairMatch:
    rank: int
    category: str
    category_label: str
    spring1_code: str
    spring2_code: str
    combined_ippt: float
    delta: float
    abs_delta: float


@dataclass
class TierResult:
    tier_key: str
    tier_label: str
    match: Optional[SpringPairMatch]
    in_range: bool


@dataclass
class CalculationResult:
    door_weight_lbs: float
    door_height_ft: float
    door_height_inches: float
    track_radius: int
    drum_model: str
    drum_label: str
    drum_circumference: float
    cable_drum_turns: float
    track_factor: float
    target_combined_ippt: float
    tolerance: float
    lower_bound: float
    upper_bound: float
    matches: list
    tier_results: list
    notes: list


# ---------------------------------------------------------------------------
# Core Calculation
# ---------------------------------------------------------------------------

def calculate_target_ippt(
    door_weight_lbs: float,
    door_height_ft: float,
    track_radius: int = 12,
    drum_model: str = "d400_96",
) -> CalculationResult:
    """
    Calculate Target Combined IPPT and find valid spring pairs.

    SSC Formula:
        CDT  = (height_inches / HEIGHT_CIRC) + radius_offset[drum][radius]
        TIPP = weight / CDT

    Pair matching uses only the explicit SSC chart whitelist —
    no pairs are computed from individual spring IPPTs.
    """
    notes = []

    if track_radius not in (12, 15):
        raise ValueError(f"Track radius must be 12 or 15. Got: {track_radius}")
    if drum_model not in DRUM_PROFILES:
        raise ValueError(f"Unknown drum model: {drum_model}. Valid options: {list(DRUM_PROFILES)}")

    drum_label = DRUM_PROFILES[drum_model]["label"]
    door_height_inches = round(door_height_ft * 12, 2)

    radius_offset = RADIUS_OFFSETS[drum_model][track_radius]
    turns = round(door_height_inches / HEIGHT_CIRC + radius_offset, 4)
    notes.append(
        f"CDT = {door_height_inches}\" / {HEIGHT_CIRC} + {radius_offset} "
        f"(offset for {drum_model}/{track_radius}\" radius) = {turns} turns"
    )

    target = round(door_weight_lbs / turns, 2)
    notes.append(f"TIPP = {door_weight_lbs} lbs / {turns} turns = {target}")

    lower = round(target - DEFAULT_TOLERANCE, 2)
    upper = round(target + DEFAULT_TOLERANCE, 2)
    notes.append(f"Match window: {lower} – {upper} IPPT (±{DEFAULT_TOLERANCE})")

    matches, tier_results = find_pair_matches(target, lower, upper)

    return CalculationResult(
        door_weight_lbs=door_weight_lbs,
        door_height_ft=door_height_ft,
        door_height_inches=door_height_inches,
        track_radius=track_radius,
        drum_model=drum_model,
        drum_label=drum_label,
        drum_circumference=HEIGHT_CIRC,
        cable_drum_turns=turns,
        track_factor=radius_offset,
        target_combined_ippt=target,
        tolerance=DEFAULT_TOLERANCE,
        lower_bound=lower,
        upper_bound=upper,
        matches=matches,
        tier_results=tier_results,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Pair Matching — whitelist only, no heuristics
# ---------------------------------------------------------------------------

def find_pair_matches(target: float, lower_bound: float, upper_bound: float):
    """
    Scan every tier's explicit pair whitelist.
    Only pairs with a printed combined_ippt in the physical SSC chart
    are considered. Whitespace cells and cross-tier pairings are
    structurally impossible here — they were never added to the lists.

    Returns:
        (flat_matches, tier_results)
    """
    all_in_range: list[dict] = []
    tier_results: list[TierResult] = []

    for tier_key, (tier_label, pair_list) in TIERS.items():
        tier_candidates = []

        for s1, s2, combined_ippt in pair_list:
            delta = round(combined_ippt - target, 2)
            abs_delta = abs(delta)
            in_range = lower_bound <= combined_ippt <= upper_bound
            is_matched = (s1 == s2)
            pair_type = "Matched" if is_matched else "Mixed"

            candidate = {
                "category": tier_key,
                "category_label": tier_label,
                "spring1_code": s1,
                "spring2_code": s2,
                "combined_ippt": combined_ippt,
                "delta": delta,
                "abs_delta": abs_delta,
                "in_range": in_range,
                "pair_type": pair_type,
            }
            tier_candidates.append(candidate)
            if in_range:
                all_in_range.append(candidate)

        tier_candidates.sort(key=lambda x: x["abs_delta"])
        in_range_for_tier = [c for c in tier_candidates if c["in_range"]]

        best_match = None
        if in_range_for_tier:
            c = in_range_for_tier[0]
            best_match = SpringPairMatch(
                rank=1,
                category=c["category"],
                category_label=c["category_label"],
                spring1_code=c["spring1_code"],
                spring2_code=c["spring2_code"],
                combined_ippt=c["combined_ippt"],
                delta=c["delta"],
                abs_delta=c["abs_delta"],
            )

        tier_results.append(TierResult(
            tier_key=tier_key,
            tier_label=tier_label,
            match=best_match,
            in_range=best_match is not None,
        ))

    all_in_range.sort(key=lambda x: x["abs_delta"])

    flat_matches = [
        SpringPairMatch(
            rank=i + 1,
            category=c["category"],
            category_label=c["category_label"],
            spring1_code=c["spring1_code"],
            spring2_code=c["spring2_code"],
            combined_ippt=c["combined_ippt"],
            delta=c["delta"],
            abs_delta=c["abs_delta"],
        )
        for i, c in enumerate(all_in_range)
    ]

    return flat_matches, tier_results


# ---------------------------------------------------------------------------
# CLI Test Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 70)
    print(" GARAGE DOOR SPRING ENGINEERING ENGINE v3.0")
    print(" Whitelist-only pair matching — no cross-tier, no invalid pairs")
    print("=" * 70)

    tests = [
        # (weight, height_ft, radius, drum, expected_tipp, label)
        (185, 7.0, 12, "d400_96",  55.12, "185lb/7ft/12/D400-96"),
        (185, 7.0, 12, "d400_144", 55.98, "185lb/7ft/12/D400-144"),
        (185, 8.0, 12, "d400_96",  49.30, "185lb/8ft/12/D400-96"),
        (195, 8.0, 15, "d400_96",  50.27, "195lb/8ft/15/D400-96"),
        (203, 8.0, 12, "d400_96",  54.10, "203lb/8ft/12/D400-96"),
        (235, 8.0, 12, "d400_144", 63.60, "235lb/8ft/12/D400-144"),
        # New 9ft and 10ft data from SSC screenshots
        (209, 9.0, 15, "d400_144", 49.67, "209lb/9ft/15/D400-144"),
        (253, 9.0, 15, "d400_144", 60.13, "253lb/9ft/15/D400-144"),
        (299, 9.0, 15, "d400_144", 71.06, "299lb/9ft/15/D400-144"),
        (302, 10.0, 12, "d400_144", 67.38, "302lb/10ft/12/D400-144"),
        (302, 10.0, 15, "d400_144", 65.67, "302lb/10ft/15/D400-144"),
        (250, 10.0, 15, "d400_144", 54.36, "250lb/10ft/15/D400-144"),
    ]

    all_pass = True
    for weight, height, radius, drum, expected, label in tests:
        r = calculate_target_ippt(weight, height, radius, drum)
        diff = abs(r.target_combined_ippt - expected)
        status = "PASS" if diff <= 0.40 else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"\n{label}")
        print(f"  Expected: {expected}  Got: {r.target_combined_ippt}  Diff: {diff:.4f}  [{status}]")
        print(f"  Window: {r.lower_bound} – {r.upper_bound}")
        for tr in r.tier_results:
            if tr.in_range:
                m = tr.match
                sign = "+" if m.delta >= 0 else ""
                print(f"  [{tr.tier_label}]: {m.spring1_code} + {m.spring2_code}  IPPT={m.combined_ippt}  (delta {sign}{m.delta})")
            else:
                print(f"  [{tr.tier_label}]: OUT OF RANGE")

    print("\n" + "=" * 70)
    print("  ALL TESTS PASSED" if all_pass else "  SOME TESTS FAILED")
    print("=" * 70)

    # Validate: confirm no cross-tier pairs exist
    print("\n=== PAIR TABLE VALIDATION ===")
    all_springs = set()
    for tier_key, (label, pairs) in TIERS.items():
        springs_in_tier = set()
        for s1, s2, _ in pairs:
            springs_in_tier.add(s1)
            springs_in_tier.add(s2)
        overlap = all_springs & springs_in_tier
        if overlap:
            print(f"  WARNING: Springs appear in multiple tiers: {overlap}")
        else:
            print(f"  {label}: {len(pairs)} pairs, {len(springs_in_tier)} springs — no cross-tier overlap ✓")
        all_springs |= springs_in_tier
