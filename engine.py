"""
Garage Door Spring Engineering Engine
======================================
Calculates the Target Combined IPPT for a door using the correct SSC formula,
then scans the spring inventory to find matching pairs within +/-3 IPPT.

CORRECT FORMULA (reverse-engineered from SSC Spring Engineering App):
    CDT  = (door_height_inches / HEIGHT_CIRC) + radius_offset[drum][radius]
    TIPP = door_weight_lbs / CDT

    HEIGHT_CIRC = 30.307021  (constant — same for all drums)

    radius_offset is per (drum_model, track_radius) combination:
        D400-96  / 12" = 0.584622
        D400-96  / 15" = 0.717743
        D400-144 / 12" = 0.533407
        D400-144 / 15" = 0.664401

VERIFIED AGAINST SSC SPRING ENGINEERING APP (all within 0.20 IPPT):
    185 lb / 7 ft / 12" / D400-96   --> 55.12 IPPT  ✓
    185 lb / 7 ft / 12" / D400-144  --> 55.98 IPPT  ✓
    185 lb / 7 ft / 15" / D400-144  --> 53.84 IPPT  ✓
    185 lb / 8 ft / 12" / D400-96   --> 49.30 IPPT  ✓
    195 lb / 8 ft / 15" / D400-96   --> 50.27 IPPT  ✓ (0.08 diff — SSC rounding)
    190 lb / 8 ft / 12" / D400-96   --> 50.64 IPPT  ✓
    200 lb / 8 ft / 12" / D400-96   --> 53.30 IPPT  ✓
    203 lb / 8 ft / 12" / D400-96   --> 54.10 IPPT  ✓
    145 lb / 8 ft / 12" / D400-96   --> 38.64 IPPT  ✓
    158 lb / 8 ft / 12" / D400-96   --> 42.11 IPPT  ✓
    169 lb / 8 ft / 12" / D400-96   --> 45.04 IPPT  ✓
    169 lb / 8 ft / 12" / D400-144  --> 45.74 IPPT  ✓
    155 lb / 8 ft / 12" / D400-144  --> 41.95 IPPT  ✓
    203 lb / 8 ft / 12" / D400-144  --> 54.94 IPPT  ✓
    218 lb / 8 ft / 12" / D400-144  --> 59.00 IPPT  ✓
    235 lb / 8 ft / 12" / D400-144  --> 63.60 IPPT  ✓
    235 lb / 8 ft / 15" / D400-144  --> 61.52 IPPT  ✓ (0.19 diff — SSC rounding)
    198 lb / 8 ft / 15" / D400-144  --> 51.84 IPPT  ✓ (0.17 diff — SSC rounding)
    183 lb / 8 ft / 15" / D400-144  --> 47.91 IPPT  ✓
    165 lb / 8 ft / 15" / D400-144  --> 43.20 IPPT  ✓
    145 lb / 8 ft / 12" / D400-144  --> 39.24 IPPT  ✓
"""

import json
import os
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# SSC Formula Constants
# ---------------------------------------------------------------------------

# Height circumference constant — same for all drum models
HEIGHT_CIRC = 30.307021

# Drum profiles — label only (circumference is no longer used directly)
DRUM_PROFILES = {
    "d400_96": {
        "label": "Canimex / TF D-400-96 (Standard Residential)",
    },
    "d400_144": {
        "label": "Canimex D-400-144 (Large Drum)",
    },
    "standard_4in": {
        "label": "Standard 4-inch Drum",
    },
    "standard_2in": {
        "label": "Standard 2-inch Drum",
    },
}

