import os, sqlite3, datetime
import config

SCHEMA = {
    "events": "id TEXT PRIMARY KEY, function TEXT, guideword TEXT, scenario TEXT, malfunction TEXT, hazard TEXT, "
              "S INT, E INT, C INT, asil TEXT, rationale TEXT, similar_to TEXT, status TEXT, source TEXT, ts TEXT",
    "goals": "id TEXT PRIMARY KEY, event_id TEXT, text TEXT, asil TEXT, safe_state TEXT, ftti TEXT, status TEXT, source TEXT, ts TEXT",
    "reqs": "id TEXT PRIMARY KEY, kind TEXT, parent TEXT, text TEXT, asil TEXT, allocated_to TEXT, verification TEXT, status TEXT, source TEXT, ts TEXT",
}
PREFIX = {"events": "HZ", "goals": "SG", "reqs": None}


def conn():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    for t, cols in SCHEMA.items():
        c.execute(f"CREATE TABLE IF NOT EXISTS {t}({cols})")
    return c


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def rows(table):
    c = conn()
    out = [dict(r) for r in c.execute(f"SELECT * FROM {table} ORDER BY id")]
    c.close()
    return out


def _next_id(c, table, prefix):
    n = c.execute(f"SELECT COUNT(*) FROM {table} WHERE id LIKE ?", (prefix + "-%",)).fetchone()[0]
    return f"{prefix}-{n + 1:02d}"


def _insert(table, d):
    c = conn()
    if table == "reqs":
        prefix = d["kind"]
    else:
        prefix = PREFIX[table]
    d = dict(d, id=_next_id(c, table, prefix), ts=now())
    cols = [x.split()[0] for x in SCHEMA[table].split(", ")]
    c.execute(f"INSERT INTO {table}({','.join(cols)}) VALUES({','.join('?' * len(cols))})", [d.get(k, "") for k in cols])
    c.commit(); c.close()
    return d["id"]


def add_event(d):
    return _insert("events", dict(d, source=d.get("source", "engineer")))


def add_goal(d):
    return _insert("goals", dict(d, status="APPROVED", source=d.get("source", "engineer")))


def add_req(d):
    return _insert("reqs", dict(d, status="APPROVED", source=d.get("source", "engineer")))


def reset():
    c = conn()
    for t in SCHEMA:
        c.execute(f"DELETE FROM {t}")
    c.commit(); c.close()


def seed_demo():
    """Synthetic demo data for the video. Marked source='demo seed'. HZ-02 chain deliberately lacks a TSR."""
    reset()
    base = dict(function="F1 Provide steering assist torque", guideword="", status="APPROVED", source="demo seed", similar_to="")
    h1 = add_event(dict(base, scenario="Highway speed, driving through a curve", malfunction="Total loss of assist torque",
                        hazard="Driver needs much higher steering force and may leave the lane", S=3, E=3, C=2, asil="B",
                        rationale="Demo seed based on library entry HE-001", similar_to="HE-001"))
    h2 = add_event(dict(base, scenario="Highway speed on a straight road", malfunction="Unintended assist torque without driver input",
                        hazard="Vehicle steers by itself", S=3, E=4, C=3, asil="D",
                        rationale="Demo seed based on library entry HE-002", similar_to="HE-002"))
    add_event(dict(base, scenario="Low speed turn at a junction", malfunction="No active return to centre",
                   hazard="Steering wheel stays turned", S=1, E=4, C=1, asil="QM",
                   rationale="Demo seed based on library entry HE-009", similar_to="HE-009"))
    g1 = add_goal(dict(event_id=h1, text="Avoid loss of steering assist without driver notification", asil="B",
                       safe_state="Assist ramped to zero, warning lamp on, manual steering", ftti="200 ms", source="demo seed"))
    g2 = add_goal(dict(event_id=h2, text="Avoid unintended steering torque at speeds above 60 km/h", asil="D",
                       safe_state="Assist ramped to zero, warning lamp on, manual steering", ftti="100 ms", source="demo seed"))
    f1 = add_req(dict(kind="FSR", parent=g1, asil="B", allocated_to="EPS ECU fault manager", source="demo seed",
                      text="The EPS shall detect a total loss of assist torque and activate the warning lamp within 200 ms.",
                      verification="HIL fault injection"))
    add_req(dict(kind="TSR", parent=f1, asil="B", allocated_to="", source="demo seed",
                 text="The EPS software shall set the warning lamp output within 50 ms after the torque monitor fault flag is set.",
                 verification="Unit test and HIL"))
    add_req(dict(kind="FSR", parent=g2, asil="D", allocated_to="EPS ECU torque monitor", source="demo seed",
                 text="The EPS shall switch off assist torque within 100 ms after an unintended torque above 1.5 Nm is detected.",
                 verification="HIL fault injection"))
