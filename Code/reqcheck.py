"""Deterministic requirement quality checks (rules REQ-1 to REQ-5)."""
import re

VAGUE = ["appropriate", "adequate", "adequately", "fast", "quickly", "as soon as possible", "asap",
         "sufficient", "reasonable", "user-friendly", "etc", "and/or", "if possible", "where possible",
         "as needed", "properly", "robust", "minimal", "safe manner"]
MEASURE_RE = re.compile(r"\b\d+(\.\d+)?\s*(ms|s|sec|seconds|%|nm|km/h|v|ma|hz|khz|deg|degrees|°|n)(?![A-Za-z])", re.I)
VALID_ASIL = ("QM", "A", "B", "C", "D")


def check_requirement(req):
    """req: dict with kind, text, asil, parent, allocated_to, verification. Returns list of issue strings."""
    issues = []
    text = (req.get("text") or "").strip()
    if not text:
        return ["REQ-1: requirement text is empty"]
    n_shall = len(re.findall(r"\bshall\b", text, re.I))
    if n_shall == 0:
        issues.append("REQ-1: the word 'shall' is missing")
    elif n_shall > 1:
        issues.append("REQ-1: more than one 'shall' (split into atomic requirements)")
    for w in VAGUE:
        if re.search(r"(?<![\w])" + re.escape(w) + r"(?![\w])", text, re.I):
            issues.append(f"REQ-2: vague term '{w}'")
    if not MEASURE_RE.search(text):
        issues.append("REQ-3: no measurable value with unit (e.g. 200 ms, 1.5 Nm)")
    if req.get("asil") not in VALID_ASIL:
        issues.append("REQ-3: ASIL missing or invalid")
    if not req.get("parent"):
        issues.append("REQ-4: no parent reference")
    if req.get("kind") == "FSR" and not (req.get("allocated_to") or "").strip():
        issues.append("REQ-4: FSR is not allocated to an architecture element")
    if not (req.get("verification") or "").strip():
        issues.append("REQ-5: no verification method")
    return issues
