import io
import re
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Forklift Shift Log", page_icon="🧧", layout="wide")

st.title("🧧 Electric Forklift Shift Log")
st.caption("Paste the OC shift report once. The app extracts the records, validates them, shows a terminal-style summary, and creates an Excel register.")

SAMPLE = '''Electric Forklift Status Report
📅 Date: 17/8/2026
⏰ Time: 3:00 PM

🧧 FLT Code: 30
📊 Status: Charging
👷 Operator:
⚙️ Operation:
🔋 Charge: 50%

🧧 FLT Code: 29
📊 Status: Active
👷 Operator: Eyasu E
⚙️ Operation: L2
🔋 Charge: 90%

🧧 FLT Code: 13
📊 Status: Active
👷 Operator: Wondewosen
⚙️ Operation: inside
🔋 Charge: 100%

🧧 FLT Code: 14
📊 Status: Charging
👷 Operator:
⚙️ Operation:
🔋 Charge: 60%

🧧 FLT Code: 24
📊 Status: Charging
👷 Operator:
⚙️ Operation:
🔋 Charge: 55%

🧧 FLT Code: 31
📊 Status: Active
👷 Operator: Teshale
⚙️ Operation: L1
🔋 Charge: 100%

🧧 FLT Code: 10
📊 Status: Active
👷 Operator: Eliyas M
⚙️ Operation: RM
🔋 Charge: 100%'''

if "forklift_records" not in st.session_state:
    st.session_state.forklift_records = pd.DataFrame()

raw = st.text_area("Paste the OC message here", value="", height=420, placeholder=SAMPLE)


def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def parse_report(text):
    lines = [line.strip() for line in text.replace("\u00a0", " ").splitlines()]
    report_date = ""
    report_time = ""
    for line in lines:
        m = re.search(r"Date\s*:\s*(.+)$", line, re.I)
        if m:
            report_date = clean(m.group(1))
        m = re.search(r"Time\s*:\s*(.+)$", line, re.I)
        if m:
            report_time = clean(m.group(1))

    blocks = re.split(r"(?=FLT\s*Code\s*:)", "\n".join(lines), flags=re.I)
    rows = []
    for block in blocks:
        if not re.search(r"FLT\s*Code\s*:", block, re.I):
            continue
        def get(pattern):
            m = re.search(pattern, block, re.I)
            return clean(m.group(1)) if m else ""
        code = get(r"FLT\s*Code\s*:\s*(\S+)")
        status = get(r"Status\s*:\s*(.*)")
        operator = get(r"Operator\s*:\s*(.*)")
        operation = get(r"Operation\s*:\s*(.*)")
        charge_raw = get(r"Charge\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*%?")
        charge = float(charge_raw) if charge_raw else None
        rows.append({
            "Date": report_date,
            "Time": report_time,
            "FLT Code": code,
            "Status": status.title(),
            "Operator": operator,
            "Operation": operation,
            "Charge %": charge,
        })
    return pd.DataFrame(rows)


if st.button("⚡ Process OC Report", type="primary", use_container_width=True):
    df = parse_report(raw)
    if df.empty:
        st.error("I couldn't find any FLT Code records. Paste the full OC report and try again.")
    else:
        st.session_state.forklift_records = df
        st.success(f"Processed {len(df)} forklift records.")


df = st.session_state.forklift_records

if not df.empty:
    st.divider()
    st.subheader("📟 Shift Terminal Summary")

    active = int((df["Status"].str.lower() == "active").sum())
    charging = int((df["Status"].str.lower() == "charging").sum())
    other = len(df) - active - charging
    avg_charge = df["Charge %"].dropna().mean()
    assigned = int(df["Operator"].fillna("").ne("").sum())
    unassigned = len(df) - assigned

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total FLTs", len(df))
    c2.metric("🟢 Active", active)
    c3.metric("🔋 Charging", charging)
    c4.metric("Average charge", f"{avg_charge:.1f}%" if pd.notna(avg_charge) else "—")
    c5.metric("Unassigned", unassigned)

    # Terminal-style operational readout
    st.code(
        "\n".join([
            "=== ELECTRIC FORKLIFT SHIFT STATUS ===",
            f"DATE : {df.iloc[0]['Date'] or 'Not detected'}    TIME : {df.iloc[0]['Time'] or 'Not detected'}",
            "----------------------------------------",
            f"TOTAL FLT        : {len(df)}",
            f"ACTIVE           : {active}",
            f"CHARGING         : {charging}",
            f"OTHER STATUS     : {other}",
            f"AVG CHARGE       : {avg_charge:.1f}%" if pd.notna(avg_charge) else "AVG CHARGE       : N/A",
            f"OPERATOR ASSIGNED: {assigned}",
            f"OPERATOR MISSING : {unassigned}",
            "----------------------------------------",
        ]),
        language="text",
    )

    st.subheader("📋 Extracted Register")
    display_df = df.copy()
    display_df["Charge %"] = display_df["Charge %"].apply(lambda x: f"{x:.0f}%" if pd.notna(x) else "")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    missing = df[df["Operator"].fillna("").eq("")]
    if not missing.empty:
        st.warning("⚠️ Operator not assigned: " + ", ".join(missing["FLT Code"].astype(str).tolist()))

    # Create an Excel workbook in memory with register + summary.
    excel_df = df.copy()
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        excel_df.to_excel(writer, index=False, sheet_name="Shift Register")
        summary = pd.DataFrame([
            [df.iloc[0]["Date"], df.iloc[0]["Time"], len(df), active, charging, other, avg_charge, assigned, unassigned]
        ], columns=["Date", "Time", "Total FLTs", "Active", "Charging", "Other", "Average Charge %", "Assigned Operators", "Missing Operators"])
        summary.to_excel(writer, index=False, sheet_name="Summary")

    st.download_button(
        "⬇️ Download Excel Register",
        data=output.getvalue(),
        file_name=f"Electric_Forklift_Status_{str(df.iloc[0]['Date']).replace('/','-')}_{str(df.iloc[0]['Time']).replace(':','-').replace(' ','_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.info("Next upgrade: we can make this automatically recognize the OC message format, keep a multi-day master register, and add shift/weekly forklift utilization KPIs.")