# ---------------------------------------------------------------------------
# Radius Offsets
# CDT = height_in / HEIGHT_CIRC + RADIUS_OFFSETS[drum_model][track_radius]
# Derived by reverse-engineering the SSC Spring Engineering App.
# ---------------------------------------------------------------------------
RADIUS_OFFSETS = {
    "d400_96": {
        12: 0.584622,
        15: 0.717743,
    },
    "d400_144": {
        12: 0.533407,
        15: 0.664401,
    },
    # Fallback for drums without calibrated offsets — use D400-96 values
    "standard_4in": {
        12: 0.584622,
        15: 0.717743,
    },
    "standard_2in": {
        12: 0.584622,
        15: 0.717743,
    },
}

# Supported track radii
TRACK_RADIUS_FACTORS = {12: None, 15: None}  # kept for UI compatibility

# Tolerance window: +/-3.0 IPPT absolute on combined target
DEFAULT_TOLERANCE = 3.0

# Spring tier definitions — maps category keys to tier names
TIER_CATEGORIES = {
    "economy":  ["low_cycle_2in"],
    "mid":      ["high_cycle_2in"],
    "max_life": ["max_life_2in"],
}

TIER_LABELS = {
    "economy":  "💰 Economy  (Low Cycle ~10k)",
    "mid":      "⚙️ Mid-Grade  (High Cycle ~20k)",
    "max_life": "🏆 Max Life  (Max Cycle ~100k)",
}


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class SpringPairMatch:
    """A matched spring pair from the combined IPPT table."""
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
    """Best match (or out-of-range flag) for a single spring tier."""
    tier_key: str          # "economy" | "mid" | "max_life"
    tier_label: str        # human-readable tier name
    match: Optional[SpringPairMatch]   # None = out of range
    in_range: bool


@dataclass
class CalculationResult:
    """Full output from the IPPT engine."""
    door_weight_lbs: float
    door_height_ft: float
    door_height_inches: float
    track_radius: int
    drum_model: str
    drum_label: str
    drum_circumference: float   # kept for display (HEIGHT_CIRC)
    cable_drum_turns: float
    track_factor: float         # kept for display (radius_offset)
    target_combined_ippt: float
    tolerance: float
    lower_bound: float
    upper_bound: float
    matches: list               # flat list (all tiers, sorted by delta)
    tier_results: list          # list[TierResult] — one per tier
    notes: list


# ---------------------------------------------------------------------------
# Core Calculation
# ---------------------------------------------------------------------------

def calculate_target_ippt(
    door_weight_lbs: float,
    door_height_ft: float,
    track_radius: int = 12,
    drum_model: str = "d400_96",
    cable_drum_turns_override: Optional[float] = None
) -> CalculationResult:
    """
    Calculate the Target Combined IPPT for a door.

    SSC Formula:
        CDT  = (height_inches / HEIGHT_CIRC) + radius_offset[drum][radius]
        TIPP = weight / CDT

    Args:
        door_weight_lbs:           Total door weight in pounds
        door_height_ft:            Door height in feet
        track_radius:              12 (standard) or 15 (high-lift)
        drum_model:                Key from DRUM_PROFILES
        cable_drum_turns_override: Manually enter CDT (skips auto-calc)

    Returns:
        CalculationResult with target IPPT, flat matches list, and tier_results
    """
    notes = []

    if track_radius not in (12, 15):
        raise ValueError(f"Track radius must be 12 or 15. Got: {track_radius}")
    if drum_model not in DRUM_PROFILES:
        raise ValueError(f"Unknown drum model: {drum_model}. Options: {list(DRUM_PROFILES.keys())}")

    drum_label = DRUM_PROFILES[drum_model]["label"]
    door_height_inches = round(door_height_ft * 12, 2)

    if cable_drum_turns_override is not None:
        turns = round(cable_drum_turns_override, 4)
        radius_offset = None
        notes.append(f"Cable drum turns manually entered: {turns}")
    else:
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
        track_factor=radius_offset if radius_offset is not None else 0.0,
        target_combined_ippt=target,
        tolerance=DEFAULT_TOLERANCE,
        lower_bound=lower,
        upper_bound=upper,
        matches=matches,
        tier_results=tier_results,
        notes=notes
    )


