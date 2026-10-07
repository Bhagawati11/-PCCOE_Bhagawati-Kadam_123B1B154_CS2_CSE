import json
import pandas as pd
import streamlit as st
import config, db, llm
from asil import determine_asil
from reqcheck import check_requirement
from traceability import completeness
from rag import VectorIndex, load_blocks, load_library

st.set_page_config(page_title="HARA Assistant", layout="wide")
st.title("Functional Safety HARA and Safety Requirement Assistant")
st.caption("Item: Electric Power Steering (synthetic). Local LLM (Ollama) + RAG (FAISS) + deterministic ASIL, "
           "requirement and traceability rules. AI output is a draft; an engineer approves every entry.")


@st.cache_resource(show_spinner="Building local indexes...")
def get_indexes():
    return (VectorIndex(load_blocks(config.ITEM_FILE, "ITEM")), VectorIndex(load_library(config.LIB_FILE)),
            VectorIndex(load_blocks(config.RULES_FILE, "RULE")))


item_idx, lib_idx, rule_idx = get_indexes()
rules_by = {r["id"]: r for r in rule_idx.items}
SER_RULES = [r for r in rule_idx.items if r["id"].split("-")[0] in ("SEV", "EXP", "CTL", "ASIL")]

with st.sidebar:
    st.header("Knowledge base")
    st.write(f"Item blocks: **{len(item_idx.items)}**  \nApproved library hazards: **{len(lib_idx.items)}**  \n"
             f"Rules: **{len(rule_idx.items)}**")
    st.write(f"Model: `{config.LLM_MODEL}`  \nEmbeddings: `{config.EMBED_MODEL}`")
    st.divider()
    st.caption("Demo helpers (synthetic data, marked 'demo seed')")
    if st.button("Load demo HARA data"):
        db.seed_demo(); st.rerun()
    if st.button("Clear all saved HARA data"):
        db.reset(); st.rerun()


def show_evidence(blocks):
    with st.expander("Retrieved evidence / citations"):
        for b in blocks:
            sc = f" (score {b['score']:.2f})" if "score" in b else ""
            st.markdown(f"**[{b['id']}]**{sc}")
            st.text(b["text"])


def show_cite_check(text, blocks):
    cc = llm.citation_check(text, blocks)
    if cc["ok"]:
        st.success("Citation check: all cited IDs " + ", ".join(cc["cited"]) + " were in the retrieved evidence.")
    elif cc["invalid"]:
        st.error("Citation check: cited IDs not in the retrieved evidence: " + ", ".join(cc["invalid"]))
    else:
        st.warning("Citation check: the answer cites no source ID.")


for k, v in {"hz_S": 3, "hz_E": 4, "hz_C": 3, "hz_malf": "", "hz_hazard": "", "hz_rat": "",
             "sg_text": "", "sg_safe": "", "sg_ftti": "", "FSR_text": "", "FSR_alloc": "", "FSR_ver": "",
             "TSR_text": "", "TSR_alloc": "", "TSR_ver": ""}.items():
    st.session_state.setdefault(k, v)
if st.session_state.get("flash"):
    st.success(st.session_state.pop("flash"))

tab1, tab2, tab3, tab4 = st.tabs(["Item & Q&A", "Hazard analysis (HARA)", "Safety goals & requirements", "Traceability & export"])

# ---------------------------------------------------------------- Tab 1
with tab1:
    q = st.text_input("Ask about the item, the approved hazard library or the HARA rules "
                      "(e.g. 'How is the ASIL determined?')")
    if st.button("Ask") and q:
        blocks = lib_idx.search(q, config.TOP_K) + item_idx.search(q, 2) + rule_idx.search(q, 3)
        with st.spinner("Thinking locally..."):
            ans = llm.ask(llm.build_prompt(llm.qa_task(q), blocks))
        st.write(ans)
        show_cite_check(ans, blocks)
        show_evidence(blocks)

