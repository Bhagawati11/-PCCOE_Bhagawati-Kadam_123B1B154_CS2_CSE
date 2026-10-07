"""Deterministic traceability completeness check (rule TRC-1).
Chain: hazardous event -> safety goal -> FSR -> TSR, each with verification and inherited ASIL."""


def completeness(events, goals, reqs):
    gaps, checks = [], 0
    ev = {e["id"]: e for e in events}
    goal_by = {g["id"]: g for g in goals}
    req_by = {r["id"]: r for r in reqs}

    for e in events:
        if e["status"] != "APPROVED" or e["asil"] == "QM":
            continue
        checks += 1
        if not any(g["event_id"] == e["id"] for g in goals):
            gaps.append(("NO_GOAL", e["id"], f"{e['id']} (ASIL {e['asil']}) has no safety goal"))
    for g in goals:
        checks += 1
        if not any(r["kind"] == "FSR" and r["parent"] == g["id"] for r in reqs):
            gaps.append(("NO_FSR", g["id"], f"{g['id']} has no functional safety requirement"))
        e = ev.get(g["event_id"])
        if e:
            checks += 1
            if e["asil"] != g["asil"]:
                gaps.append(("ASIL_MISMATCH", g["id"], f"{g['id']} ASIL {g['asil']} differs from {e['id']} ASIL {e['asil']}"))
    for r in reqs:
        checks += 1
        if not (r.get("verification") or "").strip():
            gaps.append(("NO_VERIFICATION", r["id"], f"{r['id']} has no verification method"))
        parent = goal_by.get(r["parent"]) if r["kind"] == "FSR" else req_by.get(r["parent"])
        if parent:
            checks += 1
            if parent["asil"] != r["asil"]:
                gaps.append(("ASIL_MISMATCH", r["id"], f"{r['id']} ASIL {r['asil']} differs from parent {parent['id']} ASIL {parent['asil']}"))
        if r["kind"] == "FSR":
            checks += 1
            if not any(t["kind"] == "TSR" and t["parent"] == r["id"] for t in reqs):
                gaps.append(("NO_TSR", r["id"], f"{r['id']} has no technical safety requirement"))
    pct = round(100.0 * (checks - len(gaps)) / checks, 1) if checks else 100.0
    return {"checks": checks, "gaps": gaps, "completeness_pct": pct}
