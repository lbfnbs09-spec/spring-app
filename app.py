"""
Garage Door Spring Calculator
================================
Standalone Streamlit app — no API keys, no internet required.
Enter door measurements → get matched spring pairs from your inventory chart.

Run with:
    streamlit run app.py
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import calculate_target_ippt, DRUM_PROFILES, DEFAULT_TOLERANCE

# ---------------------------------------------------------------------------
# Page Config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Spring Calc",
    page_icon="🌀",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Only the two Canimex drum options shown in UI — short names only
DRUM_OPTIONS = {
    "d400_96":  "Canimex / TF D-400-96",
    "d400_144": "Canimex D-400-144",
}

# ---------------------------------------------------------------------------
# CSS — Sleek minimal dark theme
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .stApp { background-color: #0a0a0f; color: #e8e8f0; }

    /* Hide Streamlit chrome */
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 680px; }

    /* ── App Header ── */
    .app-header {
        text-align: center;
        padding: 2rem 0 1.5rem 0;
    }
    .app-logo { font-size: 2.2rem; margin-bottom: 0.4rem; }
    .app-title {
        font-size: 1.5rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        color: #ffffff;
        margin: 0;
    }
    .app-sub {
        font-size: 0.72rem;
        color: #444460;
        margin-top: 0.3rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    /* ── Input Card ── */
    .input-card {
        background: #12121a;
        border: 1px solid #1e1e2e;
        border-radius: 16px;
        padding: 1.5rem 1.75rem 1.25rem 1.75rem;
        margin-bottom: 1rem;
    }
    .section-label {
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #333350;
        margin-bottom: 1rem;
    }

    /* ── Widget overrides ── */
    div[data-testid="stNumberInput"] label,
    div[data-testid="stRadio"] label,
    div[data-testid="stSelectbox"] label {
        color: #555570 !important;
        font-size: 0.68rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.08em !important;
        text-transform: uppercase !important;
    }
    div[data-testid="stNumberInput"] input {
        background: #0d0d14 !important;
        border: 1px solid #1e1e2e !important;
        border-radius: 8px !important;
        color: #ffffff !important;
        font-size: 1.15rem !important;
        font-weight: 700 !important;
    }
    div[data-testid="stSelectbox"] > div > div {
        background: #0d0d14 !important;
        border: 1px solid #1e1e2e !important;
        border-radius: 8px !important;
        color: #e8e8f0 !important;
        font-size: 0.85rem !important;
    }
    /* Radio buttons — clean pill style */
    div[data-testid="stRadio"] > div {
        flex-direction: row !important;
        gap: 0.5rem !important;
    }
    div[data-testid="stRadio"] > div > label {
        background: #0d0d14 !important;
        border: 1px solid #1e1e2e !important;
        border-radius: 8px !important;
        padding: 0.55rem 1.25rem !important;
        color: #888899 !important;
        font-size: 0.9rem !important;
        font-weight: 700 !important;
        text-transform: none !important;
        letter-spacing: 0 !important;
        cursor: pointer;
    }
    div[data-testid="stCheckbox"] label {
        color: #444460 !important;
        font-size: 0.75rem !important;
        text-transform: none !important;
        letter-spacing: 0 !important;
    }

    /* ── Calculate Button ── */
    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #e63946, #c1121f);
        color: white;
        font-weight: 700;
        font-size: 0.88rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        border: none;
        border-radius: 10px;
        padding: 0.9rem;
        margin-top: 0.25rem;
    }
    .stButton > button:hover { opacity: 0.85; }

    /* ── IPPT Banner ── */
    .ippt-banner {
        background: #12121a;
        border: 1px solid #1e1e2e;
        border-radius: 16px;
        padding: 1.75rem;
        text-align: center;
        margin: 1.25rem 0;
        position: relative;
        overflow: hidden;
    }
    .ippt-banner::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent, #e63946, transparent);
    }
    .ippt-value {
        font-size: 4.5rem;
        font-weight: 900;
        color: #ffffff;
        line-height: 1;
        letter-spacing: -0.04em;
    }
    .ippt-unit {
        font-size: 1.1rem;
        font-weight: 500;
        color: #e63946;
        margin-left: 0.25rem;
        vertical-align: super;
        font-size: 1rem;
    }
    .ippt-label {
        font-size: 0.62rem;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: #333350;
        margin-top: 0.5rem;
    }
    .ippt-window {
        font-size: 0.75rem;
        color: #2a2a3e;
        margin-top: 0.5rem;
    }
    .ippt-window b { color: #444460; }

    /* ── Metrics Pills ── */
    .metrics-row {
        display: flex;
        gap: 0.6rem;
        margin: 0.75rem 0 1.25rem 0;
    }
    .metric-pill {
        flex: 1;
        background: #12121a;
        border: 1px solid #1e1e2e;
        border-radius: 10px;
        padding: 0.6rem 0.5rem;
        text-align: center;
    }
    .metric-pill-val {
        font-size: 0.95rem;
        font-weight: 700;
        color: #e8e8f0;
    }
    .metric-pill-lbl {
        font-size: 0.58rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #333350;
        margin-top: 0.15rem;
    }

    /* ── Section Divider ── */
    .section-divider {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin: 1.5rem 0 1rem 0;
    }
    .sdl { flex: 1; height: 1px; background: #1a1a24; }
    .sdt {
        font-size: 0.62rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #2a2a3e;
        white-space: nowrap;
    }

    /* ── Tier Cards ── */
    .tier-card {
        background: #12121a;
        border: 1px solid #1e1e2e;
        border-radius: 14px;
        padding: 1.1rem 1.25rem;
        margin: 0.55rem 0;
        position: relative;
    }
    .tier-card-economy  { border-left: 3px solid #52525b; }
    .tier-card-mid      { border-left: 3px solid #2563eb; }
    .tier-card-maxlife  { border-left: 3px solid #d97706; }

    .tier-top-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.55rem;
    }
    .tier-badge {
        font-size: 0.58rem;
        font-weight: 700;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        padding: 0.18rem 0.5rem;
        border-radius: 20px;
    }
    .tb-economy  { background: #18181f; color: #52525b; }
    .tb-mid      { background: #0c1629; color: #2563eb; }
    .tb-maxlife  { background: #1a1200; color: #d97706; }

    .tier-delta {
        font-size: 0.68rem;
        font-weight: 600;
        padding: 0.18rem 0.5rem;
        border-radius: 20px;
        background: #0d0d14;
        border: 1px solid #1a1a24;
    }
    .td-pos  { color: #10b981; }
    .td-neg  { color: #f87171; }
    .td-zero { color: #10b981; }

    .tier-codes {
        font-size: 1.4rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -0.01em;
    }
    .tier-plus { color: #2a2a3e; font-weight: 300; margin: 0 0.3rem; }

    .tier-bottom-row {
        display: flex;
        align-items: center;
        margin-top: 0.4rem;
        gap: 0.5rem;
    }
    .tier-ippt { font-size: 0.82rem; font-weight: 600; color: #10b981; }
    .tier-sep  { color: #1e1e2e; font-size: 0.7rem; }
    .tier-cat  { font-size: 0.62rem; color: #2a2a3e; }

    /* ── Out of Range ── */
    .oor-card {
        background: #0d0d14;
        border: 1px dashed #1a1a24;
        border-radius: 14px;
        padding: 0.9rem 1.25rem;
        margin: 0.55rem 0;
        display: flex;
        align-items: center;
        gap: 0.85rem;
    }
    .oor-icon { font-size: 1.2rem; opacity: 0.25; }
    .oor-tier {
        font-size: 0.58rem;
        font-weight: 700;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #2a2a3e;
        margin-bottom: 0.15rem;
    }
    .oor-msg { font-size: 0.82rem; font-weight: 600; color: #333350; }

    /* ── Note Box ── */
    .note-box {
        background: #0a0a0f;
        border-left: 2px solid #1a1a24;
        padding: 0.45rem 0.75rem;
        border-radius: 4px;
        font-size: 0.72rem;
        color: #333350;
        margin: 0.25rem 0;
        font-family: 'Courier New', monospace;
    }

    /* ── Match Rows ── */
    .match-row {
        display: flex;
        align-items: center;
        padding: 0.6rem 0;
        border-bottom: 1px solid #14141e;
        gap: 0.75rem;
    }
    .match-row:last-child { border-bottom: none; }
    .mr-rank { font-size: 0.6rem; color: #2a2a3e; font-weight: 700; min-width: 1.5rem; }
    .mr-codes { font-size: 0.88rem; font-weight: 700; color: #e8e8f0; flex: 1; }
    .mr-cat { font-size: 0.6rem; color: #2a2a3e; display: block; margin-top: 0.1rem; }
    .mr-ippt { font-size: 0.8rem; font-weight: 600; color: #10b981; white-space: nowrap; }
    .mr-delta { font-size: 0.62rem; color: #2a2a3e; }

    /* ── Empty State ── */
    .empty-state {
        text-align: center;
        padding: 4rem 1rem 3rem 1rem;
    }
    .empty-icon { font-size: 3rem; margin-bottom: 0.75rem; opacity: 0.15; }
    .empty-text { font-size: 0.8rem; color: #222230; font-weight: 500; }

    /* ── Footer ── */
    .app-footer {
        text-align: center;
        padding: 2rem 0 0.5rem 0;
        font-size: 0.6rem;
        color: #1a1a24;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    /* Expander */
    details {
        background: #12121a !important;
        border: 1px solid #1e1e2e !important;
        border-radius: 10px !important;
        padding: 0 0.5rem !important;
    }
    details summary {
        font-size: 0.7rem !important;
        color: #333350 !important;
        font-weight: 700 !important;
        letter-spacing: 0.06em !important;
        text-transform: uppercase !important;
        padding: 0.75rem 0 !important;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("""
