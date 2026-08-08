"""Smart QS Copilot - Streamlit app.
Upload a BOQ (CSV/Excel/PDF text) -> parse -> estimate -> anomalies -> plain-language review.
Deploy target: Hugging Face Spaces (free, no server)."""
import io
import json
import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.parser import enrich, parse_csv, parse_pdf, parse_pdf_text
from src.estimator import estimate
from src.anomalies import detect, summary as flag_summary
from src.llm import llm_review, fallback_review

st.set_page_config(page_title="Smart QS Copilot", page_icon="🏗️", layout="wide")

st.title("🏗️ Smart QS Copilot")
st.caption(
    "AI screening for Bills of Quantities: parse, estimate, and flag anomalies "
    "against HK construction reference rates. Built for the Smart QS Hackathon 2026. "
    "Reference-based screening, not pricing advice."
)

uploaded = st.file_uploader("Upload a BOQ (CSV / Excel / PDF text)", type=["csv", "xlsx", "xls", "txt", "pdf"])
use_sample = st.button("Try the sample BOQ", type="primary")

rows = None
if use_sample:
    sample = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples", "sample_boq.csv")
    with open(sample, encoding="utf-8") as f:
        rows = parse_csv(f.read())
    st.info("Loaded sample BOQ (contains deliberately planted anomalies so you can see the flags).")
elif uploaded is not None:
    if uploaded.name.lower().endswith(".pdf"):
        rows = parse_pdf(uploaded.getvalue())
    elif uploaded.name.lower().endswith((".csv", ".txt")):
        raw = uploaded.getvalue().decode("utf-8", errors="ignore")
        rows = parse_csv(raw) if uploaded.name.lower().endswith(".csv") else parse_pdf_text(raw)
    else:
        try:
            df = pd.read_excel(uploaded)
            rows = parse_csv(df.to_csv(index=False))
        except Exception as e:
            st.error(f"Could not read {uploaded.name}: {e}")
    if not rows:
        st.error("No items parsed. Check that the file contains a recognizable BOQ table.")

if rows:
    rows = enrich(rows)
    flags = detect(rows)
    est = estimate(rows)

    c1, c2, c3 = st.columns(3)
    c1.metric("Items parsed", len(rows))
    c2.metric("Estimated total", f"HK${est['grand_total']:,.0f}", help=est["confidence"])
    c3.metric("Flags", flag_summary(flags))

    st.subheader("📋 Items")
    df = pd.DataFrame(rows)
    st.dataframe(
        df[["section", "item", "description", "unit", "qty", "rate", "ref_rate"]],
        use_container_width=True, hide_index=True,
    )

    st.subheader("🚨 Anomaly flags")
    if flags:
        for f in flags:
            icon = {"critical": "🔴", "warning": "🟠", "info": "🔵"}[f["severity"]]
            sev = f["severity"].upper()
            st.markdown(f"**{icon} [{sev}] {f['description']}**  \n{f['detail']}")
    else:
        st.success("No anomalies detected.")

    st.subheader("🧮 Estimate by trade")
    trades_df = pd.DataFrame(
        [{"Trade": k, "Amount": v["amount"], "Items": v["count"]} for k, v in est["trades"].items()]
    ).sort_values("Amount", ascending=False)
    st.dataframe(trades_df, use_container_width=True, hide_index=True)
    st.caption(
        f"Items total HK${est['items_total']:,.0f} + preliminaries {est['preliminaries']/est['items_total']*100:.0f}% "
        f"HK${est['preliminaries']:,.0f} + contingency {est['contingency']/est['items_total']*100:.0f}% "
        f"HK${est['contingency']:,.0f} = **HK${est['grand_total']:,.0f}**"
    )

    st.subheader("🧠 Plain-language review")
    review, status = llm_review(len(rows), est["trades"], flags, est["grand_total"])
    if status != "llm_ok":
        review = fallback_review(flags, est["grand_total"])
        st.caption("(rule-based fallback; LLM review unavailable)")
    # escape $ so Streamlit does not treat amounts as LaTeX math (renders letter-spaced)
    st.markdown(review.replace("$", "\\$"))

    st.subheader("🏛️ Market context")
    try:
        ctx = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "hk_tenders.json"), encoding="utf-8"))
        for t in ctx["tenders"]:
            st.markdown(f"- **{t['ref']}** — {t['title']} ({t['authority']})")
        st.caption(ctx.get("market_notes", ""))
    except Exception:
        pass
