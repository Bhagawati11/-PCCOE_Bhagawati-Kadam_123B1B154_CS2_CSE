"""Deterministic ASIL determination (rule ASIL-1). The LLM never decides the ASIL."""
ASIL_ORDER = ["QM", "A", "B", "C", "D"]


def determine_asil(s, e, c):
    if s not in (0, 1, 2, 3) or e not in (0, 1, 2, 3, 4) or c not in (0, 1, 2, 3):
        raise ValueError("S must be 0-3, E 0-4, C 0-3")
    if s == 0 or e == 0 or c == 0:
        return "QM"
    return {10: "D", 9: "C", 8: "B", 7: "A"}.get(s + e + c, "QM")
