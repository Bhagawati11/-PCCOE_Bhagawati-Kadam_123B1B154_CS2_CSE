import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = os.path.join(ROOT, "Input_Data")
ITEM_FILE = os.path.join(INPUT_DIR, "item_definition.txt")
LIB_FILE = os.path.join(INPUT_DIR, "hara_library.csv")
RULES_FILE = os.path.join(INPUT_DIR, "hara_rules.txt")
RESULTS_DIR = os.path.join(ROOT, "Evaluation_Results")
DB_PATH = os.path.join(RESULTS_DIR, "hara.db")
OLLAMA_URL = "http://localhost:11434/api/generate"
LLM_MODEL = "llama3.2:3b"
EMBED_MODEL = "all-MiniLM-L6-v2"
TOP_K = 3

FUNCTIONS = [
    "F1 Provide steering assist torque",
    "F2 Measure driver steering torque",
    "F3 Active return to centre",
    "F4 Fault detection and driver warning",
    "F5 Lane-keeping torque overlay",
]
GUIDEWORDS = [
    "No / loss of function",
    "Unintended activation",
    "Too much / too high",
    "Too little / too low",
    "Too early / too late (delay)",
    "Wrong direction (reversed)",
    "Stuck / intermittent",
]
