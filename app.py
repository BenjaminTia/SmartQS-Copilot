"""Smart QS Copilot — Streamlit app.
Upload a BOQ (PDF/CSV/Excel) -> parse -> estimate -> anomalies -> plain-language review.
Deploy target: Streamlit Community Cloud (free, no server)."""
import io
import json
import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.parser import parse_csv, parse_pdf, parse_pdf_text, enrich
from src.estimator import estimate
from src.anomalies import detect, summary as flag_summary
from src.llm import llm_review, fallback_review

st.set_page_config(page_title="Smart QS Copilot", page_icon="🏗️", layout="wide")

CSS = """
<style>
.block-container { padding-top: 4.2rem; padding-bottom: 3rem; max-width: 1120px; }

/* header */
.app-header { display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.4rem; }
.app-logo { font-size: 2.1rem; line-height: 1; }
.app-title { font-size: 1.6rem; font-weight: 700; letter-spacing: -0.02em; color: #F2F0EA; }
.app-tag { font-size: 0.92rem; color: #9AA3AC; margin-top: 0.1rem; }
.app-badge { display: inline-block; margin-top: 0.35rem; font-size: 0.72rem; font-weight: 600;
  color: #F5A623; border: 1px solid #F5A62355; border-radius: 99px; padding: 0.12rem 0.6rem; }

/* intro panel */
.intro-panel { background: linear-gradient(180deg, #1A2026, #161C21); border: 1px solid #2A323A;
  border-radius: 14px; padding: 1rem 1.3rem; margin: 0.8rem 0 0.2rem; }
.intro-lead { font-size: 0.98rem; line-height: 1.6; color: #DDE2E8; margin-bottom: 0.5rem; }
.intro-sub { font-size: 0.9rem; line-height: 1.55; color: #9AA3AC; }

/* section titles */
.section-title { font-size: 1.05rem; font-weight: 700; margin: 1.6rem 0 0.6rem; color: #F2F0EA;
  display: flex; align-items: center; gap: 0.45rem; }

/* summary cards */
.card-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.9rem; margin: 0.8rem 0 0.4rem; }
.card { background: #1A2026; border: 1px solid #2A323A; border-radius: 14px; padding: 0.9rem 1.1rem; }
.card-label { font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: #9AA3AC; }
.card-value { font-size: 1.55rem; font-weight: 700; margin-top: 0.25rem; letter-spacing: -0.01em; }
.card-sub { font-size: 0.78rem; color: #9AA3AC; margin-top: 0.25rem; }
.card-money .card-value { color: #F2F0EA; }
.card-risk .card-value { color: #EF6A5B; }
.card-risk { border-color: #EF6A5B66; }

/* flag cards */
.flag { border-radius: 12px; padding: 0.7rem 1rem; margin-bottom: 0.55rem; border: 1px solid; }
.flag-critical { background: #2A1517; border-color: #EF6A5B66; }
.flag-warning { background: #2A2113; border-color: #F5A62366; }
.flag-info { background: #15202B; border-color: #5B9DEF66; }
.flag-head { font-weight: 700; font-size: 0.95rem; display: flex; align-items: center; gap: 0.5rem; }
.flag-badge { font-size: 0.68rem; font-weight: 700; letter-spacing: 0.05em; border-radius: 6px;
  padding: 0.14rem 0.5rem; text-transform: uppercase; }
.flag-critical .flag-badge { background: #EF6A5B; color: #1A1010; }
.flag-warning .flag-badge { background: #F5A623; color: #1A1410; }
.flag-info .flag-badge { background: #5B9DEF; color: #101A24; }
.flag-detail { font-size: 0.88rem; color: #C6CDD4; margin-top: 0.3rem; line-height: 1.5; }

/* review panel */
.review-panel { background: linear-gradient(180deg, #1A2026, #161C21); border: 1px solid #2A323A;
  border-radius: 14px; padding: 1.1rem 1.3rem; font-size: 0.98rem; line-height: 1.65; color: #DDE2E8; }

/* state line */
.state-line { font-size: 0.85rem; color: #9AA3AC; margin-top: 0.5rem; }

/* buttons */
.stButton > button { border-radius: 10px; font-weight: 600; }
.stButton > button[kind="primary"] { background: #F5A623; color: #1A1410; border: none; }
.stButton > button[kind="primary"]:hover { background: #FFB83D; color: #1A1410; }
.stButton > button[kind="secondary"] { border-color: #3A444E; color: #C6CDD4; }

/* uploader */
[data-testid="stFileUploader"] section { border-radius: 12px; border: 1px dashed #3A444E; }
[data-testid="stFileUploader"] section:hover { border-color: #F5A62388; }

/* expander */
[data-testid="stExpander"] details { border: 1px solid #2A323A; border-radius: 12px; background: #161C21; }

/* dataframe */
[data-testid="stDataFrame"] { border-radius: 12px; border: 1px solid #2A323A; overflow: hidden; }

/* footer */
.app-footer { margin-top: 2.2rem; padding-top: 0.9rem; border-top: 1px solid #232B33;
  font-size: 0.78rem; color: #6E7680; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------- header
st.markdown(
    '<div class="app-header"><span class="app-logo">🏗️</span>'
    '<div><div class="app-title">Smart QS Copilot</div>'
    '<div class="app-tag">Check Bills of Quantities against Hong Kong construction reference rates</div>'
    '<span class="app-badge">Smart QS Hackathon 2026</span></div></div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- intro
st.markdown(
    '<div class="intro-panel">'
    '<div class="intro-lead">A <b>Bill of Quantities (BOQ)</b> is the itemized list of the materials, labor '
    'and work a construction project needs, from concrete to door handles. One incorrect rate can '
    'significantly affect a contract, but finding it in a long BOQ is usually slow and manual.</div>'
    '<div class="intro-sub">Smart QS Copilot parses your BOQ, compares item rates with Hong Kong '
    'reference data, and highlights unusual values, possible typos and missing items, then explains '
    'the findings in plain language. Typically under a minute per document. Built for quantity '
    'surveyors and project managers; results should be verified by a qualified professional.</div></div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- input zone
c_in, c_sample = st.columns([2.2, 1], vertical_alignment="center")
with c_in:
    uploaded = st.file_uploader(
        "Drop a BOQ here, or browse",
        type=["csv", "xlsx", "xls", "txt", "pdf"],
        help="Text-based PDFs are supported. Scanned PDFs need OCR first.",
    )
with c_sample:
    sample_clicked = st.button(
        "Reload demo BOQ" if "demo_loaded" in st.session_state else "Load demo BOQ",
        type="primary",
        width="stretch",
    )

rows = None
source_name = None
if sample_clicked:
    sample_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples", "sample_boq.csv")
    with open(sample_path, encoding="utf-8") as f:
        rows = parse_csv(f.read())
    source_name = "demo BOQ"
    st.session_state["demo_loaded"] = True
    st.markdown(
        '<div class="state-line">✅ Demo loaded: 27 items with 4 planted anomalies. '
        "Every one should get caught.</div>",
        unsafe_allow_html=True,
    )
elif uploaded is not None:
    raw = uploaded.getvalue().decode("utf-8", errors="ignore")
    name = uploaded.name.lower()
    if name.endswith(".pdf"):
        rows = parse_pdf(uploaded.getvalue())
    elif name.endswith(".csv"):
        rows = parse_csv(raw)
    else:
        try:
            df = pd.read_excel(uploaded)
            rows = parse_csv(df.to_csv(index=False))
        except Exception as e:
            st.error(f"Could not read {uploaded.name}: {e}")
    source_name = uploaded.name
    if not rows:
        st.error("No items parsed. For scanned PDFs, export text first.")

# ---------------------------------------------------------------- results
if rows:
    rows = enrich(rows)
    flags = detect(rows)
    est = estimate(rows)
    n_crit = sum(1 for f in flags if f["severity"] == "critical")
    n_warn = sum(1 for f in flags if f["severity"] == "warning")
    n_info = sum(1 for f in flags if f["severity"] == "info")

    # summary cards
    risk_cls = "card-risk" if n_crit else ""
    st.markdown(
        f"""
        <div class="card-row">
          <div class="card"><div class="card-label">Items parsed</div>
            <div class="card-value">{len(rows)}</div>
            <div class="card-sub">rows recognized</div></div>
          <div class="card card-money"><div class="card-label">Estimated total</div>
            <div class="card-value">HK${est['grand_total']:,.0f}</div>
            <div class="card-sub">incl. preliminaries + contingency · reference-based</div></div>
          <div class="card {risk_cls}"><div class="card-label">Flags</div>
            <div class="card-value">{len(flags)}</div>
            <div class="card-sub">{n_crit} critical · {n_warn} warnings{f' · {n_info} info' if n_info else ''}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # flags
    st.markdown('<div class="section-title">🚨 What to check</div>', unsafe_allow_html=True)
    if flags:
        for f in flags:
            sev = f["severity"]
            icon = {"critical": "🔴", "warning": "🟠", "info": "🔵"}[sev]
            st.markdown(
                f'<div class="flag flag-{sev}"><div class="flag-head">'
                f'<span class="flag-badge">{icon} {sev}</span>'
                f'<span>{f["description"]}</span></div>'
                f'<div class="flag-detail">{f["detail"]}</div></div>',
                unsafe_allow_html=True,
            )
    else:
        st.success("No anomalies detected. The BOQ looks internally consistent.")

    # review
    st.markdown('<div class="section-title">🧠 Plain-language review</div>', unsafe_allow_html=True)
    review, status = llm_review(len(rows), est["trades"], flags, est["grand_total"])
    if not status.startswith("llm_ok"):
        review = fallback_review(flags, est["grand_total"])
        st.caption(f"Rule-based fallback ({status}).")
    safe_review = review.replace("$", "\\$")
    st.markdown(f'<div class="review-panel">{safe_review}</div>', unsafe_allow_html=True)

    # items table
    st.markdown('<div class="section-title">📋 Items</div>', unsafe_allow_html=True)
    df = pd.DataFrame(rows)
    flag_of = {}
    for f in flags:
        flag_of.setdefault(f["item"], []).append(f["severity"])
    df["Flag"] = df["item"].map(
        lambda i: "🔴" if "critical" in flag_of.get(i, []) else
        ("🟠" if flag_of.get(i) else "")
    )
    df["Ref rate"] = df["ref_rate"].map(lambda v: "" if v is None else f"HK${v:,.0f}")
    df["Rate"] = df["rate"].map(lambda v: "" if v is None else f"HK${v:,.0f}")
    df["Amount"] = (df["qty"] * df["rate"]).map(lambda v: "" if v == 0 else f"HK${v:,.0f}")
    view = df[["item", "section", "description", "unit", "qty", "Rate", "Ref rate", "Amount", "Flag"]].rename(
        columns={"item": "Item", "section": "Section", "description": "Description", "unit": "Unit", "qty": "Qty"}
    )
    st.dataframe(view, width="stretch", hide_index=True)
    st.download_button(
        "⬇️ Download screening as CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="boq_screening.csv",
        mime="text/csv",
    )

    # methodology
    with st.expander("How the screening works"):
        st.markdown(
            "- **Parse**: structure-aware extraction of items, units, quantities and rates (PDF, CSV, Excel)\n"
            "- **Estimate**: trade rollup plus 8% preliminaries and 5% contingency, clearly marked as reference-based\n"
            "- **Flag**: rate deviations over +-50% against HK reference rates, duplicate items, missing "
            "access or safety sections, and line-total outliers\n"
            "- **Explain**: an LLM turns the flags into plain language, with the raw analysis in the table above\n\n"
            "Reference rates are a screening baseline (HK market, 2025-26), not pricing advice. "
            "Always confirm flagged items against the tender drawings and original quotes."
        )

    # footer
    st.markdown(
        '<div class="app-footer">Built for the Smart QS Hackathon 2026 · Housing Bureau + Cyberport + HKU. '
        "Screening only: final pricing stays with a qualified quantity surveyor.</div>",
        unsafe_allow_html=True,
    )
