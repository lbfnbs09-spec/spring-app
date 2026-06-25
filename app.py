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

from engine import calculate_target_ippt, DRUM_PROFILES, TRACK_RADIUS_FACTORS, DEFAULT_TOLERANCE

# ---------------------------------------------------------------------------
# Page Config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Spring Calc",
    page_icon="🌀",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ---------------------------------------------------------------------------
# CSS — Dark field-ready theme
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .stApp { background-color: #111827; color: #f3f4f6; }

    .header-box {
        background: linear-gradient(135deg, #1f2937, #374151);
        border-left: 5px solid #ef4444;
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 18px;
    }
    .header-box h2 { margin: 0; color: #ef4444; font-size: 1.5rem; }
    .header-box p  { margin: 4px 0 0 0; color: #9ca3af; font-size: 0.82rem; }

    .ippt-box {
        background: #1f2937;
        border: 2px solid #ef4444;
        border-radius: 12px;
        padding: 18px;
        text-align: center;
        margin: 12px 0;
    }
    .ippt-number { font-size: 3rem; font-weight: 900; color: #ef4444; line-height: 1; }
    .ippt-label  { font-size: 0.85rem; color: #9ca3af; margin-top: 4px; }
    .band-label  { font-size: 0.9rem; color: #6b7280; margin-top: 6px; }

    /* Tier cards */
    .tier-card {
        background: #1f2937;
        border: 1px solid #374151;
        border-radius: 12px;
        padding: 16px 18px;
        margin: 10px 0;
    }
    .tier-card-economy  { border-left: 5px solid #6b7280; }
    .tier-card-mid      { border-left: 5px solid #3b82f6; }
    .tier-card-maxlife  { border-left: 5px solid #f59e0b; }

    .tier-header {
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 6px;
    }
    .tier-economy-color  { color: #9ca3af; }
    .tier-mid-color      { color: #60a5fa; }
    .tier-maxlife-color  { color: #fbbf24; }

    .tier-codes {
        font-size: 1.25rem;
        font-weight: 800;
        color: #f9fafb;
        margin: 4px 0;
    }
    .tier-ippt {
        font-size: 1.0rem;
        color: #10b981;
        font-weight: 600;
    }
    .tier-delta {
        font-size: 0.82rem;
        color: #9ca3af;
    }
    .tier-cat {
        font-size: 0.75rem;
        color: #6b7280;
        margin-top: 2px;
    }

    .out-of-range-card {
        background: #1f2937;
        border: 1px dashed #4b5563;
        border-radius: 12px;
        padding: 16px 18px;
        margin: 10px 0;
        text-align: center;
    }
    .out-of-range-title {
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: #6b7280;
        margin-bottom: 8px;
    }
    .out-of-range-msg {
        font-size: 1.0rem;
        color: #f59e0b;
        font-weight: 600;
    }
    .out-of-range-sub {
        font-size: 0.78rem;
        color: #6b7280;
        margin-top: 4px;
    }

    .match-card {
        background: #1f2937;
        border: 1px solid #374151;
        border-radius: 10px;
        padding: 14px 16px;
        margin: 8px 0;
    }
    .match-card-top {
        background: #1f2937;
        border: 2px solid #10b981;
        border-radius: 10px;
        padding: 14px 16px;
        margin: 8px 0;
    }
    .match-rank   { font-size: 0.75rem; color: #6b7280; }
    .match-codes  { font-size: 1.1rem; font-weight: 700; color: #f9fafb; }
    .match-cat    { font-size: 0.78rem; color: #60a5fa; margin-top: 2px; }
    .match-ippt   { font-size: 1.0rem; color: #10b981; font-weight: 600; }
    .match-delta  { font-size: 0.82rem; color: #9ca3af; }

    .no-match-box {
        background: #1f2937;
        border: 1px solid #f59e0b;
        border-radius: 10px;
        padding: 16px;
        color: #fbbf24;
        text-align: center;
    }

    .note-box {
        background: #111827;
        border-left: 3px solid #374151;
        padding: 8px 12px;
        border-radius: 4px;
        font-size: 0.8rem;
        color: #6b7280;
    }

    div[data-testid="stNumberInput"] label,
    div[data-testid="stRadio"] label,
    div[data-testid="stSelectbox"] label { color: #d1d5db !important; font-weight: 600; }

    .stButton > button {
        width: 100%;
        background-color: #ef4444;
        color: white;
        font-weight: 700;
        font-size: 1.05rem;
        border: none;
        border-radius: 8px;
        padding: 12px;
    }
    .stButton > button:hover { background-color: #dc2626; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("""
<div class="header-box">
    <h2>🌀 GARAGE DOOR SPRING CALCULATOR</h2>
    <p>Enter door measurements → get matched spring pairs from your inventory</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Input Form
# ---------------------------------------------------------------------------
st.markdown("### Door Measurements")

col1, col2 = st.columns(2)

with col1:
    door_weight = st.number_input(
        "Door Weight (lbs)",
        min_value=50,
        max_value=700,
        value=185,
        step=5,
        help="Total door weight in pounds"
    )

with col2:
    door_height = st.number_input(
        "Door Height (ft)",
        min_value=6.0,
        max_value=16.0,
        value=7.0,
        step=0.5,
        help="Door height in feet (e.g. 7, 7.5, 8)"
    )

col3, col4 = st.columns(2)

with col3:
    track_radius = st.radio(
        "Track Radius",
        options=[12, 15],
        index=0,
        format_func=lambda x: f'{x}" — {"Standard" if x == 12 else "High-Lift"}',
        help="12\" = standard residential. 15\" = high-lift or commercial."
    )

with col4:
    drum_model = st.selectbox(
        "Drum Model",
        options=list(DRUM_PROFILES.keys()),
        index=0,
        format_func=lambda k: DRUM_PROFILES[k]["label"],
        help="Select the cable drum model installed on this door"
    )

# Optional manual turns override
manual_turns_enabled = st.checkbox("Override Drum Turns manually", value=False)
if manual_turns_enabled:
    manual_turns = st.number_input(
        "Drum Turns",
        min_value=1.0,
        max_value=20.0,
        value=3.4,
        step=0.05
    )
else:
    manual_turns = None

st.markdown("---")

# ---------------------------------------------------------------------------
# Calculate Button
# ---------------------------------------------------------------------------
calc_btn = st.button("⚡ CALCULATE SPRING REQUIREMENTS")

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

        # --- Target IPPT display ---
        st.markdown("### 🎯 Target Combined IPPT")

        st.markdown(f"""
        <div class="ippt-box">
            <div class="ippt-number">{result.target_combined_ippt}</div>
            <div class="ippt-label">TARGET COMBINED IPPT</div>
            <div class="band-label">
                Match window: {result.lower_bound} – {result.upper_bound}
                &nbsp;(±{result.tolerance} IPPT)
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Metrics row
        c1, c2, c3 = st.columns(3)
        c1.metric("Door Weight", f"{result.door_weight_lbs} lbs")
        c2.metric("Cable Drum Turns", f"{result.cable_drum_turns}")
        c3.metric("Track", f'{result.track_radius}" radius')
        st.caption(f"Drum: {result.drum_label} | Radius offset: {result.track_factor}")

        # Calculation notes
        with st.expander("📝 How this was calculated"):
            for note in result.notes:
                st.markdown(f"""<div class="note-box">• {note}</div>""", unsafe_allow_html=True)

        # --- 3-Tier Spring Options ---
        st.markdown("---")
        st.markdown("### 🔧 Spring Options by Grade")
        st.caption("One best match shown per grade — ⚠️ Out of Range means no inventory match within ±3 IPPT")

        # Tier styling config
        tier_style = {
            "economy":  ("tier-economy-color",  "tier-card-economy"),
            "mid":      ("tier-mid-color",       "tier-card-mid"),
            "max_life": ("tier-maxlife-color",   "tier-card-maxlife"),
        }

        for tr in result.tier_results:
            color_cls, border_cls = tier_style.get(tr.tier_key, ("", ""))

            if tr.in_range:
                m = tr.match
                same_label = "✅ Matched Pair" if m.spring1_code == m.spring2_code else "🔀 Mixed Pair"
                delta_sign = f"+{m.delta}" if m.delta >= 0 else str(m.delta)

                st.markdown(f"""
                <div class="tier-card {border_cls}">
                    <div class="tier-header {color_cls}">{tr.tier_label}</div>
                    <div class="tier-codes">{m.spring1_code} &nbsp;+&nbsp; {m.spring2_code}</div>
                    <div class="tier-cat">{m.category_label} &nbsp;·&nbsp; {same_label}</div>
                    <div class="tier-ippt">
                        Combined IPPT: {m.combined_ippt}
                        &nbsp;<span class="tier-delta">({delta_sign} from target)</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="out-of-range-card">
                    <div class="out-of-range-title {color_cls}">{tr.tier_label}</div>
                    <div class="out-of-range-msg">⚠️ Out of Range — Does Not Qualify</div>
                    <div class="out-of-range-sub">
                        No {tr.tier_label.split('(')[0].strip()} spring pair within
                        ±{result.tolerance} IPPT of {result.target_combined_ippt}
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # --- All Matched Pairs (collapsible detail) ---
        st.markdown("---")
        if result.matches:
            with st.expander(f"📋 All {len(result.matches)} matching pair(s) — sorted by closest match"):
                for m in result.matches:
                    is_top = (m.rank == 1)
                    card_class = "match-card-top" if is_top else "match-card"
                    same_label = "✅ Matched Pair" if m.spring1_code == m.spring2_code else "🔀 Mixed Pair"
                    delta_sign = f"+{m.delta}" if m.delta >= 0 else str(m.delta)
                    top_badge = "⭐ BEST MATCH &nbsp;" if is_top else ""

                    st.markdown(f"""
                    <div class="{card_class}">
                        <div class="match-rank">#{m.rank} &nbsp; {top_badge}{same_label}</div>
                        <div class="match-codes">
                            {m.spring1_code} &nbsp;+&nbsp; {m.spring2_code}
                        </div>
                        <div class="match-cat">{m.category_label}</div>
                        <div class="match-ippt">
                            Combined IPPT: {m.combined_ippt}
                            &nbsp;
                            <span class="match-delta">({delta_sign} from target)</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="no-match-box">
                ⚠️ No spring pairs found within ±{result.tolerance} IPPT of {result.target_combined_ippt}<br/>
                <small>Check door weight / height inputs, or the target may fall between inventory sizes.</small>
            </div>
            """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"❌ Calculation error: {e}")
        st.exception(e)

else:
    # Placeholder before first calculation
    st.markdown("""
    <div style="text-align:center; padding: 40px 0; color: #4b5563;">
        <div style="font-size: 3rem;">🌀</div>
        <div style="font-size: 1rem; margin-top: 8px;">
            Enter door measurements above and tap <strong>Calculate</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    "<p style='text-align:center; color:#374151; font-size:0.75rem;'>"
    "Spring Calc v2.2 — SSC Formula Verified | Standalone / No internet required"
    "</p>",
    unsafe_allow_html=True
)
