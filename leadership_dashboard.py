import json
import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from governance_schema import DISPLAY_MAPPING, NIST_SUBCHECKS

st.set_page_config(page_title="AI Risk & Compliance Posture", layout="wide", initial_sidebar_state="collapsed")

# -----------------------------------------------------------------------------
# Visual language - one place for every color so tiles, charts, and badges
# agree with each other at a glance.
# -----------------------------------------------------------------------------
TIER_COLOR = {
    "Prohibited Risk": "#7A0019",
    "High Risk": "#D9534F",
    "Limited Risk": "#F0AD4E",
    "Minimal Risk": "#4CAF50",
}
TIER_ICON = {
    "Prohibited Risk": "\u26d4",
    "High Risk": "\U0001F534",
    "Limited Risk": "\U0001F7E1",
    "Minimal Risk": "\U0001F7E2",
}
ACTION_COLOR = {
    "BLOCKED - Prohibited Under EU AI Act Article 5": "#7A0019",
    "CRITICAL - Immediate Remediation": "#D9534F",
    "Manual Compliance Review (Low Confidence)": "#9B59B6",
    "High - Requires Conformity Assessment": "#E08E2B",
    "Escalate - Review Required": "#E0C02B",
    "Monitor": "#4CAF50",
}
NEUTRAL_BG = "#F4F6F8"

