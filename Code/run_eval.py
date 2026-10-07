"""Evaluation for CS2 HARA assistant. Run: python run_eval.py   (add --llm to also test AI drafts; needs Ollama)"""
import os, sys, csv, json, time
import config
from asil import determine_asil
from reqcheck import check_requirement
from traceability import completeness

# Reference ASIL values (anchor cases written independently of the code)
ASIL_ANCHORS = [
    ((3, 4, 3), "D"), ((3, 4, 2), "C"), ((3, 4, 1), "B"), ((3, 3, 3), "C"), ((3, 3, 2), "B"), ((3, 3, 1), "A"),
    ((3, 2, 3), "B"), ((3, 2, 2), "A"), ((3, 2, 1), "QM"), ((3, 1, 3), "A"), ((3, 1, 2), "QM"),
    ((2, 4, 3), "C"), ((2, 4, 2), "B"), ((2, 4, 1), "A"), ((2, 3, 3), "B"), ((2, 3, 2), "A"), ((2, 2, 3), "A"),
    ((1, 4, 3), "B"), ((1, 4, 2), "A"), ((1, 3, 3), "A"), ((1, 1, 1), "QM"), ((0, 4, 3), "QM"), ((3, 0, 3), "QM"),
]

REQ_CASES = [  # (kind, text, asil, parent, allocated, verification, expected_pass)
    ("FSR", "The EPS shall detect a total loss of assist torque and activate the warning lamp within 200 ms.", "B", "SG-01", "EPS ECU", "HIL test", True),
    ("FSR", "The EPS shall switch off assist torque within 100 ms after unintended torque above 1.5 Nm is detected.", "D", "SG-02", "EPS ECU", "HIL test", True),
    ("TSR", "The EPS software shall set the warning lamp output within 50 ms after the fault flag is set.", "B", "FSR-01", "", "Unit test", True),
    ("FSR", "The EPS should detect a loss of assist torque quickly.", "B", "SG-01", "EPS ECU", "HIL test", False),
    ("FSR", "The EPS shall appropriately limit assist torque.", "C", "SG-03", "EPS ECU", "Review", False),
    ("FSR", "The EPS shall detect the fault within 200 ms and the EPS shall warn the driver.", "B", "SG-01", "EPS ECU", "HIL test", False),
    ("FSR", "The EPS shall detect the fault within 200 ms.", "B", "SG-01", "", "HIL test", False),
    ("TSR", "The EPS software shall monitor the torque sensor within 10 ms.", "A", "FSR-02", "", "", False),
    ("TSR", "The EPS software shall monitor the torque sensor within 10 ms.", "", "FSR-02", "", "Unit test", False),
    ("FSR", "The EPS shall limit the overlay torque to 2 Nm and end it within 300 ms after driver override.", "C", "", "EPS ECU", "HIL test", False),
]


def eval_asil():
    ok = sum(determine_asil(*k) == v for k, v in ASIL_ANCHORS)
    return {"anchor_cases": len(ASIL_ANCHORS), "correct": ok, "accuracy": round(ok / len(ASIL_ANCHORS), 3)}


def eval_library():
    from rag import load_library
    lib = load_library(config.LIB_FILE)
    ok = sum(determine_asil(h["S"], h["E"], h["C"]) == h["asil"] for h in lib)
    return {"entries": len(lib), "asil_consistent": ok}


def eval_reqcheck():
    rows, ok = [], 0
    for kind, text, asil, parent, alloc, ver, exp in REQ_CASES:
        issues = check_requirement(dict(kind=kind, text=text, asil=asil, parent=parent, allocated_to=alloc, verification=ver))
        passed = not issues
        ok += passed == exp
        rows.append({"text": text, "expected_pass": exp, "got_pass": passed, "issues": " | ".join(issues)})
    return {"cases": len(REQ_CASES), "correct": ok, "accuracy": round(ok / len(REQ_CASES), 3)}, rows


def eval_traceability():
    ev = lambda i, a, s="APPROVED": dict(id=i, asil=a, status=s)
    events = [ev("HZ-01", "B"), ev("HZ-02", "D"), ev("HZ-03", "C"), ev("HZ-04", "A"), ev("HZ-05", "QM"), ev("HZ-06", "D", "REJECTED")]
    goals = [dict(id="SG-01", event_id="HZ-01", asil="B"), dict(id="SG-02", event_id="HZ-03", asil="C"),
             dict(id="SG-03", event_id="HZ-04", asil="A")]
    rq = lambda i, k, p, a, v="HIL": dict(id=i, kind=k, parent=p, asil=a, verification=v)
    reqs = [rq("FSR-01", "FSR", "SG-01", "B"), rq("TSR-01", "TSR", "FSR-01", "B"), rq("FSR-02", "FSR", "SG-03", "A"),
            rq("FSR-03", "FSR", "SG-03", "A", ""), rq("TSR-02", "TSR", "FSR-03", "B")]
    expected = {("NO_GOAL", "HZ-02"), ("NO_FSR", "SG-02"), ("NO_TSR", "FSR-02"),
                ("NO_VERIFICATION", "FSR-03"), ("ASIL_MISMATCH", "TSR-02")}
    res = completeness(events, goals, reqs)
    found = {(g[0], g[1]) for g in res["gaps"]}
    return {"injected_gaps": len(expected), "detected": len(found & expected), "false_alarms": len(found - expected),
            "completeness_pct_on_test_set": res["completeness_pct"]}