# ---------------------------------------------------------------- Tab 2
with tab2:
    c1, c2 = st.columns(2)
    fn = c1.selectbox("Item function", config.FUNCTIONS)
    gw = c2.selectbox("Guideword", config.GUIDEWORDS)
    scen = st.text_input("Operating situation", "Highway speed, straight road")
    if st.button("Find similar approved hazards and suggest (AI)"):
        sim = lib_idx.search(f"{fn} {gw} {scen}", config.TOP_K)
        blocks = sim + item_idx.search(fn, 2) + SER_RULES
        with st.spinner("Generating suggestion locally..."):
            text = llm.ask(llm.build_prompt(llm.suggest_task(fn, gw, scen), blocks))
        st.session_state["suggest"] = {"text": text, "blocks": blocks, "sim": sim}
        top = sim[0]
        st.session_state.update(hz_S=top["S"], hz_E=top["E"], hz_C=top["C"], hz_malf=top["malfunction"],
                                hz_hazard=top["hazard"], hz_rat="")
    sg = st.session_state.get("suggest")
    if sg:
        st.subheader("Similar approved library hazards")
        st.dataframe(pd.DataFrame([{"id": h["id"], "malfunction": h["malfunction"], "situation": h["scenario"],
                                    "S": h["S"], "E": h["E"], "C": h["C"], "ASIL": h["asil"],
                                    "score": round(h["score"], 2)} for h in sg["sim"]]), use_container_width=True)
        st.subheader("AI suggestion (draft)")
        st.markdown(sg["text"])
        show_cite_check(sg["text"], sg["blocks"])
        show_evidence(sg["blocks"])
        st.subheader("Engineer rating")
        st.caption("S, E and C were pre-filled from the closest library entry. Change them with your own judgement.")
        a, b, c = st.columns(3)
        S = a.selectbox("Severity S", [0, 1, 2, 3], key="hz_S")
        E = b.selectbox("Exposure E", [0, 1, 2, 3, 4], key="hz_E")
        C = c.selectbox("Controllability C", [0, 1, 2, 3], key="hz_C")
        asil = determine_asil(S, E, C)
        st.metric("ASIL (deterministic rule ASIL-1)", asil)
        st.text_input("Malfunctioning behaviour", key="hz_malf")
        st.text_area("Hazard / hazardous event", key="hz_hazard")
        st.text_area("Rationale for S, E, C (engineer)", key="hz_rat")
        if st.button("Explain rating (AI)"):
            ev = dict(function=fn, malfunction=st.session_state.hz_malf, hazard=st.session_state.hz_hazard,
                      scenario=scen, S=S, E=E, C=C, asil=asil)
            with st.spinner("Generating..."):
                t = llm.ask(llm.build_prompt(llm.rating_task(ev), SER_RULES))
            st.markdown(t); show_cite_check(t, SER_RULES)

        def _save_event(status):
            s = st.session_state
            eid = db.add_event(dict(function=fn, guideword=gw, scenario=scen, malfunction=s.hz_malf, hazard=s.hz_hazard,
                                    S=s.hz_S, E=s.hz_E, C=s.hz_C, asil=determine_asil(s.hz_S, s.hz_E, s.hz_C),
                                    rationale=s.hz_rat, similar_to=sg["sim"][0]["id"], status=status))
            s["flash"] = f"Saved hazardous event {eid} as {status}"
            s["suggest"] = None
        d1, d2 = st.columns(2)
        d1.button("Approve hazardous event", on_click=_save_event, args=("APPROVED",))
        d2.button("Reject hazardous event", on_click=_save_event, args=("REJECTED",))

# ---------------------------------------------------------------- Tab 3
with tab3:
    events = [e for e in db.rows("events") if e["status"] == "APPROVED" and e["asil"] != "QM"]
    goals = db.rows("goals")
    reqs = db.rows("reqs")
    st.subheader("1. Safety goal")
    if not events:
        st.info("No approved hazardous event with ASIL A-D yet. Approve one in the HARA tab (or load the demo data).")
    else:
        labels = [f"{e['id']} [ASIL {e['asil']}] {e['malfunction']}" for e in events]
        ev = events[labels.index(st.selectbox("Approved hazardous event", labels))]
        if st.button("Draft safety goal (AI)"):
            blocks = [rules_by["SG-1"], rules_by["SG-2"]] + item_idx.search(ev["function"], 2)
            with st.spinner("Drafting..."):
                t = llm.ask(llm.build_prompt(llm.sg_task(ev), blocks))
            g, sstate, ft = llm.parse_sg(t)
            st.session_state.update(sg_text=g, sg_safe=sstate, sg_ftti=ft)
            st.caption("Raw AI draft:"); st.markdown(t); show_cite_check(t, blocks)
        st.text_area("Safety goal text", key="sg_text")
        st.text_input("Safe state", key="sg_safe")
        st.text_input("FTTI", key="sg_ftti")

        def _save_goal():
            s = st.session_state
            gid = db.add_goal(dict(event_id=ev["id"], text=s.sg_text, asil=ev["asil"], safe_state=s.sg_safe, ftti=s.sg_ftti))
            s["flash"] = f"Saved safety goal {gid} (ASIL {ev['asil']}, inherited from {ev['id']})"
            s.update(sg_text="", sg_safe="", sg_ftti="")
        st.button("Approve safety goal", on_click=_save_goal,
                  disabled=not (st.session_state.sg_text.strip() and st.session_state.sg_ftti.strip()))


    def requirement_section(kind, parents):
        st.subheader(f"{'2' if kind == 'FSR' else '3'}. {kind}" +
                     (" (functional safety requirement)" if kind == "FSR" else " (technical safety requirement)"))
        if not parents:
            st.info("Needs an approved " + ("safety goal." if kind == "FSR" else "FSR."))
            return
        labels = [f"{p['id']} [ASIL {p['asil']}] {p['text'][:80]}" for p in parents]
        p = parents[labels.index(st.selectbox(f"Parent of the {kind}", labels, key=f"{kind}_parent"))]
        if st.button(f"Draft {kind} (AI)", key=f"{kind}_draft"):
            blocks = [rules_by[r] for r in ("REQ-1", "REQ-2", "REQ-3", "REQ-4")] + [rules_by["SG-1"]]
            with st.spinner("Drafting..."):
                t = llm.ask(llm.build_prompt(llm.req_task(kind, p), blocks))
            st.session_state[f"{kind}_text"] = t.strip().splitlines()[0] if t.strip() else ""
            show_cite_check(t, blocks)
        st.text_area(f"{kind} text", key=f"{kind}_text")
        if kind == "FSR":
            st.text_input("Allocated to (architecture element)", key="FSR_alloc")
        st.text_input("Verification method", key=f"{kind}_ver")
        s = st.session_state
        cand = dict(kind=kind, text=s[f"{kind}_text"], asil=p["asil"], parent=p["id"],
                    allocated_to=s["FSR_alloc"] if kind == "FSR" else "", verification=s[f"{kind}_ver"])
        issues = check_requirement(cand)
        if issues:
            st.warning("Requirement quality check:\n\n" + "\n".join("- " + i for i in issues))
        else:
            st.success(f"Requirement quality check passed. ASIL {p['asil']} is inherited from {p['id']}.")

        def _save():
            rid = db.add_req(cand)
            st.session_state["flash"] = f"Saved {rid}"
            st.session_state.update({f"{kind}_text": "", f"{kind}_ver": ""})
            if kind == "FSR":
                st.session_state["FSR_alloc"] = ""
        st.button(f"Approve {kind}", key=f"{kind}_save", on_click=_save, disabled=bool(issues))

    requirement_section("FSR", goals)
    requirement_section("TSR", [r for r in reqs if r["kind"] == "FSR"])