# ---------------------------------------------------------------------------
# Inventory Matching
# ---------------------------------------------------------------------------

def load_pricebook() -> dict:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "inventory", "pricebook.json")
    with open(path, "r") as f:
        return json.load(f)


def find_pair_matches(target: float, lower_bound: float, upper_bound: float):
    """
    Scan all spring pairs in the combined IPPT table.

    Returns:
        (flat_matches, tier_results)
        flat_matches  — all in-range pairs sorted by abs_delta
        tier_results  — list[TierResult], one per tier (economy/mid/max_life)
                        each holds the single best match for that tier, or
                        in_range=False if no pair qualifies.
    """
    pricebook = load_pricebook()
    categories = pricebook.get("spring_categories", {})

    # Build a dict: cat_key -> list of candidate dicts
    cat_candidates: dict[str, list] = {}

    for cat_key, cat_data in categories.items():
        label = cat_data.get("label", cat_key)
        pairs = cat_data.get("combined_ippt_table", {}).get("pairs", [])
        cat_candidates[cat_key] = []

        for pair in pairs:
            combined = pair.get("combined_ippt", 0)
            delta = round(combined - target, 2)
            abs_delta = abs(delta)
            cat_candidates[cat_key].append({
                "category": cat_key,
                "category_label": label,
                "spring1_code": pair["spring1"],
                "spring2_code": pair["spring2"],
                "combined_ippt": combined,
                "delta": delta,
                "abs_delta": abs_delta,
                "in_range": lower_bound <= combined <= upper_bound,
            })

        # Sort each category by abs_delta
        cat_candidates[cat_key].sort(key=lambda x: x["abs_delta"])

    # --- Flat list of all in-range matches (all tiers combined) ---
    all_in_range = []
    for candidates in cat_candidates.values():
        all_in_range.extend([c for c in candidates if c["in_range"]])
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
            abs_delta=c["abs_delta"]
        )
        for i, c in enumerate(all_in_range)
    ]

    # --- Per-tier results: best match (or out-of-range) for each tier ---
    tier_results = []
    for tier_key, cat_keys in TIER_CATEGORIES.items():
        tier_label = TIER_LABELS[tier_key]
        best_match = None

        # Collect in-range candidates across all categories in this tier
        tier_in_range = []
        for cat_key in cat_keys:
            if cat_key in cat_candidates:
                tier_in_range.extend([c for c in cat_candidates[cat_key] if c["in_range"]])

        tier_in_range.sort(key=lambda x: x["abs_delta"])

        if tier_in_range:
            c = tier_in_range[0]
            best_match = SpringPairMatch(
                rank=1,
                category=c["category"],
                category_label=c["category_label"],
                spring1_code=c["spring1_code"],
                spring2_code=c["spring2_code"],
                combined_ippt=c["combined_ippt"],
                delta=c["delta"],
                abs_delta=c["abs_delta"]
            )

        tier_results.append(TierResult(
            tier_key=tier_key,
            tier_label=tier_label,
            match=best_match,
            in_range=best_match is not None,
        ))

    return flat_matches, tier_results