QUESTIONS = [
    ("What is the hazard if the steering assist torque is lost completely while cornering on a highway?", "HE-001"),
    ("Steering pulls by itself on a straight highway without driver input", "HE-002"),
    ("Torque sensor signal drops out intermittently and assist oscillates", "HE-008"),
    ("Warning lamp does not light when the power steering assist fails", "HE-011"),
    ("Lane keeping torque cannot be overridden by the driver", "HE-014"),
    ("Steering wheel does not return to centre after a low speed turn", "HE-009"),
]


def eval_retrieval():
    from rag import VectorIndex, load_library
    idx = VectorIndex(load_library(config.LIB_FILE))
    rows = []
    for q, exp in QUESTIONS:
        t = time.time()
        hits = idx.search(q, config.TOP_K)
        rows.append({"question": q, "expected_id": exp, "hit_in_top3": exp in [h["id"] for h in hits],
                     "top1": hits[0]["id"], "retrieved": "; ".join(f"{h['id']}({h['score']:.2f})" for h in hits),
                     "latency_s": round(time.time() - t, 3)})
    return rows


def eval_llm():
    import llm
    from rag import VectorIndex, load_library, load_blocks
    lib = load_library(config.LIB_FILE)
    lib_by = {h["id"]: h for h in lib}
    rules = load_blocks(config.RULES_FILE, "RULE")
    rules_by = {r["id"]: r for r in rules}
    item = load_blocks(config.ITEM_FILE, "ITEM")
    out = []
    for hid in ("HE-001", "HE-002", "HE-011"):
        h = lib_by[hid]
        ev = dict(function=h["function"], malfunction=h["malfunction"], hazard=h["hazard"], scenario=h["scenario"], asil=h["asil"])
        blocks = [h, rules_by["SG-1"], rules_by["SG-2"], item[7]]
        sg = llm.ask(llm.build_prompt(llm.sg_task(ev), blocks))
        goal, safe, ftti = llm.parse_sg(sg)
        cc = llm.citation_check(sg, blocks)
        out.append({"event": hid, "task": "safety_goal", "output": sg, "citations_ok": cc["ok"], "invalid_cites": cc["invalid"],
                    "has_safe_state": bool(safe), "has_ftti": bool(ftti)})
        parent = dict(id="SG-X", asil=h["asil"], text=goal)
        fb = [rules_by[r] for r in ("REQ-1", "REQ-2", "REQ-3", "REQ-4")] + [rules_by["SG-1"]]
        fsr = llm.ask(llm.build_prompt(llm.req_task("FSR", parent), fb))
        issues = check_requirement(dict(kind="FSR", text=fsr.splitlines()[0] if fsr else "", asil=h["asil"], parent="SG-X",
                                        allocated_to="EPS ECU", verification="HIL test"))
        out.append({"event": hid, "task": "FSR", "output": fsr, "quality_issues": issues, "passes_checker": not issues})
    return out


if __name__ == "__main__":
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    summary = {}
    summary["asil_rule"] = eval_asil(); print("ASIL RULE:", summary["asil_rule"])
    summary["library_consistency"] = eval_library(); print("LIBRARY:", summary["library_consistency"])
    summary["requirement_checker"], rc = eval_reqcheck(); print("REQ CHECKER:", summary["requirement_checker"])
    summary["traceability"] = eval_traceability(); print("TRACEABILITY:", summary["traceability"])
    r = eval_retrieval()
    for x in r:
        print(x)
    rate = sum(x["hit_in_top3"] for x in r) / len(r)
    top1 = sum(x["top1"] == x["expected_id"] for x in r) / len(r)
    summary["retrieval"] = {"questions": len(r), "hit_rate_top3": round(rate, 3), "hit_rate_top1": round(top1, 3)}
    print("RETRIEVAL HIT RATE (top-3):", rate, " (top-1):", round(top1, 3))
    with open(os.path.join(config.RESULTS_DIR, "retrieval_eval.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=r[0].keys()); w.writeheader(); w.writerows(r)
    with open(os.path.join(config.RESULTS_DIR, "requirement_checker_eval.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rc[0].keys()); w.writeheader(); w.writerows(rc)
    if "--llm" in sys.argv:
        o = eval_llm()
        cites = [x for x in o if x["task"] == "safety_goal"]
        reqs = [x for x in o if x["task"] == "FSR"]
        summary["llm_drafts"] = {"safety_goals": len(cites), "citations_valid": sum(x["citations_ok"] for x in cites),
                                 "fsr_drafts": len(reqs), "fsr_pass_checker": sum(x["passes_checker"] for x in reqs)}
        print("LLM DRAFTS:", summary["llm_drafts"])
        json.dump(o, open(os.path.join(config.RESULTS_DIR, "llm_samples.json"), "w"), indent=2)
    json.dump(summary, open(os.path.join(config.RESULTS_DIR, "eval_summary.json"), "w"), indent=2)
    print("Saved results to", config.RESULTS_DIR)