<div class="app-header">
    <div class="app-logo">🌀</div>
    <div class="app-title">Spring Calculator</div>
    <div class="app-sub">SSC Formula · Field Edition</div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
st.markdown('<div class="input-card"><div class="section-label">Door Specifications</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    door_weight = st.number_input("Weight (lbs)", min_value=50, max_value=700, value=185, step=5)
with col2:
    door_height = st.number_input("Height (ft)", min_value=6.0, max_value=16.0, value=7.0, step=0.5)

col3, col4 = st.columns(2)
with col3:
    track_radius = st.radio(
        "Track Radius",
        options=[12, 15],
        index=0,
        format_func=lambda x: f'{x}"'
    )
with col4:
    drum_model = st.selectbox(
        "Drum Model",
        options=list(DRUM_OPTIONS.keys()),
        index=0,
        format_func=lambda k: DRUM_OPTIONS[k]
    )

manual_turns_enabled = st.checkbox("Override drum turns manually", value=False)
if manual_turns_enabled:
    manual_turns = st.number_input("Drum Turns (CDT)", min_value=1.0, max_value=20.0, value=3.4, step=0.05)
else:
    manual_turns = None

st.markdown('</div>', unsafe_allow_html=True)

calc_btn = st.button("⚡  Calculate Spring Requirements")

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
if calc_btn:
    try:
        result = calculate_target_ippt(
            door_weight_lbs=float(door_weight),
            door_height_ft=float(door_height),
            track_radius=int(track_radius),
            drum_model=drum_model,
            cable_drum_turns_override=manual_turns
        )

        # ── IPPT Banner ──
        st.markdown(f"""
        <div class="ippt-banner">
            <div class="ippt-value">{result.target_combined_ippt}<span class="ippt-unit">IPPT</span></div>
            <div class="ippt-label">Target Combined IPPT</div>
            <div class="ippt-window">
                Match window &nbsp;<b>{result.lower_bound} – {result.upper_bound}</b>&nbsp; (±{result.tolerance})
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Metrics ──
        st.markdown(f"""
        <div class="metrics-row">
            <div class="metric-pill">
                <div class="metric-pill-val">{result.door_weight_lbs} lbs</div>
                <div class="metric-pill-lbl">Weight</div>
            </div>
            <div class="metric-pill">
                <div class="metric-pill-val">{result.door_height_ft} ft</div>
                <div class="metric-pill-lbl">Height</div>
            </div>
            <div class="metric-pill">
                <div class="metric-pill-val">{result.track_radius}"</div>
                <div class="metric-pill-lbl">Radius</div>
            </div>
            <div class="metric-pill">
                <div class="metric-pill-val">{result.cable_drum_turns}</div>
                <div class="metric-pill-lbl">CDT</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Calculation Notes ──
        with st.expander("Calculation details"):
            for note in result.notes:
                st.markdown(f'<div class="note-box">▸ {note}</div>', unsafe_allow_html=True)

        # ── Tier Divider ──
        st.markdown("""
        <div class="section-divider">
            <div class="sdl"></div>
            <div class="sdt">Spring Options by Grade</div>
            <div class="sdl"></div>
        </div>
        """, unsafe_allow_html=True)

        # Tier config: key -> (badge_cls, card_cls, name)
        tier_cfg = {
            "economy":  ("tb-economy",  "tier-card-economy",  "Economy"),
            "mid":      ("tb-mid",      "tier-card-mid",      "Mid-Grade"),
            "max_life": ("tb-maxlife",  "tier-card-maxlife",  "Max Life"),
        }

        for tr in result.tier_results:
            badge_cls, card_cls, tier_name = tier_cfg.get(tr.tier_key, ("", "", tr.tier_key))

            if tr.in_range:
                m = tr.match
                if m.delta > 0:
                    delta_str, delta_cls = f"+{m.delta}", "td-pos"
                elif m.delta < 0:
                    delta_str, delta_cls = str(m.delta), "td-neg"
                else:
                    delta_str, delta_cls = "±0", "td-zero"

                pair_type = "Matched" if m.spring1_code == m.spring2_code else "Mixed"

                st.markdown(f"""
                <div class="tier-card {card_cls}">
                    <div class="tier-top-row">
                        <span class="tier-badge {badge_cls}">{tier_name}</span>
                        <span class="tier-delta {delta_cls}">{delta_str} IPPT</span>
                    </div>
                    <div class="tier-codes">
                        {m.spring1_code}<span class="tier-plus">+</span>{m.spring2_code}
                    </div>
                    <div class="tier-bottom-row">
                        <span class="tier-ippt">{m.combined_ippt} IPPT</span>
                        <span class="tier-sep">·</span>
                        <span class="tier-cat">{m.category_label} · {pair_type} pair</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="oor-card">
                    <div class="oor-icon">⊘</div>
                    <div>
                        <div class="oor-tier">{tier_name}</div>
                        <div class="oor-msg">Out of Range — Does Not Qualify</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # ── All Matches ──
        if result.matches:
            with st.expander(f"All {len(result.matches)} matching pair(s)"):
                for m in result.matches:
                    delta_sign = f"+{m.delta}" if m.delta >= 0 else str(m.delta)
                    st.markdown(f"""
                    <div class="match-row">
                        <span class="mr-rank">#{m.rank}</span>
                        <span class="mr-codes">
                            {m.spring1_code} + {m.spring2_code}
                            <span class="mr-cat">{m.category_label}</span>
                        </span>
                        <span class="mr-ippt">{m.combined_ippt}
                            <span class="mr-delta">({delta_sign})</span>
                        </span>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="oor-card">
                <div class="oor-icon">⊘</div>
                <div>
                    <div class="oor-msg">No pairs found within ±{result.tolerance} IPPT of {result.target_combined_ippt}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Calculation error: {e}")
        st.exception(e)

else:
    st.markdown("""
    <div class="empty-state">
        <div class="empty-icon">🌀</div>
        <div class="empty-text">Enter door specs above and tap Calculate</div>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="app-footer">Spring Calc v2.2 &nbsp;·&nbsp; SSC Formula Verified &nbsp;·&nbsp; No internet required</div>',
    unsafe_allow_html=True
)
