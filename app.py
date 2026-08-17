import json, re
from pathlib import Path
from difflib import SequenceMatcher
import streamlit as st

BASE = Path(__file__).parent
DATA = json.loads((BASE / "knowledge_base.json").read_text(encoding="utf-8"))
SYMPTOMS = DATA["symptoms"]
DIAGNOSTICS = DATA["diagnostics"]

st.set_page_config(page_title="Maintenance Diagnostic Assistant", page_icon="🔧", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 2rem; max-width: 1200px;}
.hero {padding: 1.2rem 1.4rem; border-radius: 16px; border: 1px solid rgba(128,128,128,.25); margin-bottom: 1.2rem;}
.small {opacity: .72; font-size: .9rem;}
</style>
""", unsafe_allow_html=True)

def tokens(s):
    return set(re.findall(r"[a-zA-Z0-9]+", str(s).lower()))

def similarity(a, b):
    a, b = str(a), str(b)
    if not a or not b:
        return 0
    ta, tb = tokens(a), tokens(b)
    overlap = len(ta & tb) / max(1, len(ta))
    seq = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return .68 * overlap + .32 * seq

def search(query, symptom=""):
    q = f"{symptom} {query}".strip()
    rows = []
    for item in DIAGNOSTICS:
        s = max(similarity(q, item.get("cause", "")), .75 * similarity(q, item.get("remedy", "")))
        rows.append((s, item))
    return sorted(rows, key=lambda x: x[0], reverse=True)

def questions_for(items):
    patterns = [
        ("pressure", "Is the relevant pressure/air pressure normal?"),
        ("air", "Is the air supply functioning normally?"),
        ("sensor", "Is the relevant sensor clean and functioning?"),
        ("suction", "Is suction functioning normally?"),
        ("motor", "Does the motor run normally?"),
        ("belt", "Is the belt/chain correctly tensioned and aligned?"),
        ("alignment", "Is the mechanism correctly aligned?"),
        ("jam", "Is there a jam or obstruction?"),
        ("lubric", "Is lubrication adequate?"),
        ("loose", "Are connections and fasteners secure?"),
        ("broken", "Is any component visibly damaged or broken?"),
        ("clean", "Is the relevant area clean and free of buildup?"),
        ("voltage", "Is the electrical supply/voltage normal?"),
        ("temperature", "Is the machine temperature normal?"),
    ]
    text = " ".join(i.get("cause", "") + " " + i.get("remedy", "") for _, i in items[:8]).lower()
    return [q for key, q in patterns if key in text][:5]

st.markdown("""
<div class="hero">
<h1>🔧 Maintenance Diagnostic Assistant</h1>
<p class="small">Troubleshoot equipment using your approved maintenance knowledge base.</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Diagnosis")
    machine = st.text_input("Machine / equipment", placeholder="e.g. Conveyor, filler, forklift")
    symptom_labels = ["-- Select a known symptom --"] + [f"{k}. {v}" for k, v in SYMPTOMS.items()]
    selected = st.selectbox("Known symptom", symptom_labels)
    selected_text = "" if selected == symptom_labels[0] else selected.split(". ", 1)[1]
    st.divider()
    st.caption(f"Knowledge base: {len(SYMPTOMS)} symptoms • {len(DIAGNOSTICS)} records")
    if st.button("↺ Reset diagnosis", use_container_width=True):
        for k in ["results", "questions", "answers", "diagnosed"]:
            st.session_state.pop(k, None)
        st.rerun()

st.subheader("1. Describe the problem")
issue = st.text_area("What is happening?", placeholder="Describe the alarm, abnormal movement, noise, quality problem, leak, stoppage, etc.", height=130)

if st.button("🔍 Diagnose", type="primary", use_container_width=True):
    if not issue.strip() and not selected_text:
        st.warning("Please select a symptom or describe the problem.")
    else:
        results = search(issue, selected_text)
        st.session_state.results = results
        st.session_state.questions = questions_for(results)
        st.session_state.answers = {}
        st.session_state.diagnosed = False

if "results" in st.session_state:
    results = st.session_state.results
    if st.session_state.get("questions"):
        st.divider()
        st.subheader("2. Quick diagnostic checks")
        st.caption("Answer what you can safely verify. These checks only prioritize the existing knowledge base.")
        for i, q in enumerate(st.session_state.questions):
            st.session_state.answers[i] = st.radio(q, ["Not checked", "Yes", "No"], key=f"answer_{i}", horizontal=True)
        if st.button("Continue to result →", type="primary"):
            st.session_state.diagnosed = True

    if st.session_state.get("diagnosed") or not st.session_state.get("questions"):
        st.divider()
        st.subheader("3. Diagnostic result")
        ranked = []
        for base, item in results:
            adjusted = base
            combined = item.get("cause", "") + " " + item.get("remedy", "")
            for i, ans in st.session_state.get("answers", {}).items():
                if ans == "Yes" and tokens(st.session_state.questions[i]) & tokens(combined): adjusted += .08
                elif ans == "No" and tokens(st.session_state.questions[i]) & tokens(combined): adjusted -= .04
            ranked.append((adjusted, item))
        ranked.sort(key=lambda x: x[0], reverse=True)
        best_score, best = ranked[0]
        confidence = max(10, min(98, round(best_score * 100)))
        st.success(f"**Most likely cause:** {best.get('cause') or 'Cause not specified'}")
        st.progress(confidence, text=f"Diagnostic confidence: {confidence}%")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Recommended action")
            st.write(best.get("remedy") or "No remedy specified in the knowledge base.")
        with c2:
            st.markdown("### Responsibility")
            owner = best.get("owner", "")
            if owner == "M": st.error("🛠️ Maintenance intervention")
            elif owner == "C": st.info("👷 Operator / conductor check")
            else: st.warning("Responsibility not specified")
        st.markdown("### Other possible causes")
        for n, (score, item) in enumerate(ranked[1:6], 2):
            with st.container(border=True):
                st.markdown(f"**{n}. {item.get('cause') or 'Cause not specified'}**")
                if item.get("remedy"): st.write(item["remedy"])
                owner = item.get("owner", "")
                st.caption("Maintenance" if owner == "M" else "Operator / conductor" if owner == "C" else "Responsibility not specified")
        st.warning("⚠️ Safety: This assistant supports troubleshooting and does not replace the machine manual, lockout/tagout procedure, risk assessment, or a qualified maintenance decision. Stop the machine when required by your approved safety procedure.")

st.divider()
st.caption("Maintenance Diagnostic Assistant • Free prototype • No paid AI API required")