# ---------------------------------------------------------------- Tab 4
with tab4:
    events, goals, reqs = db.rows("events"), db.rows("goals"), db.rows("reqs")
    if not events:
        st.info("Nothing saved yet. Approve hazardous events or load the demo data from the sidebar.")
    else:
        res = completeness(events, goals, reqs)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Hazardous events", len(events))
        m2.metric("Safety goals", len(goals))
        m3.metric("Requirements", len(reqs))
        m4.metric("Traceability completeness", f"{res['completeness_pct']}%")
        matrix = []
        for e in events:
            if e["status"] != "APPROVED":
                continue
            gs = [g for g in goals if g["event_id"] == e["id"]] or [None]
            for g in gs:
                fs = [r for r in reqs if g and r["kind"] == "FSR" and r["parent"] == g["id"]] or [None]
                for f in fs:
                    ts = [r for r in reqs if f and r["kind"] == "TSR" and r["parent"] == f["id"]] or [None]
                    for t in ts:
                        matrix.append({"Hazard": e["id"], "ASIL": e["asil"], "Goal": g["id"] if g else "-",
                                       "FSR": f["id"] if f else "-", "TSR": t["id"] if t else "-"})
        st.subheader("Traceability matrix")
        st.dataframe(pd.DataFrame(matrix), use_container_width=True)
        st.subheader("Gaps (rule TRC-1)")
        if res["gaps"]:
            st.dataframe(pd.DataFrame(res["gaps"], columns=["type", "id", "description"]), use_container_width=True)
        else:
            st.success("No traceability gaps.")
        st.subheader("HARA worksheet")
        st.dataframe(pd.DataFrame(events), use_container_width=True)
        md = ["# HARA report (draft)\n"]
        for e in events:
            md.append(f"- {e['id']} [{e['status']}] {e['function']} / {e['malfunction']}: S{e['S']} E{e['E']} C{e['C']} = ASIL {e['asil']}")
        md.append("\n## Safety goals")
        md += [f"- {g['id']} (ASIL {g['asil']}, from {g['event_id']}): {g['text']} | safe state: {g['safe_state']} | FTTI: {g['ftti']}" for g in goals]
        md.append("\n## Requirements")
        md += [f"- {r['id']} (ASIL {r['asil']}, parent {r['parent']}): {r['text']} | verification: {r['verification']}" for r in reqs]
        md.append(f"\nTraceability completeness: {res['completeness_pct']}%")
        a, b, c = st.columns(3)
        a.download_button("Export matrix CSV", pd.DataFrame(matrix).to_csv(index=False), "traceability_matrix.csv")
        b.download_button("Export all JSON", json.dumps({"events": events, "goals": goals, "reqs": reqs, "gaps": res["gaps"]}, indent=2), "hara_export.json")
        c.download_button("Export report (Markdown)", "\n".join(md), "hara_report.md")
