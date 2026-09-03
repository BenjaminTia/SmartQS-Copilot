"""Smart QS Copilot v2 - Streamlit app.

Five-step Hong Kong post-award workflow, built around the BOQ:
  1. Upload (PDF / CSV / XLSX)
  2. Trade map and flags
  3. Fair-rate build-up
  4. Cashflow (S-curve and interim payment gap)
  5. Security of Payment documents (Cap. 652)

Every analysis step is deterministic software; the optional plain-language
review at the end is prose only and falls back to rules offline.
"""
import os
import sys
from datetime import date

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.anomalies import detect
from src.cashflow import interim_payment_gap, s_curve_cashflow
from src.estimator import estimate
from src.llm import fallback_review, llm_review
from src.parser import parse_csv, parse_excel, parse_pdf, parse_pdf_text, enrich
from src import fairrate, hksmm, sor, sop652

REPO = os.path.dirname(os.path.abspath(__file__))
SAMPLE_CSV = os.path.join(REPO, "samples", "sample_boq_messy.csv")
SAMPLE_XLSX = os.path.join(REPO, "samples", "sample_boq_messy.xlsx")

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
.flag-meta { font-size: 0.82rem; color: #F5A623; margin-top: 0.3rem; }
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

/* disclaimers */
.disclaimer { font-size: 0.82rem; color: #9AA3AC; background: #161C21; border: 1px solid #2A323A;
  border-radius: 10px; padding: 0.6rem 0.9rem; margin: 0.6rem 0; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------- helpers


def _parse_upload(uploaded):
    name = (uploaded.name or "").lower()
    data = uploaded.getvalue()
    if name.endswith(".pdf"):
        return parse_pdf(data)
    if name.endswith((".xlsx", ".xls")):
        return parse_excel(data)
    if name.endswith(".txt"):
        return parse_pdf_text(data.decode("utf-8", errors="ignore"))
    return parse_csv(data.decode("utf-8", errors="ignore"))


def _store_rows(rows, source_name):
    st.session_state["rows"] = enrich(rows)
    st.session_state["source"] = source_name


def _build_flags(rows):
    """Merge every rule-based flag source into one list for display."""
    rows_by_item = {r["item"]: r for r in rows if r.get("item")}
    flags = list(detect(rows))
    flags += hksmm.scan_missing_trades(rows)
    flags += hksmm.find_duplicates(rows)
    for r in rows:
        is_bi, ratio = hksmm.detect_bilingual(r["description"])
        if is_bi:
            flags.append({
                "severity": "info",
                "type": "bilingual",
                "item": r["item"],
                "description": "Bilingual description (English + Chinese)",
                "detail": f"Description mixes English and Chinese (Chinese ratio {ratio:.0%}). "
                          "Not an error; check it matches the tender text.",
            })
    for f in flags:
        r = rows_by_item.get(f.get("item"))
        f.setdefault("number", None)
        f.setdefault("reference", None)
        if r is not None and f.get("type") == "rate":
            f["number"] = r.get("rate")
            f["reference"] = r.get("ref_rate")
    order = {"critical": 0, "warning": 1, "info": 2}
    flags.sort(key=lambda f: (order.get(f["severity"], 3), f.get("item") or "zzz"))
    return flags


def _flag_meta(f):
    parts = []
    if f.get("item") and f.get("item") != "-":
        parts.append(f"Item {f['item']}")
    if f.get("number") is not None:
        parts.append(f"rate HK${f['number']:,.2f}")
    if f.get("reference") is not None:
        parts.append(f"reference HK${f['reference']:,.2f}")
    return "  ·  ".join(parts)


def _flag_card(f):
    sev = f["severity"]
    icon = {"critical": "🔴", "warning": "🟠", "info": "🔵"}[sev]
    meta = _flag_meta(f)
    meta_html = f'<div class="flag-meta">{meta}</div>' if meta else ""
    return (
        f'<div class="flag flag-{sev}"><div class="flag-head">'
        f'<span class="flag-badge">{icon} {sev}</span>'
        f'<span>{f["description"]}</span></div>'
        f'{meta_html}'
        f'<div class="flag-detail">{f["detail"]}</div></div>'
    )


def _boq_summary(rows, est):
    trade_names = list(est["trades"].keys())
    names = ", ".join(trade_names[:5])
    if len(trade_names) > 5:
        names += f" and {len(trade_names) - 5} more"
    return (
        f"Measured works across {len(rows)} items in {len(trade_names)} trades "
        f"({names}), totalling HK${est['grand_total']:,.0f} reference-based."
    )


# ---------------------------------------------------------------- header
st.markdown(
    '<div class="app-header"><span class="app-logo">🏗️</span>'
    '<div><div class="app-title">Smart QS Copilot</div>'
    '<div class="app-tag">Hong Kong post-award workflow: from BOQ to payment claim</div>'
    '<span class="app-badge">Smart QS Hackathon 2026</span></div></div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="intro-panel">'
    '<div class="intro-lead">Money in Hong Kong construction is often lost <b>after</b> award: '
    're-measurement, variations, interim payment and Security of Payment (Cap. 652) compliance. '
    'One BOQ upload takes you from <b>cost to compliance to cashflow to documents</b>, in a '
    'Hong-Kong-native flow.</div>'
    '<div class="intro-sub">The analysis is deterministic software (parse, classify, flag, '
    'build-up, dates). It never claims accuracy and always shows which rate, rule or section '
    'drove each result. Screening only: final pricing and legal steps stay with a qualified '
    'quantity surveyor or lawyer.</div></div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- parse input
uploaded = st.file_uploader(
    "Drop a BOQ here, or browse (PDF / CSV / XLSX)",
    type=["csv", "xlsx", "xls", "txt", "pdf"],
    help="Text-based PDFs are supported. Scanned PDFs need OCR first.",
)

c_sample, c_xlsx = st.columns(2)
sample_clicked = c_sample.button("Try a messy sample BOQ (CSV)", type="secondary", width="stretch")
xlsx_clicked = False
if os.path.exists(SAMPLE_XLSX):
    xlsx_clicked = c_xlsx.button("Try the messy sample with merged cells (XLSX)", type="secondary", width="stretch")

if sample_clicked:
    with open(SAMPLE_CSV, encoding="utf-8") as fh:
        _store_rows(parse_csv(fh.read()), "sample_boq_messy.csv")
elif xlsx_clicked:
    with open(SAMPLE_XLSX, "rb") as fh:
        _store_rows(parse_excel(fh.read()), "sample_boq_messy.xlsx")
elif uploaded is not None:
    rows = _parse_upload(uploaded)
    if rows:
        _store_rows(rows, uploaded.name)
    else:
        st.error("No items parsed. For scanned PDFs, export text first.")

rows = st.session_state.get("rows")
if rows:
    st.markdown(
        f'<div class="state-line">Parsed {len(rows)} items from '
        f'{st.session_state.get("source", "upload")}.</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------- steps
if rows:
    est = estimate(rows)
    flags = _build_flags(rows)
    sor_lookup = sor.load_sor()
    proj_index = sor.project_rate_index(rows)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "1. Upload", "2. Trade map & flags", "3. Fair rate build-up",
        "4. Cashflow", "5. Security of Payment",
    ])

    # ================= Step 1: Upload =================
    with tab1:
        st.markdown('<div class="section-title">📁 Upload</div>', unsafe_allow_html=True)
        st.markdown(
            "Drop a BOQ above and it flows through the five steps below. The parser "
            "tolerates messy real-world files: leading title rows, more than one header "
            "row, item codes, mixed English and Traditional Chinese descriptions, and "
            "merged trade cells (forward-filled)."
        )
        n_crit = sum(1 for f in flags if f["severity"] == "critical")
        n_warn = sum(1 for f in flags if f["severity"] == "warning")
        n_info = sum(1 for f in flags if f["severity"] == "info")
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

    # ================= Step 2: Trade map & flags =================
    with tab2:
        st.markdown('<div class="section-title">🗺️ Trade map and flags</div>', unsafe_allow_html=True)

        classified = []
        for r in rows:
            code, trade_en, score = hksmm.classify_trade(r["description"])
            classified.append((code or "", trade_en, round(score, 2)))
        df = pd.DataFrame(rows)
        df["Trade"] = [f"{c} · {t}" for c, t, _ in classified]
        df["Confidence"] = [s for _, _, s in classified]
        df["Amount"] = (df["qty"].fillna(0) * df["rate"].fillna(0)).map(lambda v: f"HK${v:,.0f}")
        view = df[["item", "section", "description", "unit", "qty", "rate", "Amount", "Trade", "Confidence"]].rename(
            columns={
                "item": "Item", "section": "Section", "description": "Description",
                "unit": "Unit", "qty": "Qty", "rate": "Rate (HK$)", "Trade": "Trade (HKSMM)",
            }
        )
        st.dataframe(view, width="stretch", hide_index=True, height=360)
        st.download_button(
            "Download screening as CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="boq_screening.csv",
            mime="text/csv",
        )

        st.markdown('<div class="section-title">🚩 What to check</div>', unsafe_allow_html=True)
        crit = [f for f in flags if f["severity"] == "critical"]
        warn = [f for f in flags if f["severity"] == "warning"]
        info = [f for f in flags if f["severity"] == "info"]
        if not flags:
            st.success("No flags raised. The BOQ looks internally consistent; still worth a QS eye for scope omissions.")
        for f in crit + warn:
            st.markdown(_flag_card(f), unsafe_allow_html=True)
        if info:
            with st.expander(f"{len(info)} informational note(s), mostly bilingual descriptions"):
                for f in info:
                    st.markdown(_flag_card(f), unsafe_allow_html=True)

    # ================= Step 3: Fair rate build-up =================
    with tab3:
        st.markdown('<div class="section-title">🧮 Fair rate build-up</div>', unsafe_allow_html=True)
        st.markdown(
            "When a rate looks off, build up a rough fair rate from the demo SoR reference, "
            "scaled by this BOQ's own rate index, then split it into labour, material, plant, "
            "overheads and profit. The arithmetic is shown, not hidden."
        )
        st.markdown(
            '<div class="disclaimer">SoR figures are indicative demo values, not the official '
            'ArchSD Schedule of Rates. The component split is a stated assumption, not a measured '
            'build-up. Treat this as a screening reference only.</div>',
            unsafe_allow_html=True,
        )

        index_info = proj_index
        st.markdown(
            f"**Project rate index:** {index_info['index']} "
            f"(from {index_info['matched']} SoR-matched items; "
            f"BOQ avg HK${index_info['boq_avg']:,.2f} vs SoR demo avg HK${index_info['sor_avg']:,.2f})"
            if index_info.get("boq_avg") is not None
            else f"**Project rate index:** {index_info['index']} ({index_info['notes'][0]})"
        )

        rate_items = [f["item"] for f in flags if f.get("type") == "rate" and f.get("item")]
        options = [f"{r['item']} · {r['description'][:52]}" for r in rows]
        default_idx = 0
        for i, r in enumerate(rows):
            if r["item"] in rate_items:
                default_idx = i
                break
        sel = st.selectbox("Choose an item to build up", options, index=default_idx)
        chosen = rows[options.index(sel)]

        build = fairrate.build_fair_rate(
            chosen["description"], chosen["rate"], sor_lookup, project_index=index_info["index"]
        )
        st.markdown(f"**Item:** {chosen['item']} · {chosen['description']} ({chosen['unit']})")

        m_sor = build["matched_sor"] or "no SoR demo match"
        m_sor_rate = f"HK${build['sor_rate']:,.2f}" if build["sor_rate"] is not None else "n/a"
        st.markdown(
            f"| Step | Value |\n"
            f"| --- | --- |\n"
            f"| Matched SoR demo item | {m_sor} |\n"
            f"| SoR demo rate | {m_sor_rate} / {build['sor_unit'] or 'n/a'} |\n"
            f"| Project rate index | {build['project_rate_index']} |\n"
            f"| BOQ rate | HK${chosen['rate']:,.2f} |\n"
            f"| Adjusted fair rate | HK${build['adjusted_rate']:,.2f} |\n"
        )

        comp = build["components"]
        comp_df = pd.DataFrame({
            "Component": ["Material", "Labour", "Plant", "Overheads", "Profit"],
            "HK$": [comp["material"], comp["labour"], comp["plant"], comp["overheads"], comp["profit"]],
        }).set_index("Component")
        st.bar_chart(comp_df)
        st.markdown(f"Component total: HK${build['total']:,.2f}")

        for note in build["notes"]:
            st.markdown(f"- {note}")

    # ================= Step 4: Cashflow =================
    with tab4:
        st.markdown('<div class="section-title">💧 Cashflow</div>', unsafe_allow_html=True)
        st.markdown(
            "Spread the estimated total over the contract months with an S-curve, and show the "
            "working capital the builder carries before interim payments land (a two-month, "
            "roughly 60-day lag, matching the Cap. 652 default payment window)."
        )
        months = st.number_input(
            "Contract duration (months)", min_value=1, max_value=60, value=12, step=1
        )
        total = est["grand_total"]
        curve = s_curve_cashflow(total, int(months))
        gap = interim_payment_gap(curve, payment_lag_months=2)

        labels = [f"M{m['month']}" for m in curve]
        curve_df = pd.DataFrame({
            "Cumulative (HK$)": [m["cumulative_amount"] for m in curve],
        }, index=labels)
        monthly_df = pd.DataFrame({
            "Monthly (HK$)": [m["monthly_amount"] for m in curve],
        }, index=labels)
        gap_df = pd.DataFrame({
            "Working capital gap (HK$)": [g["gap"] for g in gap],
        }, index=labels)

        st.markdown(f"Estimated total spread: **HK${total:,.0f}** over {int(months)} months.")
        st.markdown("**S-curve (cumulative spend)**")
        st.line_chart(curve_df)
        st.markdown("**Monthly spend**")
        st.bar_chart(monthly_df)
        st.markdown("**Interim payment gap (60-day lag)**")
        st.bar_chart(gap_df)
        st.markdown(
            f"Peak working-capital gap: **HK${max((g['gap'] for g in gap), default=0):,.0f}**. "
            "This is the cash the builder is out of pocket before payment lands; it is a planning "
            "figure, not a forecast of actual receipts."
        )

    # ================= Step 5: Security of Payment =================
    with tab5:
        st.markdown('<div class="section-title">📄 Security of Payment (Cap. 652)</div>', unsafe_allow_html=True)
        st.markdown(
            "Generate a payment claim and a payment response in the shape Cap. 652 expects "
            "(in writing, identifies the work, states the amount, gives the basis of calculation), "
            "and see the statutory deadlines computed from the claim date."
        )
        st.markdown(
            '<div class="disclaimer">This is a screening helper, not legal advice. Review any '
            'generated document against Cap. 652 and the contract before serving it.</div>',
            unsafe_allow_html=True,
        )

        with st.form("sop_form"):
            claim_date = st.date_input("Payment claim date", value=date.today())
            period = st.text_input("Work period covered", value="e.g. 1-31 Aug 2026")
            work_desc = st.text_area("Work description", value=_boq_summary(rows, est))
            amount = st.number_input(
                "Amount claimed (HK$)", min_value=0.0, value=float(est["grand_total"]), step=1000.0
            )
            submitted = st.form_submit_button("Generate claim + response")

        if submitted:
            dl = sop652.deadlines(claim_date)
            st.markdown("**Statutory timetable (from the claim date)**")
            st.markdown(
                f"- Payment response due: **{sop652.format_hk(dl['payment_response_deadline'])}** "
                f"(30 days, Cap. 652 s. 31)\n"
                f"- Payment due: **{sop652.format_hk(dl['payment_deadline'])}** "
                f"(60 days, Cap. 652 s. 32)\n"
                f"- Adjudication referral window opens **{sop652.format_hk(dl['adjudication_window_open'])}** "
                f"and closes **{sop652.format_hk(dl['adjudication_window_close'])}** (28 days, s. 47/48)"
            )
            claim_info = {
                "claimant": "the contractor",
                "respondent": "the employer",
                "contract_ref": "Contract ref (add yours)",
                "claim_number": "1",
                "work_period": period or "(period not stated)",
                "work_description": work_desc,
                "amount_claimed": amount,
                "basis_of_calculation": "Measured work per the BOQ, quantities x rates.",
            }
            claim = sop652.payment_claim(claim_info)
            response = sop652.payment_response({
                **claim_info,
                "admitted_amount": amount,
                "disputed_amount": 0.0,
                "reasons": "No amount withheld on this claim.",
                "calculation": "Admitted amount matches the claimed amount.",
            })
            c_claim, c_resp = st.columns(2)
            with c_claim:
                st.markdown("**Payment claim**")
                st.code(claim["text"], language=None)
                st.download_button(
                    "Download claim (.txt)", data=claim["text"],
                    file_name="payment_claim.txt", mime="text/plain",
                )
            with c_resp:
                st.markdown("**Payment response**")
                st.code(response["text"], language=None)
                st.download_button(
                    "Download response (.txt)", data=response["text"],
                    file_name="payment_response.txt", mime="text/plain",
                )
        else:
            st.caption("Fill the form above to generate the documents.")

        st.markdown('<div class="section-title">🔎 Subcontract clause audit</div>', unsafe_allow_html=True)
        st.markdown(
            "Paste a subcontract clause to screen for pay-when-paid or conditional-payment "
            "language, which Cap. 652 voids. This is a keyword screen: it can miss reworded "
            "clauses, so read the full text."
        )
        contract_text = st.text_area(
            "Subcontract text", height=160,
            placeholder="Paste the payment clause here, for example: 'Payment to the subcontractor is conditional upon receipt of payment from the employer.'",
        )
        if contract_text.strip():
            contract_flags = sop652.scan_contract(contract_text)
            st.markdown(sop652.scan_summary(contract_flags))
            for f in contract_flags:
                st.markdown(_flag_card(f), unsafe_allow_html=True)

# ---------------------------------------------------------------- plain-language review
if rows:
    st.markdown('<div class="section-title">🧠 Plain-language review</div>', unsafe_allow_html=True)
    with st.spinner("Writing the plain-language review (free AI, may take a minute)..."):
        review, status = llm_review(len(rows), est["trades"], flags, est["grand_total"])
    if not status.startswith("llm_ok"):
        review = fallback_review(flags, est["grand_total"])
        tag = f"rule-based fallback ({status})"
    else:
        tag = status
    st.caption(
        f"Provider: {tag}. This is optional plain-language prose, not analysis; "
        "the findings come from the deterministic flags and tables above."
    )
    safe_review = review.replace("$", "\\$")
    st.markdown(f'<div class="review-panel">{safe_review}</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- footer
st.markdown(
    '<div class="app-footer">Built for the Smart QS Hackathon 2026 · Housing Bureau + Cyberport + HKU. '
    'Hong Kong regime only: HKSMM5 trade framing, ArchSD-style SoR (demo subset), and Cap. 652. '
    'Screening only: final pricing and legal steps stay with a qualified quantity surveyor or lawyer.</div>',
    unsafe_allow_html=True,
)