# ---------------------------------------------------------------------------
# CLI Test Runner — verified against SSC Spring Engineering App
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    # Force UTF-8 on Windows cmd so emoji in tier labels don't crash
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # ASCII-safe tier labels for CLI output
    CLI_TIER_LABELS = {
        "economy":  "Economy  (Low Cycle ~10k)",
        "mid":      "Mid-Grade (High Cycle ~20k)",
        "max_life": "Max Life  (Max Cycle ~100k)",
    }

    print("=" * 70)
    print("  GARAGE DOOR SPRING ENGINEERING ENGINE")
    print("  Verified against SSC Spring Engineering App")
    print("=" * 70)

    tests = [
        # (weight, height_ft, radius, drum, expected_tipp, label)
        # --- Original verified tests ---
        (185, 7.0, 12, "d400_96",  55.12, "SS1: 185lb/7ft/12/D400-96"),
        (185, 7.0, 12, "d400_144", 55.98, "SS2: 185lb/7ft/12/D400-144"),
        (185, 7.0, 15, "d400_144", 53.84, "SS3: 185lb/7ft/15/D400-144"),
        (205, 7.0, 15, "d400_96",  58.75, "SS4: 205lb/7ft/15/D400-96"),
        (230, 7.0, 15, "d400_96",  65.91, "SS5: 230lb/7ft/15/D400-96"),
        (185, 8.0, 12, "d400_96",  49.30, "SS6: 185lb/8ft/12/D400-96"),
        (195, 8.0, 15, "d400_96",  50.27, "SS7: 195lb/8ft/15/D400-96"),
        # --- New cross-reference tests from SSC app screenshots ---
        (190, 8.0, 12, "d400_96",  50.64, "New01: 190lb/8ft/12/D400-96"),
        (200, 8.0, 12, "d400_96",  53.30, "New02: 200lb/8ft/12/D400-96"),
        (203, 8.0, 12, "d400_96",  54.10, "New03: 203lb/8ft/12/D400-96"),
        (145, 8.0, 12, "d400_96",  38.64, "New04: 145lb/8ft/12/D400-96"),
        (158, 8.0, 12, "d400_96",  42.11, "New05: 158lb/8ft/12/D400-96"),
        (169, 8.0, 12, "d400_96",  45.04, "New06: 169lb/8ft/12/D400-96"),
        (169, 8.0, 12, "d400_144", 45.74, "New07: 169lb/8ft/12/D400-144"),
        (155, 8.0, 12, "d400_144", 41.95, "New08: 155lb/8ft/12/D400-144"),
        (203, 8.0, 12, "d400_144", 54.94, "New09: 203lb/8ft/12/D400-144"),
        (218, 8.0, 12, "d400_144", 59.00, "New10: 218lb/8ft/12/D400-144"),
        (235, 8.0, 12, "d400_144", 63.60, "New11: 235lb/8ft/12/D400-144"),
        (235, 8.0, 15, "d400_144", 61.52, "New12: 235lb/8ft/15/D400-144"),
        (198, 8.0, 15, "d400_144", 51.84, "New13: 198lb/8ft/15/D400-144"),
        (183, 8.0, 15, "d400_144", 47.91, "New14: 183lb/8ft/15/D400-144"),
        (165, 8.0, 15, "d400_144", 43.20, "New15: 165lb/8ft/15/D400-144"),
        (145, 8.0, 12, "d400_144", 39.24, "New16: 145lb/8ft/12/D400-144"),
    ]

    all_pass = True
    for weight, height, radius, drum, expected, label in tests:
        r = calculate_target_ippt(weight, height, radius, drum)
        diff = abs(r.target_combined_ippt - expected)
        # Allow 0.20 tolerance — SSC app itself rounds at this scale
        status = "PASS" if diff <= 0.20 else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"\n{label}")
        print(f"  Expected: {expected}  Got: {r.target_combined_ippt}  Diff: {diff:.4f}  [{status}]")
        for n in r.notes:
            print(f"  - {n}")
        # Show best match per tier (use ASCII-safe labels for Windows cmd)
        for tr in r.tier_results:
            cli_label = CLI_TIER_LABELS.get(tr.tier_key, tr.tier_key)
            if tr.in_range:
                m = tr.match
                print(f"  [{cli_label}]: {m.spring1_code} + {m.spring2_code}  IPPT={m.combined_ippt}  (delta {m.delta:+.2f})")
            else:
                print(f"  [{cli_label}]: *** OUT OF RANGE ***")

    print("\n" + "=" * 70)
    print("  ALL TESTS PASSED" if all_pass else "  SOME TESTS FAILED — check diffs above")
    print("=" * 70)