st.markdown(
    f"""
    <style>
    .block-container {{ padding-top: 1.4rem; }}
    div[data-testid="stMetric"] {{
        background: white; border-radius: 10px; padding: 14px 16px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08); border-left: 5px solid #ccc;
    }}
    .kpi-critical div[data-testid="stMetric"] {{ border-left-color: {ACTION_COLOR['CRITICAL - Immediate Remediation']}; }}
    .kpi-manual div[data-testid="stMetric"] {{ border-left-color: {ACTION_COLOR['Manual Compliance Review (Low Confidence)']}; }}
    .kpi-approved div[data-testid="stMetric"] {{ border-left-color: {ACTION_COLOR['Monitor']}; }}
    .kpi-total div[data-testid="stMetric"] {{ border-left-color: #4472C4; }}
    .posture-banner {{
        border-radius: 10px; padding: 16px 22px; font-size: 1.15rem;
        font-weight: 600; margin-bottom: 10px; color: white;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

REPORT_CSV = "laya_full_audit_report.csv"
BENCHMARK_JSON_CANDIDATES = ["./laya_fine_tuned_model/laya_benchmark_report.json", "laya_benchmark_report.json"]


@st.cache_data
def load_report(_mtime):
    if not os.path.exists(REPORT_CSV):
        return None
    df = pd.read_csv(REPORT_CSV)
    for function in NIST_SUBCHECKS:
        col = f"{function.title()}_Final"
        df[f"{function.title()}_Exec"] = df[col].map(DISPLAY_MAPPING[function]).fillna(df[col])
    return df


@st.cache_data
def load_benchmark():
    for path in BENCHMARK_JSON_CANDIDATES:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    return None


report_mtime = os.path.getmtime(REPORT_CSV) if os.path.exists(REPORT_CSV) else None
df = load_report(report_mtime)
benchmark_data = load_benchmark()

if df is None:
    st.warning(f"'{REPORT_CSV}' not found. Run `python laya_risk_engine.py` first, then reload this page.")
    st.stop()

# -----------------------------------------------------------------------------
# Header
# -----------------------------------------------------------------------------
left, right = st.columns([3, 1])
with left:
    st.title("AI Risk & Regulatory Compliance Posture")
    st.caption("EU AI Act exposure and NIST AI RMF maturity across the enterprise AI inventory.")
with right:
    st.metric("Assets Tracked", len(df))
    st.caption(f"Last scored: {datetime.fromtimestamp(report_mtime):%b %d, %Y %H:%M}")

# -----------------------------------------------------------------------------
# One-glance posture banner
# -----------------------------------------------------------------------------
n_blocked_critical = df["Action_Priority"].str.contains("CRITICAL|BLOCKED", na=False, regex=True).sum()
n_manual = df["Action_Priority"].str.contains("Manual", na=False).sum()
n_escalate = df["Action_Priority"].str.contains("Escalate", na=False).sum()

if n_blocked_critical > 0:
    st.markdown(
        f'<div class="posture-banner" style="background:{ACTION_COLOR["CRITICAL - Immediate Remediation"]}">'
        f'\U0001F534 ACTION REQUIRED &mdash; {n_blocked_critical} asset(s) blocked or need immediate remediation</div>',
        unsafe_allow_html=True,
    )
elif n_manual > 0 or n_escalate > 0:
    st.markdown(
        f'<div class="posture-banner" style="background:{ACTION_COLOR["High - Requires Conformity Assessment"]}">'
        f'\U0001F7E1 REVIEW NEEDED &mdash; {n_manual} low-confidence and {n_escalate} disagreement case(s) awaiting human review</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f'<div class="posture-banner" style="background:{ACTION_COLOR["Monitor"]}">'
        f'\U0001F7E2 PORTFOLIO HEALTHY &mdash; no blocked, critical, or unreviewed assets</div>',
        unsafe_allow_html=True,
    )

tab1, tab2 = st.tabs(["\U0001F4CA  Risk Portfolio", "\U0001F916  Engine Reliability"])

# =============================================================================
# TAB 1: Risk Portfolio
# =============================================================================
with tab1:
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown('<div class="kpi-total">', unsafe_allow_html=True)
        st.metric("Total AI Inventory", len(df))
        st.markdown("</div>", unsafe_allow_html=True)
    with k2:
        st.markdown('<div class="kpi-critical">', unsafe_allow_html=True)
        st.metric("Critical / Blocked", int(n_blocked_critical))
        st.markdown("</div>", unsafe_allow_html=True)
    with k3:
        st.markdown('<div class="kpi-manual">', unsafe_allow_html=True)
        st.metric("Needs Human Review", int(n_manual + n_escalate))
        st.markdown("</div>", unsafe_allow_html=True)
    with k4:
        st.markdown('<div class="kpi-approved">', unsafe_allow_html=True)
        st.metric("Auto-Approved (clean posture)", int(df["Is_Approved"].astype(bool).sum()))
        st.markdown("</div>", unsafe_allow_html=True)

    if "Undisclosed_Risk_Flag" in df and df["Undisclosed_Risk_Flag"].astype(bool).any():
        n = int(df["Undisclosed_Risk_Flag"].astype(bool).sum())
        st.warning(f"\u26a0\ufe0f Laya flagged {n} asset(s) as High/Prohibited Risk with no matching EU AI Act trigger disclosed on intake.")

    st.markdown("### Portfolio at a glance")
    c1, c2 = st.columns([1, 1])

    with c1:
        tier_counts = df["EU_Risk_Tier"].value_counts().reindex(
            ["Prohibited Risk", "High Risk", "Limited Risk", "Minimal Risk"]).fillna(0).astype(int)
        fig = go.Figure(go.Pie(
            labels=[f"{TIER_ICON[t]} {t}" for t in tier_counts.index],
            values=tier_counts.values, hole=0.55,
            marker=dict(colors=[TIER_COLOR[t] for t in tier_counts.index]),
            textinfo="value+percent", sort=False,
        ))
        fig.update_layout(title="EU AI Act Risk Tier", height=320, margin=dict(t=40, b=0, l=0, r=0),
                           showlegend=True, legend=dict(orientation="h", y=-0.1))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        action_counts = df["Action_Priority"].value_counts()
        order = [a for a in ACTION_COLOR if a in action_counts.index]
        action_counts = action_counts.reindex(order).dropna()
        fig2 = go.Figure(go.Bar(
            x=action_counts.values, y=[a.split(" - ")[0].split(" (")[0] for a in action_counts.index],
            orientation="h", marker=dict(color=[ACTION_COLOR[a] for a in action_counts.index]),
            text=action_counts.values, textposition="outside",
        ))
        fig2.update_layout(title="Required Action", height=320, margin=dict(t=40, b=0, l=0, r=20),
                            xaxis_title="Assets", yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("### NIST AI RMF maturity (portfolio average)")
    nist_cols = st.columns(4)
    for col, function in zip(nist_cols, NIST_SUBCHECKS):
        score_col = f"{function.title()}_Final"
        scores = df[score_col].apply(lambda s: {"Level 1": 1, "Level 2": 2, "Level 3": 3, "Level 4": 4}.get(s, 1))
        avg = scores.mean()
        pct = avg / 4
        color = "#D9534F" if avg < 2 else ("#F0AD4E" if avg < 3 else "#4CAF50")
        with col:
            st.markdown(f"**{function.upper()}**")
            st.progress(pct)
            st.markdown(f"<span style='color:{color};font-weight:600'>Avg Level {avg:.1f} / 4</span>", unsafe_allow_html=True)

    st.divider()
    st.markdown("### Enterprise AI Asset Register")
    tier_filter = st.selectbox("Filter by regulatory exposure:", ["All Assets", "Prohibited Risk", "High Risk", "Limited Risk", "Minimal Risk"])
    view_df = df if tier_filter == "All Assets" else df[df["EU_Risk_Tier"] == tier_filter]

    presentation_df = view_df.copy()
    presentation_df["EU Risk Tier"] = presentation_df["EU_Risk_Tier"].apply(lambda t: f"{TIER_ICON.get(t, '')} {t}")
    presentation_df = presentation_df[[
        "Name", "EU Risk Tier", "EU_Confidence",
        "Govern_Exec", "Map_Exec", "Measure_Exec", "Manage_Exec", "Action_Priority",
    ]].rename(columns={
        "Govern_Exec": "Govern", "Map_Exec": "Map", "Measure_Exec": "Measure", "Manage_Exec": "Manage",
        "EU_Confidence": "AI Certainty", "Action_Priority": "Action Required",
    })

    def style_action(val):
        color = ACTION_COLOR.get(val, "#888")
        return f"background-color: {color}22; color: {color}; font-weight: 600;"

    st.caption("Select a row below to see the full compliance breakdown.")
    event = st.dataframe(
        presentation_df.style.map(style_action, subset=["Action Required"]),
        use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row",
    )

    with st.expander("Regulatory definitions & methodology"):
        st.markdown(
            """
* **EU High-Risk trigger:** a developer-disclosed Annex III use case (credit, HR, biometrics, critical infrastructure). This can only *escalate* the tier -- it never overrides a higher tier Laya identifies on its own.
* **AI Certainty:** Laya's predicted probability for the chosen EU risk tier. Below 85%, the asset is routed to manual review regardless of the deterministic score.
* **NIST Govern:** the more conservative of the questionnaire's weighted composite and Laya's semantic read (Laya is fine-tuned on this function).
* **NIST Map / Measure / Manage:** the questionnaire's weighted composite. Laya's read on these is advisory only (zero-shot, not yet fine-tuned) and only raises a review flag when it disagrees by 2+ levels.
"""
        )

    st.divider()
    selected = event.selection.rows
    if selected:
        asset_name = presentation_df.iloc[selected[0]]["Name"]
        asset = df[df["Name"] == asset_name].iloc[0]
        trace = json.loads(asset["Decision_Trace"])
        tier = asset["EU_Risk_Tier"]

        st.markdown(f"## {TIER_ICON.get(tier, '')} {asset['Name']}")
        hdr1, hdr2, hdr3, hdr4 = st.columns(4)
        hdr1.metric("Regulatory Exposure", tier)
        hdr2.metric("AI Certainty", asset["EU_Confidence"])
        hdr3.metric("Action", asset["Action_Priority"].split(" - ")[0].split(" (")[0])
        hdr4.metric("Auto-Approved", "Yes" if asset["Is_Approved"] else "No")

        if trace["decision"]["undisclosed_risk"]:
            st.error("Semantic model flagged risk not disclosed on intake.")
        if trace["decision"]["any_disagreement"]:
            st.warning("Deterministic and semantic scores disagree by 2+ levels on at least one NIST function.")

        d1, d2 = st.columns([1, 1])
        with d1:
            st.markdown("#### NIST maturity profile")
            funcs = list(NIST_SUBCHECKS.keys())
            final_scores = [trace["decision"].get(f"{f}_final_score" if f != "govern" else "govern_final_score", 1) for f in funcs]
            fig3 = go.Figure(go.Bar(
                x=[f.upper() for f in funcs], y=final_scores,
                marker=dict(color=["#D9534F" if s < 2 else ("#F0AD4E" if s < 3 else "#4CAF50") for s in final_scores]),
                text=[f"{s:.1f}" for s in final_scores], textposition="outside",
            ))
            fig3.add_hline(y=2.5, line_dash="dash", line_color="gray", annotation_text="Approval baseline")
            fig3.update_layout(height=300, yaxis=dict(range=[0, 4.3], title="Level"), margin=dict(t=10, b=0, l=0, r=0))
            st.plotly_chart(fig3, use_container_width=True)

        with d2:
            st.markdown("#### EU AI Act triggers disclosed on intake")
            trig_df = pd.DataFrame(
                [{"Trigger": k.replace("_", " ").title(), "Disclosed": "\u2705 Yes" if v else "\u2014 No"}
                 for k, v in trace["triggers"].items()]
            )
            st.dataframe(trig_df, hide_index=True, use_container_width=True)

        st.markdown("#### Sub-check detail")
        rows_out = []
        for function in NIST_SUBCHECKS:
            final_key = f"{function}_final_score" if function != "govern" else "govern_final_score"
            rows_out.append({
                "NIST Function": function.upper(),
                "Questionnaire composite": trace["decision"].get(f"{function}_composite" if function == "govern" else f"{function}_final_score"),
                "Laya semantic read": trace["semantic"].get(f"nist_{function}", "n/a (advisory)"),
                "Final (conservative)": trace["decision"].get(final_key),
                "Disagreement flagged": "\u26a0\ufe0f Yes" if trace["decision"].get(f"{function}_disagreement") else "No",
            })
            for item_key, level in trace["nist_subchecks"][function].items():
                rows_out.append({
                    "NIST Function": f"    \u2514 {NIST_SUBCHECKS[function]['items'][item_key]['question']}",
                    "Questionnaire composite": level, "Laya semantic read": "",
                    "Final (conservative)": "", "Disagreement flagged": "",
                })
        st.dataframe(pd.DataFrame(rows_out), hide_index=True, use_container_width=True)
    else:
        st.info("Select an asset above to inspect its NIST sub-checks and the reasoning behind its score.")

# =============================================================================
# TAB 2: Engine Reliability
# =============================================================================
with tab2:
    st.markdown("### Laya Model Reliability Scorecard")
    st.caption("Measured by `test_laya_suite.py` against a golden test set with known-correct answers.")

    if benchmark_data:
        m = benchmark_data["metrics"]
        acc, ece, lat = m.get("accuracy", 0), m.get("ece", 0), m.get("latency_p50_ms", 0)
        acc_color = "#4CAF50" if acc >= 0.9 else ("#F0AD4E" if acc >= 0.75 else "#D9534F")
        ece_color = "#4CAF50" if ece < 0.10 else ("#F0AD4E" if ece < 0.20 else "#D9534F")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"<h2 style='color:{acc_color}'>{acc * 100:.1f}%</h2>", unsafe_allow_html=True)
            st.caption("Golden-Set Accuracy")
        with c2:
            st.markdown(f"<h2 style='color:{ece_color}'>{ece * 100:.1f}%</h2>", unsafe_allow_html=True)
            st.caption("Calibration Error (lower is better)")
        with c3:
            st.markdown(f"<h2>{lat:.0f} ms</h2>", unsafe_allow_html=True)
            st.caption("Median Latency")
        with c4:
            st.markdown("<h2>100% On-Prem</h2>", unsafe_allow_html=True)
            st.caption("Data Privacy Standard")

        st.divider()
        rc1, rc2 = st.columns(2)
        rc1.markdown(("\u2705 " if m.get("robustness_consistent") else "\u274c ") +
                      "Consistent classification across paraphrased descriptions")
        rc2.markdown(("\u2705 " if m.get("ambiguous_case_appropriately_uncertain") else "\u274c ") +
                      "Hedges (lower confidence) on genuinely ambiguous input")

        st.caption(
            "This reflects only what test_laya_suite.py measured on this model. It does not "
            "include a commercial-API comparison unless that suite was run with a live API key."
        )
        if "comparison" in benchmark_data:
            st.subheader("Head-to-Head Comparison (measured, not estimated)")
            st.dataframe(pd.DataFrame(benchmark_data["comparison"]), use_container_width=True, hide_index=True)
    else:
        st.info("No benchmark report found. Run `python test_laya_suite.py` to generate one.")
